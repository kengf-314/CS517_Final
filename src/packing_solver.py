from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any, Literal

try:
    from z3 import Bool, If, Int, ModelRef, Or, Solver, is_true, sat, unsat
except ModuleNotFoundError as exc:  # pragma: no cover - exercised only without deps
    Bool = If = Int = ModelRef = Or = Solver = is_true = sat = unsat = None
    Z3_IMPORT_ERROR = exc
else:
    Z3_IMPORT_ERROR = None


Mode = Literal["squares", "rectangles_no_rotation", "rectangles_rotation"]
Status = Literal["SAT", "UNSAT", "UNKNOWN"]


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


@dataclass(frozen=True)
class PackingInstance:
    name: str
    container_width: int
    container_height: int
    pieces: tuple[Piece, ...]
    mode: Mode = "rectangles_rotation"
    timeout_seconds: int | None = 10
    symmetry_breaking: bool = True

    def __post_init__(self) -> None:
        if self.container_width <= 0 or self.container_height <= 0:
            raise ValueError("Container dimensions must be positive")
        if self.mode not in {"squares", "rectangles_no_rotation", "rectangles_rotation"}:
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
            if self.mode == "squares" and not piece.is_square:
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
            mode="squares",
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
                status="UNSAT",
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
            result = PackingResult(self.name, self.mode, "SAT", tuple(placements), elapsed, stats)
            result.validate_result(self)
            return result
        if check_result == unsat:
            return PackingResult(self.name, self.mode, "UNSAT", (), elapsed, stats)
        return PackingResult(self.name, self.mode, "UNKNOWN", (), elapsed, stats, reason=str(check_result))

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
        return self.mode == "rectangles_rotation" and piece.rotatable and not piece.is_square


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
        return self.status == "SAT"

    def validate_result(self, instance: PackingInstance) -> None:
        if self.status != "SAT":
            return
        by_id = {piece.id: piece for piece in instance.pieces}
        for placement in self.placements:
            if placement.id not in by_id:
                raise ValueError(f"Unknown placement id {placement.id}")
            if placement.x < 0 or placement.y < 0:
                raise ValueError(f"Piece {placement.id} has a negative coordinate")
            if placement.x + placement.width > instance.container_width:
                raise ValueError(f"Piece {placement.id} exceeds container width")
            if placement.y + placement.height > instance.container_height:
                raise ValueError(f"Piece {placement.id} exceeds container height")

        for i, a in enumerate(self.placements):
            for b in self.placements[i + 1:]:
                separated = (
                    a.x + a.width <= b.x
                    or b.x + b.width <= a.x
                    or a.y + a.height <= b.y
                    or b.y + b.height <= a.y
                )
                if not separated:
                    raise ValueError(f"Pieces {a.id} and {b.id} overlap")

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
