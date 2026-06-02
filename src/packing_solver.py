from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations
from time import perf_counter
from typing import NamedTuple
from z3 import Bool, If, Int, IntVal, Or, Solver, is_true, sat, unsat

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from z3 import ArithRef, BoolRef, ModelRef


class Mode(StrEnum):
    SQUARES = "squares"
    RECTANGLES_NO_ROTATION = "rectangles_no_rotation"
    RECTANGLES_ROTATION = "rectangles_rotation"


class Status(StrEnum):
    SAT = "SAT"
    UNSAT = "UNSAT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Piece:
    id: str
    width: int
    height: int
    rotatable: bool = False

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def is_square(self) -> bool:
        return self.width == self.height


@dataclass(frozen=True)
class Placement:
    id: str
    x: int
    y: int
    width: int
    height: int
    rotated: bool = False

    def is_within_container(self, container_width: int, container_height: int) -> bool:
        if self.x < 0 or self.y < 0:
            return False
        if self.x + self.width > container_width:
            return False
        if self.y + self.height > container_height:
            return False
        return True

    def overlaps_with(self, other: Placement) -> bool:
        is_separated = (
            self.x + self.width <= other.x
            or other.x + other.width <= self.x
            or self.y + self.height <= other.y
            or other.y + other.height <= self.y
        )
        return not is_separated

    def matches_piece_dimensions(self, piece: Piece) -> bool:
        if self.rotated:
            return self.width == piece.height and self.height == piece.width
        else:
            return self.width == piece.width and self.height == piece.height

    @classmethod
    def from_z3_variables(
        cls,
        model: ModelRef,
        piece: Piece,
        x_var: ArithRef,
        y_var: ArithRef,
        rot_var: BoolRef | None,
    ) -> Placement:
        rotated = bool(rot_var is not None and is_true(model.eval(rot_var, model_completion=True)))
        actual_width = piece.height if rotated else piece.width
        actual_height = piece.width if rotated else piece.height

        return cls(
            id=piece.id,
            x=model.eval(x_var, model_completion=True).as_long(),  # type: ignore
            y=model.eval(y_var, model_completion=True).as_long(),  # type: ignore
            width=actual_width,
            height=actual_height,
            rotated=rotated,
        )


@dataclass(frozen=True)
class PackingInstance:
    name: str
    container_width: int
    container_height: int
    pieces: tuple[Piece, ...]
    mode: Mode = Mode.RECTANGLES_ROTATION
    timeout_seconds: int | None = 10
    symmetry_breaking: bool = True

    def __post_init__(self) -> None:
        if self.container_width <= 0 or self.container_height <= 0:
            raise ValueError("Container dimensions must be positive")
        if self.mode not in Mode:
            raise ValueError(f"Unsupported mode: {self.mode}")
        if not self.pieces:
            raise ValueError("An instance must contain at least one piece")
        seen_ids: set[str] = set()
        for piece in self.pieces:
            if not piece.id:
                raise ValueError("Piece ids must be non-empty")
            if piece.id in seen_ids:
                raise ValueError(f"Duplicate piece id: {piece.id}")
            seen_ids.add(piece.id)
            if piece.width <= 0 or piece.height <= 0:
                raise ValueError(f"Piece {piece.id} has non-positive dimensions")
            if self.mode == Mode.SQUARES and not piece.is_square:
                raise ValueError("Square mode accepts only square pieces")

    @property
    def container_area(self) -> int:
        return self.container_width * self.container_height

    @property
    def total_piece_area(self) -> int:
        return sum(piece.area for piece in self.pieces)

    @classmethod
    def from_squares(
        cls,
        container_size: int,
        square_sizes: list[int],
        *,
        name: str = "square-instance",
        timeout_seconds: int | None = 10,
        symmetry_breaking: bool = True,
    ) -> PackingInstance:
        pieces = tuple(Piece(f"s{i}", side, side, False) for i, side in enumerate(square_sizes))
        return cls(
            name=name,
            container_width=container_size,
            container_height=container_size,
            pieces=pieces,
            mode=Mode.SQUARES,
            timeout_seconds=timeout_seconds,
            symmetry_breaking=symmetry_breaking,
        )

    def solve(self) -> PackingResult:
        ordered_pieces = tuple(sorted(self.pieces, key=lambda piece: (-piece.area, piece.id)))
        stats_base = self._base_stats(ordered_pieces)
        if self.total_piece_area > self.container_area:
            return PackingResult(
                instance_name=self.name,
                mode=self.mode,
                status=Status.UNSAT,
                placements=(),
                solver_time_seconds=0.0,
                stats=stats_base,
                reason="area lower bound",
            )

        class Z3PieceVariables(NamedTuple):
            piece: Piece
            x_var: ArithRef
            y_var: ArithRef
            rot_var: BoolRef | None
            width_expr: ArithRef
            height_expr: ArithRef

        solver = Solver()
        if self.timeout_seconds is not None:
            solver.set(timeout=self.timeout_seconds * 1000)

        z3_pieces: list[Z3PieceVariables] = []
        for piece in ordered_pieces:
            can_rotate = self._piece_can_rotate(piece)
            rot_var = Bool(f"rot_{piece.id}") if can_rotate else None

            width_expr: ArithRef = If(rot_var, piece.height, piece.width) if rot_var is not None else IntVal(piece.width)  # type: ignore
            height_expr: ArithRef = If(rot_var, piece.width, piece.height) if rot_var is not None else IntVal(piece.height)  # type: ignore

            z3_pieces.append(
                Z3PieceVariables(
                    piece=piece,
                    x_var=Int(f"x_{piece.id}"),
                    y_var=Int(f"y_{piece.id}"),
                    rot_var=rot_var,
                    width_expr=width_expr,
                    height_expr=height_expr,
                )
            )

        boundary_constraints = 0
        for item in z3_pieces:
            solver.add(item.x_var >= 0)
            solver.add(item.y_var >= 0)
            solver.add(item.x_var + item.width_expr <= self.container_width)
            solver.add(item.y_var + item.height_expr <= self.container_height)
            boundary_constraints += 4

        non_overlap_constraints = 0
        for item_a, item_b in combinations(z3_pieces, 2):
            solver.add(
                Or(
                    item_a.x_var + item_a.width_expr <= item_b.x_var,
                    item_b.x_var + item_b.width_expr <= item_a.x_var,
                    item_a.y_var + item_a.height_expr <= item_b.y_var,
                    item_b.y_var + item_b.height_expr <= item_a.y_var,
                )
            )
            non_overlap_constraints += 1

        if self.symmetry_breaking and z3_pieces:
            # Reflection symmetry lets the largest piece be placed in the lower-left half
            # without changing satisfiability.
            largest = z3_pieces[0]
            solver.add(2 * largest.x_var + largest.width_expr <= self.container_width)
            solver.add(2 * largest.y_var + largest.height_expr <= self.container_height)

        start = perf_counter()
        check_result = solver.check()
        elapsed = perf_counter() - start

        stats = PackingStats(
            num_pieces=len(z3_pieces),
            num_variables=(2 * len(z3_pieces)) + sum(item.rot_var is not None for item in z3_pieces),
            num_assertions=len(solver.assertions()),
            num_boundary_constraints=boundary_constraints,
            num_non_overlap_constraints=non_overlap_constraints,
            num_rotation_variables=sum(item.rot_var is not None for item in z3_pieces),
            total_piece_area=self.total_piece_area,
            container_area=self.container_area,
        )

        if check_result == unsat:
            return PackingResult(self.name, self.mode, Status.UNSAT, (), elapsed, stats)

        if check_result != sat:
            return PackingResult(self.name, self.mode, Status.UNKNOWN, (), elapsed, stats, reason=str(check_result))

        z3_model = solver.model()
        placements = tuple(
            Placement.from_z3_variables(
                z3_model, item.piece, item.x_var, item.y_var, item.rot_var
            )
            for item in z3_pieces
        )
        result = PackingResult(self.name, self.mode, Status.SAT, placements, elapsed, stats)
        result.validate_result(self)
        return result

    def _base_stats(self, ordered_pieces: tuple[Piece, ...]) -> PackingStats:
        rotation_variables = sum(self._piece_can_rotate(piece) for piece in ordered_pieces)
        return PackingStats(
            num_pieces=len(ordered_pieces),
            num_variables=(2 * len(ordered_pieces)) + rotation_variables,
            num_assertions=0,
            num_boundary_constraints=4 * len(ordered_pieces),
            num_non_overlap_constraints=len(ordered_pieces) * (len(ordered_pieces) - 1) // 2,
            num_rotation_variables=rotation_variables,
            total_piece_area=self.total_piece_area,
            container_area=self.container_area,
        )

    def _piece_can_rotate(self, piece: Piece) -> bool:
        return self.mode == Mode.RECTANGLES_ROTATION and piece.rotatable and not piece.is_square


@dataclass(frozen=True)
class PackingStats:
    num_pieces: int
    num_variables: int
    num_assertions: int
    num_boundary_constraints: int
    num_non_overlap_constraints: int
    num_rotation_variables: int
    total_piece_area: int
    container_area: int


@dataclass(frozen=True)
class PackingResult:
    instance_name: str
    mode: Mode
    status: Status
    placements: tuple[Placement, ...]
    solver_time_seconds: float
    stats: PackingStats
    reason: str = ""

    @property
    def is_sat(self) -> bool:
        return self.status == Status.SAT

    def validate_result(self, instance: PackingInstance) -> None:
        if self.status != Status.SAT:
            return

        if len(self.placements) != len(instance.pieces):
            raise ValueError("Duplicate or missing placements detected")

        expected_ids = {piece.id for piece in instance.pieces}
        actual_ids = {placement.id for placement in self.placements}

        if expected_ids != actual_ids:
            raise ValueError(
                "Placement pieces do not match the instance pieces.\n"
                f"Expected IDs: {tuple(sorted(expected_ids))}\n"
                f"Got      IDs: {tuple(sorted(actual_ids))}"
            )

        pieces_by_id = {piece.id: piece for piece in instance.pieces}
        for placement in self.placements:
            original_piece = pieces_by_id[placement.id]

            if not placement.matches_piece_dimensions(original_piece):
                raise ValueError(
                    f"Piece {placement.id} dimensions were altered. "
                    f"Original: {original_piece}, "
                    f"Got: {placement}"
                )

            if not placement.is_within_container(instance.container_width, instance.container_height):
                raise ValueError(f"{placement} exceeds container boundaries")

        for current_placement, other_placement in combinations(self.placements, 2):
            if current_placement.overlaps_with(other_placement):
                raise ValueError(f"{current_placement} and {other_placement} overlap")


def solve_square_packing(container_size: int, square_sizes: list[int]) -> list[tuple[int, int]] | None:
    instance = PackingInstance.from_squares(container_size, square_sizes)
    result = instance.solve()

    if not result.is_sat:
        return None
    return [(placement.x, placement.y) for placement in result.placements]
