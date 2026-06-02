from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations
from time import perf_counter

from typing import Any

try:
    from z3 import Bool, If, Int, ModelRef, Or, Solver, is_true, sat, unsat
except ModuleNotFoundError as exc:  # pragma: no cover - exercised only without deps
    Bool = If = Int = ModelRef = Or = Solver = is_true = sat = unsat = None
    Z3_IMPORT_ERROR = exc
else:
    Z3_IMPORT_ERROR = None


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
        if Z3_IMPORT_ERROR is not None:
            raise ModuleNotFoundError(
                "z3-solver is required. Install dependencies with `python -m pip install -r requirements.txt`."
            ) from Z3_IMPORT_ERROR

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

        solver = Solver()
        if self.timeout_seconds is not None:
            solver.set(timeout=self.timeout_seconds * 1000)

        x_vars = [Int(f"x_{piece.id}") for piece in ordered_pieces]
        y_vars = [Int(f"y_{piece.id}") for piece in ordered_pieces]
        rot_vars = []
        widths: list[Any] = []
        heights: list[Any] = []

        for piece in ordered_pieces:
            can_rotate = self._piece_can_rotate(piece)
            rot = Bool(f"rot_{piece.id}") if can_rotate else None
            rot_vars.append(rot)
            if rot is None:
                widths.append(piece.width)
                heights.append(piece.height)
            else:
                widths.append(If(rot, piece.height, piece.width))
                heights.append(If(rot, piece.width, piece.height))

        boundary_constraints = 0
        for i, _piece in enumerate(ordered_pieces):
            solver.add(x_vars[i] >= 0)
            solver.add(y_vars[i] >= 0)
            solver.add(x_vars[i] + widths[i] <= self.container_width)
            solver.add(y_vars[i] + heights[i] <= self.container_height)
            boundary_constraints += 4

        non_overlap_constraints = 0
        for i in range(len(ordered_pieces)):
            for j in range(i + 1, len(ordered_pieces)):
                solver.add(
                    Or(
                        x_vars[i] + widths[i] <= x_vars[j],
                        x_vars[j] + widths[j] <= x_vars[i],
                        y_vars[i] + heights[i] <= y_vars[j],
                        y_vars[j] + heights[j] <= y_vars[i],
                    )
                )
                non_overlap_constraints += 1

        if self.symmetry_breaking and ordered_pieces:
            # Reflection symmetry lets the largest piece be placed in the lower-left half
            # without changing satisfiability.
            solver.add(2 * x_vars[0] + widths[0] <= self.container_width)
            solver.add(2 * y_vars[0] + heights[0] <= self.container_height)

        start = perf_counter()
        check_result = solver.check()
        elapsed = perf_counter() - start

        stats = PackingStats(
            num_pieces=len(ordered_pieces),
            num_variables=(2 * len(ordered_pieces)) + sum(rot is not None for rot in rot_vars),
            num_assertions=len(solver.assertions()),
            num_boundary_constraints=boundary_constraints,
            num_non_overlap_constraints=non_overlap_constraints,
            num_rotation_variables=sum(rot is not None for rot in rot_vars),
            total_piece_area=self.total_piece_area,
            container_area=self.container_area,
        )

        if check_result == sat:
            placements = PackingResult._extract_placements(solver.model(), ordered_pieces, x_vars, y_vars, rot_vars)
            result = PackingResult(self.name, self.mode, Status.SAT, tuple(placements), elapsed, stats)
            result.validate_result(self)
            return result
        if check_result == unsat:
            return PackingResult(self.name, self.mode, Status.UNSAT, (), elapsed, stats)
        return PackingResult(self.name, self.mode, Status.UNKNOWN, (), elapsed, stats, reason=str(check_result))

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

    @classmethod
    def _extract_placements(
        cls,
        model: ModelRef,
        pieces: tuple[Piece, ...],
        x_vars: list[Any],
        y_vars: list[Any],
        rot_vars: list[Any],
    ) -> list[Placement]:
        placements: list[Placement] = []
        for piece, x_var, y_var, rot_var in zip(pieces, x_vars, y_vars, rot_vars):
            rotated = bool(rot_var is not None and is_true(model.eval(rot_var, model_completion=True)))
            width = piece.height if rotated else piece.width
            height = piece.width if rotated else piece.height
            placements.append(
                Placement(
                    id=piece.id,
                    x=model.eval(x_var, model_completion=True).as_long(),
                    y=model.eval(y_var, model_completion=True).as_long(),
                    width=width,
                    height=height,
                    rotated=rotated,
                )
            )
        return placements


def solve_square_packing(container_size: int, square_sizes: list[int]) -> list[tuple[int, int]] | None:
    instance = PackingInstance.from_squares(container_size, square_sizes)
    result = instance.solve()

    if not result.is_sat:
        return None
    return [(placement.x, placement.y) for placement in result.placements]
