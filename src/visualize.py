from __future__ import annotations

from pathlib import Path

from .packing_solver import PackingInstance, PackingResult


def plot_result(instance: PackingInstance, result: PackingResult, output_path: str | Path) -> None:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(7, 7))
    _draw_result(ax, instance, result)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def plot_result_grid(
    entries: list[tuple[PackingInstance, PackingResult]],
    output_path: str | Path,
    *,
    columns: int = 4,
) -> None:
    import math
    import matplotlib.pyplot as plt

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = math.ceil(len(entries) / columns)
    fig, axes = plt.subplots(rows, columns, figsize=(4 * columns, 4 * rows))
    flat_axes = list(axes.flatten()) if hasattr(axes, "flatten") else [axes]

    for ax, (instance, result) in zip(flat_axes, entries):
        _draw_result(ax, instance, result)
    for ax in flat_axes[len(entries):]:
        ax.axis("off")

    fig.tight_layout()
    fig.savefig(output_path, dpi=300)
    plt.close(fig)


def _draw_result(ax, instance: PackingInstance, result: PackingResult) -> None:
    import matplotlib.patches as patches

    ax.add_patch(
        patches.Rectangle(
            (0, 0),
            instance.container_width,
            instance.container_height,
            fill=False,
            edgecolor="black",
            linewidth=2,
        )
    )
    if result.status == "SAT":
        colors = _palette()
        for i, placement in enumerate(result.placements):
            ax.add_patch(
                patches.Rectangle(
                    (placement.x, placement.y),
                    placement.width,
                    placement.height,
                    facecolor=colors[i % len(colors)],
                    edgecolor="black",
                    alpha=0.9,
                )
            )
            label = placement.id
            if placement.rotated:
                label += " R"
            ax.text(
                placement.x + placement.width / 2,
                placement.y + placement.height / 2,
                label,
                ha="center",
                va="center",
                fontsize=7,
            )
    else:
        ax.text(
            instance.container_width / 2,
            instance.container_height / 2,
            result.status,
            ha="center",
            va="center",
            color="red",
            fontsize=12,
            fontweight="bold",
        )

    ax.set_title(
        f"{instance.name}\n{result.status}, {result.solver_time_seconds:.3f}s",
        fontsize=9,
    )
    ax.set_xlim(-1, instance.container_width + 1)
    ax.set_ylim(-1, instance.container_height + 1)
    ax.set_aspect("equal")
    ax.set_xticks(range(0, instance.container_width + 1, max(1, instance.container_width // 5)))
    ax.set_yticks(range(0, instance.container_height + 1, max(1, instance.container_height // 5)))
    ax.grid(True, linestyle="--", alpha=0.35)


def _palette() -> list[str]:
    return [
        "#8dd3c7",
        "#ffffb3",
        "#bebada",
        "#fb8072",
        "#80b1d3",
        "#fdb462",
        "#b3de69",
        "#fccde5",
        "#d9d9d9",
        "#bc80bd",
        "#ccebc5",
        "#ffed6f",
    ]
