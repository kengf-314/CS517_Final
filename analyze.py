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
import matplotlib.pyplot as plt
import matplotlib.patches as mp

# Paths to input and output data
results_dir = Path("rand_tests")
analysis_dir = Path(results_dir / "analysis")
analysis_dir.mkdir(parents=True, exist_ok=True)
input_csv = Path(analysis_dir / "results.csv")
unknown_csv = Path("hard_cases.csv")

# Takes data category and returns a print ready string
def colloquialize(data):
    # Create a dict for colloquialization
    translate = {
        "all": "All Data",
        "limit": "Limit Cases",
        "squares": "Square Packing",
        "rectangles_rotation": "Rectangle Packing, Rotation Enabled",
        "rectangles_no_rotation": "Rectangle Packing, Rotation Disabled",
        "container_width": "Container Width",
        "container_height": "Container Height",
        "num_pieces": "Number of Pieces",
        "total_piece_area": "Total Piece Area",
        "container_area": "Container Area",
        "container_width_height_ratio": "Container Width Height Ratio",
        "density": "Density",
        "status": "Status",
        "SAT": "Satisfiable",
        "UNSAT": "Unsatisfiable",
        "UNKNOWN": "Unknown",
        "solver_time_seconds": "Runtime (S)",
        "rotation_variables": "Number of Rotations",
    }

    # Return colloquialized value if possible, otherwise returns input
    try:
        return translate[str(data)]
    except:
        return data

# Creates a graph title
def make_title(data_condition, x_var, y_var, color_condition, graph_type, prefix="", postfix=""):
    # Make variables title ready
    data_condition = colloquialize(data_condition)
    x_var = colloquialize(x_var)
    y_var = colloquialize(y_var)
    color_condition = colloquialize(color_condition)

    # Combine variables to form title
    return f"{prefix}{data_condition}: {x_var} vs {y_var}{postfix} {graph_type} Separated by {color_condition}"

# Take CSV data and create a dataframe
def load_data():
    # Initialize dataframe
    df = pd.read_csv(input_csv)

    # Set numbers
    df["density"] = pd.to_numeric(df["density"], errors="coerce")
    df["solver_time_seconds"] = pd.to_numeric(df["solver_time_seconds"], errors="coerce")

    return df

# Find the final satisfiable case for each set of test cases
def find_limits(df):
    # Initialize limit df
    new_df = []
    print("Finding final satisfiable cases")

    # Filter each seed
    for seed in df["seed"].unique():
        print(f"\tFinding limit case for seed {seed} / {len(df['seed'].unique())}")
        set = df[df["seed"] == seed]

        # Filter each mode
        for mode in df["mode"].unique():
            subset = set[set["mode"] == mode]

            # Filter for satisfiable cases
            subset = subset[subset["status"] == "SAT"]

            # Add new data point
            counter = 0
            for name in subset["name"]:
                # Check if this is the last satisfiable case in the test family
                if counter == len(subset) - 1:
                    # Find and append limit case
                    lim = subset[subset["name"] == name]
                    new_df.append(lim)

                counter += 1

    # Turn list into dataframe
    lim_df = pd.concat(new_df, ignore_index=True)
    return lim_df

# Create a scatter plot of two variables colored by a third var
def generate_graph(
    df,
    x_var,
    y_var="Count",
    x_scale="linear",
    y_scale="linear",
    category="status",
    colors=["#00FF0040", "#FF000040"],
    data_condition="all",
    graph_type="Scatterplot"
):
    # Make graph title
    graph_name = make_title(data_condition, x_var, y_var, category, graph_type)

    # Remove impossible cases (where piece area exceeds container area)
    df = df[df["density"] <= 1.0]
    groups = []
    labels = []

    # Create a scatter plot for the variables for the current category
    print(graph_name)
    plt.figure(figsize=(10, 10))
    plt.xscale(x_scale)
    plt.yscale(y_scale)
    
    counter = 0
    # Seperate data by category to be uniquely colored
    for current_category in sorted(df[category].unique()):
        subset = df[df[category] == current_category]

        # Add category data to scatter plot
        if graph_type == "Scatterplot":
            plt.scatter(
                x=subset[x_var],
                y=subset[y_var],
                label=colloquialize(current_category),
                c=colors[counter],
                edgecolors="none",
                rasterized=True,
            )

        # Add category data to box plot
        if graph_type == "Box Plot" or graph_type == "Violin Plot":
            subset = df[df[category] == current_category]
            groups.append(subset[y_var].dropna())
            labels.append(colloquialize(current_category))

        counter += 1

    if graph_type == "Box Plot":
        plt.boxplot(groups, tick_labels=labels)
    
    if graph_type == "Violin Plot":
        plt.violinplot(groups)
        plt.xticks(
            range(1, len(labels) + 1),
            labels,
        )
        plt.ylabel(f"{colloquialize(y_var)}")
    else:
        plt.xlabel(f"{colloquialize(x_var)}")
        plt.ylabel(f"{colloquialize(y_var)}")
        plt.legend()

    plt.title(graph_name)
    plt.tight_layout()

    # Save the graph
    plt.savefig(
        analysis_dir / f"{graph_name.replace(':', '')}.png",
        dpi=1000,
    )
    plt.close()

def generate_all_graphs(df, lim_df):
    print("Generating analysis graphs")

    # Density distributions
    generate_graph(
        df,
        x_var="status",
        y_var="density",
        y_scale="linear",
        category="status",
        data_condition="all",
        graph_type="Violin Plot",
    )
    generate_graph(
        lim_df,
        x_var="status",
        y_var="density",
        category="status",
        data_condition="limit",
        graph_type="Violin Plot",
    )

    # Runtime distributions
    generate_graph(
        df,
        x_var="status",
        y_var="solver_time_seconds",
        category="status",
        data_condition="all",
        y_scale="log",
        graph_type="Violin Plot",
    )
    generate_graph(
        df,
        x_var="num_pieces",
        y_var="solver_time_seconds",
        category="num_pieces",
        data_condition="all",
        y_scale="log",
        graph_type="Violin Plot",
    )

    # Runtime scatterplots
    generate_graph(
        df,
        x_var="density",
        y_var="solver_time_seconds",
        y_scale="log",
        category="status",
    )
    generate_graph(
        df,
        x_var="density",
        y_var="solver_time_seconds",
        y_scale="log",
        category="mode",
        colors=["#FFFF0040", "#FF00FF40", "#00FFFF40"],
    )
    generate_graph(
        df,
        x_var="density",
        y_var="solver_time_seconds",
        y_scale="log",
        category="num_pieces",
        colors=["#FFFF0040", "#FF808040", "#FF00FF40", "#8080FF40", "#00FFFF40", "#80FF8040"],
    )

    # Runtime vs pieces
    generate_graph(
        df,
        x_var="density",
        y_var="solver_time_seconds",
        y_scale="log",
        category="num_pieces",
        colors=["#FFFF0040", "#FF808040", "#FF00FF40", "#8080FF40", "#00FFFF40", "#80FF8040"],
    )
    generate_graph(
        df,
        x_var="num_pieces",
        y_var="solver_time_seconds",
        y_scale="log",
        category="num_pieces",
        graph_type="Box Plot",
    )

# Finds relationships between various aspects and runtime
def print_runtime_correlations(df):
    numeric_columns = [
        "container_width",
        "container_height",
        "num_pieces",
        "total_piece_area",
        "container_area",
        "container_width_height_ratio",
        "density",
    ]
    runtime = np.log10(
        df["solver_time_seconds"].clip(lower=1e-6)
    )
    results = []

    # Find correlations
    for column in numeric_columns:
        if column not in df.columns:
            continue

        corr = df[column].corr(runtime)
        results.append((column, corr))

    # Sort and print results
    results.sort(key=lambda x: abs(x[1]), reverse=True)
    print(f"{'Variable':35} {'Correlation':>12}")
    print("-" * 50)
    for name, corr in results:
        print(f"{name:35} {corr:12.4f}")

# Find cases where rotation changes satisfiability
def analyze_rotation_status_changes(lim_df):
    # Filter dataframe by mode
    rot = lim_df[lim_df["mode"] == "rectangles_rotation"]
    norot = lim_df[lim_df["mode"] == "rectangles_no_rotation"]
    merged = rot.merge(
        norot,
        on=["seed"],
        suffixes=("_rot", "_norot"),
    )

    gains = []

    counter = 0
    for i, row in merged.iterrows():
        # Find improvement
        gain = row["density_rot"] - row["density_norot"]
        gains.append(gain)
        if gain > 0:
            counter += 1

    # Print details
    print(f"Families analyzed: {len(merged)}")
    print(f"Improved cases: {counter}")
    print(f"No improvement: {len(merged) - counter}")
    print(f"Percent showing improvement: {100 * counter / len(merged):.2f}%")
    print(f"Average density gain: {np.mean(gains):.4f}")
    print(f"Maximum density gain: {max(gains):.4f}")

df = load_data()
lim_df = find_limits(df)
generate_all_graphs(df, lim_df)
print_runtime_correlations(lim_df)
analyze_rotation_status_changes(lim_df)