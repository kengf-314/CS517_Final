from __future__ import annotations

import csv
import random
from pathlib import Path
import math

from src.packing_solver import (
    Piece,
    PackingInstance,
    solve_packing,
)

from src.visualize import plot_result, plot_result_grid

# Paths to store results and visualizations
results_dir = Path("rand_tests")
results_dir.mkdir(parents=True, exist_ok=True)
figure_dir = Path("figures")
figure_dir.mkdir(parents=True, exist_ok=True)
grid_path = Path("grids")
grid_path.mkdir(parents=True, exist_ok=True)
results_csv = "random_results.csv"

# Write the header row for the CSV results file
def write_csv_header(results_dir=results_dir, results_csv=results_csv):
    with (results_dir / results_csv).open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
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
        ])

# Write a row of results for a given instance and result to the CSV file
def write_result_row(instance, result, results_dir=results_dir, results_csv=results_csv):
    # Calculate density of pieces in the container
    density = (
        instance.total_piece_area /
        instance.container_area
    )

    # Write a row of results to the CSV file
    with (results_dir / results_csv).open("a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
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
        ])


# Generate a random set of square pieces
def generate_square_family(seed: int) -> tuple[str, tuple[Piece, ...]]:
    # Seed rng and randomize number of squares
    rng = random.Random(seed)
    num_squares = rng.randint(10, 15)
    rand_sizes = [rng.randint(1, 10) for i in range(num_squares)]

    # Create individual pieces
    pieces = tuple(
        Piece(
            # Name piece and randomize size
            id=f"s{i}",
            width=rand_sizes[i],
            height=rand_sizes[i],
            rotatable=False,
        )
        for i in range(num_squares)
    )

    # Return square family name and pieces
    return f"square_family_{seed}", pieces

# Generate a random set of rectangular pieces
def generate_rectangle_family(seed: int, rotatable: bool) -> tuple[str, tuple[Piece, ...]]:
    # Seed rng and randomize number of rectangles
    rng = random.Random(seed)
    num_rects = rng.randint(10, 15)

    # Create individual pieces
    pieces = tuple(
        Piece(
            # Name piece and randomize side lengths
            id=f"r{i}",
            width=rng.randint(1, 10),
            height=rng.randint(1, 10),
            rotatable=rotatable,
        )
        for i in range(num_rects)
    )

    # Return rectangle family name and pieces
    return f"rectangle_family_{seed}", pieces

# Generate a set of square containers from 30x30 down to 5x5
def generate_square_containers():
    return [(i, i) for i in range(30, 4, -1)]

# Generate a set of rectangular containers [X]x[Y], [X-1]x[Y-1], ..., ([5]x[Y-n] or [X-n]x[5])
def generate_rectangle_containers(seed: int):
    # Seed rng and randomize initial container size
    rng = random.Random(seed)
    width = rng.randint(25, 35)
    height = rng.randint(25, 35)

    # Generate containers by decrementing width and height until one or both sides are 5
    containers = []
    while width >= 5 and height >= 5:
        containers.append((width, height))
        width -= 1
        height -= 1

    return containers

# Generate a set of square packing instances by combining square containers with square pieces
def generate_square_containers_square_pieces_instances(seed: int):
    instances = []

    # Generate containers and pieces
    square_containers = generate_square_containers()
    squares = generate_square_family(seed)[1]

    # Square pieces in square container
    for container_width, container_height in square_containers:
        instances.append(
            PackingInstance(
                name=f"seed_{seed}_square_pieces_square_container_{container_width}x{container_height}",
                mode="squares",
                container_width=container_width,
                container_height=container_height,
                pieces=squares,
            )
        )
    
    return instances

# Generate a set of square packing instances by combining rectangular containers with square pieces
def generate_rectangle_containers_square_pieces_instances(seed: int):
    instances = []

    # Generate containers and pieces
    rectangle_containers = generate_rectangle_containers(seed)
    squares = generate_square_family(seed)[1]

    # Square pieces in rectangle container
    for container_width, container_height in rectangle_containers:
        instances.append(
            PackingInstance(
                name=f"seed_{seed}_square_pieces_rectangle_container_{container_width}x{container_height}",
                mode="squares",
                container_width=container_width,
                container_height=container_height,
                pieces=squares,
            )
        )

    return instances

# Generate a set of rectangle packing instances by combining square containers with rectangular pieces
def generate_square_containers_rectangle_pieces_instances(seed: int):
    instances = []

    # Generate containers and pieces
    square_containers = generate_square_containers()
    rectangles_no_rotation = generate_rectangle_family(seed, rotatable=False)[1]
    rectangles_rotation = generate_rectangle_family(seed, rotatable=True)[1]

    # Rectangle pieces in square container
    for container_width, container_height in square_containers:
        # No rotation
        instances.append(
            PackingInstance(
                name=f"seed_{seed}_rectangle_pieces_square_container_{container_width}x{container_height}_no_rotation",
                mode="rectangles_no_rotation",
                container_width=container_width,
                container_height=container_height,
                pieces=rectangles_no_rotation,
            )
        )

        # With rotation
        instances.append(
            PackingInstance(
                name=f"seed_{seed}_rectangle_pieces_square_container_{container_width}x{container_height}_rotation",
                mode="rectangles_rotation",
                container_width=container_width,
                container_height=container_height,
                pieces=rectangles_rotation,
            )
        )
    
    return instances

# Generate a set of rectangle packing instances by combining rectangular containers with rectangular pieces
def generate_rectangle_containers_rectangle_pieces_instances(seed: int):
    instances = []

    # Generate containers and pieces
    rectangle_containers = generate_rectangle_containers(seed)
    rectangles_no_rotation = generate_rectangle_family(seed, rotatable=False)[1]
    rectangles_rotation = generate_rectangle_family(seed, rotatable=True)[1]

    # Rectangle pieces no rotation in rectangle container
    for container_width, container_height in rectangle_containers:
        # No rotation
        instances.append(
            PackingInstance(
                name=f"seed_{seed}_rectangle_pieces_rectangle_container_{container_width}x{container_height}_no_rotation",
                mode="rectangles_no_rotation",
                container_width=container_width,
                container_height=container_height,
                pieces=rectangles_no_rotation,
            )
        )

        # With rotation
        instances.append(
            PackingInstance(
                name=f"seed_{seed}_rectangle_pieces_rectangle_container_{container_width}x{container_height}_rotation",
                mode="rectangles_rotation",
                container_width=container_width,
                container_height=container_height,
                pieces=rectangles_rotation,
            )
        )

    return instances

# Solve each instance in a family, write results to CSV, and generate visualizations
def run_family(instances, file):
    entries = []
    
    # Solve each instance, write results, and generate visualizations
    counter = 0
    for instance in instances:
        counter += 1
        print(f"\t\tSolving instance {counter} / {len(instances)}")
        # Solve individual instance
        result = solve_packing(instance)

        # Write results to CSV
        write_result_row(
            instance,
            result,
        )

        # Generate visualization for instance
        plot_result(
            instance,
            result,
            results_dir / figure_dir / f"{instance.name}.png",
        )

        # Add entry for grid visualization
        entries.append(
            (instance, result)
        )

    # Generate grid visualization for family
    plot_result_grid(
        entries,
        results_dir / grid_path / file,
        columns=math.ceil(math.sqrt(len(instances)) / 2) * 2,
    )

if __name__ == "__main__":
    write_csv_header()

    for i in range(1, 1001):
        print(f"Running Seed {i} / 1000")
        print(f"\tSquare Pieces, Square Containers, Family {(i - 1) * 4 + 1} / 4000")
        run_family(generate_square_containers_square_pieces_instances(i), f"seed_{i}_square_pieces_square_containers.png")
        print(f"\tSquare Pieces, Rectangle Containers, Family {(i - 1) * 4 + 2} / 4000")
        run_family(generate_rectangle_containers_square_pieces_instances(i), f"seed_{i}_square_pieces_rectangle_containers.png")
        print(f"\tRectangle Pieces, Square Containers, Family {(i - 1) * 4 + 3} / 4000")
        run_family(generate_square_containers_rectangle_pieces_instances(i), f"seed_{i}_rectangle_pieces_square_containers.png")
        print(f"\tRectangle Pieces, Rectangle Containers, Family {(i - 1) * 4 + 4} / 4000")
        run_family(generate_rectangle_containers_rectangle_pieces_instances(i), f"seed_{i}_rectangle_pieces_rectangle_containers.png")