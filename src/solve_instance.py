from __future__ import annotations

import argparse
import json
from pathlib import Path

from .instances import load_instance
from .packing_solver import solve_packing
from .visualize import plot_result


def main() -> None:
    parser = argparse.ArgumentParser(description="Solve one packing instance from JSON.")
    parser.add_argument("input", help="Path to a JSON instance file")
    parser.add_argument("--image", help="Optional PNG output path")
    args = parser.parse_args()

    instance = load_instance(args.input)
    result = solve_packing(instance)
    print(
        json.dumps(
            {
                "name": result.instance_name,
                "mode": result.mode,
                "status": result.status,
                "solver_time_seconds": result.solver_time_seconds,
                "placements": [placement.__dict__ for placement in result.placements],
                "stats": result.stats.__dict__,
                "reason": result.reason,
            },
            indent=2,
        )
    )
    if args.image:
        plot_result(instance, result, Path(args.image))


if __name__ == "__main__":
    main()
