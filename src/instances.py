from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from .packing_solver import Mode, PackingInstance, Piece


def load_instance(path: str | Path) -> PackingInstance:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return instance_from_dict(data)


def save_instance(instance: PackingInstance, path: str | Path) -> None:
    Path(path).write_text(json.dumps(instance_to_dict(instance), indent=2), encoding="utf-8")


def instance_from_dict(data: dict[str, Any]) -> PackingInstance:
    container = data["container"]
    settings = data.get("settings", {})
    mode = Mode(data.get("mode", settings.get("mode", Mode.RECTANGLES_ROTATION)))
    pieces = tuple(
        Piece(
            id=str(piece.get("id", f"p{i}")),
            width=int(piece["width"]),
            height=int(piece["height"]),
            rotatable=bool(piece.get("rotatable", mode == Mode.RECTANGLES_ROTATION)),
        )
        for i, piece in enumerate(data["pieces"])
    )
    return PackingInstance(
        name=str(data.get("name", "json-instance")),
        container_width=int(container["width"]),
        container_height=int(container["height"]),
        pieces=pieces,
        mode=mode,
        timeout_seconds=settings.get("timeout_seconds", 10),
        symmetry_breaking=bool(settings.get("symmetry_breaking", True)),
    )


def instance_to_dict(instance: PackingInstance) -> dict[str, Any]:
    return {
        "name": instance.name,
        "mode": instance.mode,
        "container": {
            "width": instance.container_width,
            "height": instance.container_height,
        },
        "pieces": [
            {
                "id": piece.id,
                "width": piece.width,
                "height": piece.height,
                "rotatable": piece.rotatable,
            }
            for piece in instance.pieces
        ],
        "settings": {
            "timeout_seconds": instance.timeout_seconds,
            "symmetry_breaking": instance.symmetry_breaking,
        },
    }


def random_rectangles_instance(
    *,
    name: str,
    container_width: int,
    container_height: int,
    num_pieces: int,
    min_side: int = 1,
    max_side: int = 6,
    seed: int = 0,
    mode: Mode = Mode.RECTANGLES_ROTATION,
    rotatable: bool = True,
    timeout_seconds: int | None = 10,
    symmetry_breaking: bool = True,
) -> PackingInstance:
    rng = random.Random(seed)
    pieces = tuple(
        Piece(
            id=f"r{i}",
            width=rng.randint(min_side, max_side),
            height=rng.randint(min_side, max_side),
            rotatable=rotatable,
        )
        for i in range(num_pieces)
    )
    return PackingInstance(
        name=name,
        container_width=container_width,
        container_height=container_height,
        pieces=pieces,
        mode=mode,
        timeout_seconds=timeout_seconds,
        symmetry_breaking=symmetry_breaking,
    )


def rotation_witness_instance(*, allow_rotation: bool) -> PackingInstance:
    mode: Mode = Mode.RECTANGLES_ROTATION if allow_rotation else Mode.RECTANGLES_NO_ROTATION
    return PackingInstance(
        name=f"rotation-witness-{mode}",
        container_width=5,
        container_height=3,
        pieces=(
            Piece("a", 3, 2, allow_rotation),
            Piece("b", 3, 2, allow_rotation),
        ),
        mode=mode,
        timeout_seconds=10,
        symmetry_breaking=False,
    )
