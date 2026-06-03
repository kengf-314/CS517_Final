import random
from .packing_solver import Piece, Placement


def generate_cut_placements(width: int, height: int, probability: float = 0.5, seed: int | None = None) -> tuple[Placement, ...]:
    if seed is not None:
        random.seed(seed)
    placements: list[Placement] = []

    def cut_recursive(current_width: int, current_height: int, offset_x: int, offset_y: int, cut_horizontal: bool, force_cut: bool = False) -> None:
        if not force_cut and random.random() >= probability:
            placements.append(Placement(id=f"r{len(placements)}", x=offset_x, y=offset_y, width=current_width, height=current_height, rotated=False))
            return
        if cut_horizontal:
            if current_width > 1:
                cut_point = random.randint(1, current_width - 1)
                cut_recursive(cut_point, current_height, offset_x, offset_y, False)
                cut_recursive(current_width - cut_point, current_height, offset_x + cut_point, offset_y, False)
            else:
                cut_recursive(current_width, current_height, offset_x, offset_y, False, force_cut)
        else:
            if current_height > 1:
                cut_point = random.randint(1, current_height - 1)
                cut_recursive(current_width, cut_point, offset_x, offset_y, True)
                cut_recursive(current_width, current_height - cut_point, offset_x, offset_y + cut_point, True)
            else:
                cut_recursive(current_width, current_height, offset_x, offset_y, True, force_cut)

    cut_recursive(width, height, 0, 0, True, force_cut=True)
    return tuple(placements)


def shuffle_placements(placements: tuple[Placement, ...], seed: int | None = None) -> tuple[Piece, ...]:
    if seed is not None:
        random.seed(seed)
    pieces: list[Piece] = []
    for placement in placements:
        width, height = max(placement.width, placement.height), min(placement.width, placement.height)
        pieces.append(Piece(id=placement.id, width=width, height=height, rotatable=True))
    pieces.sort(key=lambda piece: (-piece.width, piece.id))
    return tuple(pieces)


if __name__ == "__main__":
    import pickle
    from pathlib import Path
    from .experiments import write_csv
    from .packing_solver import Mode, PackingInstance, PackingResult, Status
    from .visualize import plot_result, plot_result_grid

    MAX_SEED = 12
    WIDTH = 10
    HEIGHT = 8
    TIMEOUT_SECOND = 10

    cases: list[tuple[PackingInstance, PackingResult, tuple[Placement, ...]]] = []

    start_seed = 0
    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)

    existing_pickle_files = list(results_dir.glob(f"{WIDTH}x{HEIGHT}_{TIMEOUT_SECOND}s_*.pkl"))
    if existing_pickle_files:
        latest_file = max(
            existing_pickle_files,
            key=lambda path: int(path.stem.split("_")[-1]),
        )
        start_seed = int(latest_file.stem.split("_")[-1]) + 1
        with latest_file.open("rb") as handle:
            cases = pickle.load(handle)

    for seed in range(start_seed, MAX_SEED):
        print(f"{seed}: ", end="")

        placements = generate_cut_placements(WIDTH, HEIGHT, 0.75, seed)
        pieces = shuffle_placements(placements)
        instance = PackingInstance(
            name=f"{seed}",
            container_width=WIDTH,
            container_height=HEIGHT,
            pieces=pieces,
            mode=Mode.RECTANGLES_ROTATION,
            timeout_seconds=TIMEOUT_SECOND,
            symmetry_breaking=True,
        )
        result = instance.solve()
        print(f"{result.solver_time_seconds} sec")

        cases.append((instance, result, placements))

        current_pickle = results_dir / f"{WIDTH}x{HEIGHT}_{TIMEOUT_SECOND}s_{seed}.pkl"
        with current_pickle.open("wb") as handle:
            pickle.dump(cases, handle)

        previous_pickle = results_dir / f"{WIDTH}x{HEIGHT}_{TIMEOUT_SECOND}s_{seed - 1}.pkl"
        if previous_pickle.exists():
            previous_pickle.unlink()

    original_format_cases = [(instance, result) for instance, result, placements in cases]
    write_csv(original_format_cases, results_dir / f"{WIDTH}x{HEIGHT}_{TIMEOUT_SECOND}s_{MAX_SEED}.csv")

    new_cases: list[tuple[PackingInstance, PackingResult]] = []
    for instance, result, placements in cases[start_seed:start_seed+12]:
        if result.status != Status.SAT:
            new_result = PackingResult(
                result.instance_name,
                result.mode,
                result.status,
                placements,
                0,
                result.stats,
                result.reason,
            )
            new_cases.append((instance, new_result))
        else:
            new_cases.append((instance, result))

    plot_result_grid(new_cases, f"{results_dir}/figures/{WIDTH}x{HEIGHT}_{TIMEOUT_SECOND}s_{start_seed}-{start_seed+len(new_cases)}.png")
