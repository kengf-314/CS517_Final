from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .instances import random_rectangles_instance, rotation_witness_instance
from .packing_solver import PackingInstance, PackingResult, Piece, solve_packing, squares_instance
from .visualize import plot_result, plot_result_grid


def final_preset() -> list[PackingInstance]:
    instances: list[PackingInstance] = []

    square_sizes = [5, 4, 3, 3, 3, 2, 2, 2, 2, 1, 1, 1, 1]
    for side in [30, 25, 20, 15, 12, 11, 10, 9]:
        instances.append(
            squares_instance(
                side,
                square_sizes,
                name=f"squares-L{side}",
                timeout_seconds=10,
                symmetry_breaking=True,
            )
        )

    base_rectangles = (
        Piece("r0", 6, 4, True),
        Piece("r1", 5, 3, True),
        Piece("r2", 4, 4, True),
        Piece("r3", 3, 7, True),
        Piece("r4", 2, 8, True),
        Piece("r5", 5, 2, True),
        Piece("r6", 3, 3, True),
        Piece("r7", 2, 4, True),
    )
    for count in [4, 5, 6, 7, 8]:
        for mode in ["rectangles_no_rotation", "rectangles_rotation"]:
            instances.append(
                PackingInstance(
                    name=f"{mode}-n{count}",
                    container_width=12,
                    container_height=10,
                    pieces=base_rectangles[:count],
                    mode=mode,
                    timeout_seconds=10,
                    symmetry_breaking=True,
                )
            )

    instances.append(rotation_witness_instance(allow_rotation=False))
    instances.append(rotation_witness_instance(allow_rotation=True))

    for count in [6, 8, 10, 12, 14]:
        instances.append(
            random_rectangles_instance(
                name=f"random-density-n{count}",
                container_width=15,
                container_height=12,
                num_pieces=count,
                min_side=2,
                max_side=6,
                seed=517 + count,
                mode="rectangles_rotation",
                timeout_seconds=10,
                symmetry_breaking=True,
            )
        )

    return instances


def run_instances(instances: list[PackingInstance], output_dir: Path) -> list[tuple[PackingInstance, PackingResult]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    image_dir = output_dir / "figures"
    rows: list[tuple[PackingInstance, PackingResult]] = []
    for instance in instances:
        print(f"Running {instance.name} ({instance.mode})")
        result = solve_packing(instance)
        rows.append((instance, result))
        plot_result(instance, result, image_dir / f"{instance.name}.png")
        print(
            f"  {result.status} in {result.solver_time_seconds:.4f}s, "
            f"vars={result.stats.num_variables}, assertions={result.stats.num_assertions}"
        )
    plot_result_grid(rows[:8], output_dir / "square_baseline_grid.png")
    plot_result_grid(rows[8:20], output_dir / "rectangle_experiments_grid.png", columns=3)
    write_csv(rows, output_dir / "summary.csv")
    return rows


def write_csv(rows: list[tuple[PackingInstance, PackingResult]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "name",
                "mode",
                "container_width",
                "container_height",
                "num_pieces",
                "total_piece_area",
                "container_area",
                "density",
                "status",
                "solver_time_seconds",
                "variables",
                "assertions",
                "boundary_constraints",
                "non_overlap_constraints",
                "rotation_variables",
                "reason",
            ]
        )
        for instance, result in rows:
            density = instance.total_piece_area / instance.container_area
            writer.writerow(
                [
                    instance.name,
                    instance.mode,
                    instance.container_width,
                    instance.container_height,
                    result.stats.num_pieces,
                    result.stats.total_piece_area,
                    result.stats.container_area,
                    f"{density:.4f}",
                    result.status,
                    f"{result.solver_time_seconds:.6f}",
                    result.stats.num_variables,
                    result.stats.num_assertions,
                    result.stats.num_boundary_constraints,
                    result.stats.num_non_overlap_constraints,
                    result.stats.num_rotation_variables,
                    result.reason,
                ]
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CS517 packing experiments.")
    parser.add_argument("--preset", choices=["final"], default="final")
    parser.add_argument("--output-dir", default="results")
    args = parser.parse_args()

    if args.preset != "final":
        raise ValueError(f"Unknown preset: {args.preset}")
    run_instances(final_preset(), Path(args.output_dir))


if __name__ == "__main__":
    main()

