from __future__ import annotations

import numpy as np
import math
import re
from pathlib import Path

from random_experiments import (
    generate_square_family,
    generate_rectangle_family,
    write_csv_header,
    write_result_row,
)
from src.packing_solver import (
    PackingInstance,
    solve_packing,
)
from src.visualize import plot_result
import pandas as pd

results_dir = Path("rand_tests")
results_csv = Path(results_dir / "random_results.csv")
analysis_dir = Path(results_dir / "analysis")
analysis_dir.mkdir(parents=True, exist_ok=True)
hard_cases_csv = Path(analysis_dir / "hard_cases.csv")
new_results_csv = Path(analysis_dir / "results.csv")

# Find the random number seed from the instance name
def extract_seed(df):
    df["seed"] = df["name"].str.extract(r"seed_(\d+)")
    return df

# Take CSV data and create a dataframe
def load_data(csv):
    # Initialize dataframe
    df = pd.read_csv(csv)

    # Set numbers
    df["density"] = pd.to_numeric(df["density"], errors="coerce")
    df["solver_time_seconds"] = pd.to_numeric(df["solver_time_seconds"],errors="coerce")

    # Find seeds for df cases
    df = extract_seed(df)

    # Find ratio of container width and height
    df["container_width_height_ratio"] = df["container_width"] / df["container_height"]

    return df

# Uses seed to recreate unsolved cases
def rebuild_instance(instance):
    # Generate pieces based on mode
    if instance["mode"] == "squares":
        pieces = generate_square_family(int(instance["seed"]))[1]
    elif instance["mode"] == "rectangles_rotation":
        pieces = generate_rectangle_family(int(instance["seed"]), True)[1]
    else:
        pieces = generate_rectangle_family(int(instance["seed"]), False)[1]

    return PackingInstance(
        name=instance["name"],
        mode=instance["mode"],
        container_width=instance["container_width"],
        container_height=instance["container_height"],
        pieces=pieces,
        timeout_seconds=None,
    )

def test_unknown(df):
    # Filter for unsolved cases
    subset = df[df["status"] == "UNKNOWN"]
    
    # Set up csv for hard cases
    write_csv_header(results_csv=hard_cases_csv)

    # Retry cases
    counter = 0
    for row in subset.iterrows():
        instance = row[1]
        print(f"Retrying unsolved case {counter + 1} / {len(subset)}")
        inst = rebuild_instance(instance)

        result = solve_packing(inst)

        # Write results
        write_result_row(inst, result, results_csv=hard_cases_csv)
        
        # Plot results
        plot_result(
            instance,
            result,
            analysis_dir / "hard_cases" / f"{instance['name']}.png",
        )
        counter += 1

df = load_data(results_csv)
# test_unknown(df)
hard_cases_df = load_data(hard_cases_csv)

# Align the datasets on the "name" column
df = df.set_index("name")
hard_cases_df = hard_cases_df.set_index("name")

# Overwrite the matching rows in df
df.update(hard_cases_df)

# Restore "name" as a regular column
df = df.reset_index()
hard_cases_df = hard_cases_df.reset_index()

# Write new data to a csv
df.to_csv(new_results_csv, index=False)