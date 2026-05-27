from __future__ import annotations

import unittest

from src.instances import instance_from_dict, rotation_witness_instance
from src.packing_solver import PackingInstance, Piece, solve_packing, squares_instance, validate_result


def z3_available() -> bool:
    try:
        import z3  # noqa: F401
    except ModuleNotFoundError:
        return False
    return True


@unittest.skipUnless(z3_available(), "z3-solver is not installed")
class PackingSolverTests(unittest.TestCase):
    def test_single_square_is_sat(self) -> None:
        result = solve_packing(squares_instance(5, [3], symmetry_breaking=False))
        self.assertEqual(result.status, "SAT")
        self.assertEqual(len(result.placements), 1)

    def test_area_bound_unsat(self) -> None:
        result = solve_packing(squares_instance(3, [3, 2], symmetry_breaking=False))
        self.assertEqual(result.status, "UNSAT")
        self.assertEqual(result.reason, "area lower bound")

    def test_two_large_rectangles_cannot_fit(self) -> None:
        instance = PackingInstance(
            name="two-large",
            container_width=5,
            container_height=5,
            pieces=(Piece("a", 4, 4), Piece("b", 4, 4)),
            mode="rectangles_no_rotation",
            symmetry_breaking=False,
        )
        result = solve_packing(instance)
        self.assertEqual(result.status, "UNSAT")

    def test_rotation_changes_feasibility(self) -> None:
        without_rotation = solve_packing(rotation_witness_instance(allow_rotation=False))
        with_rotation = solve_packing(rotation_witness_instance(allow_rotation=True))
        self.assertEqual(without_rotation.status, "UNSAT")
        self.assertEqual(with_rotation.status, "SAT")
        self.assertTrue(any(placement.rotated for placement in with_rotation.placements))

    def test_json_instance_round_trip_shape(self) -> None:
        instance = instance_from_dict(
            {
                "name": "json-smoke",
                "mode": "rectangles_rotation",
                "container": {"width": 6, "height": 4},
                "pieces": [
                    {"id": "a", "width": 4, "height": 2, "rotatable": True},
                    {"id": "b", "width": 2, "height": 2, "rotatable": True},
                ],
                "settings": {"timeout_seconds": 5, "symmetry_breaking": False},
            }
        )
        result = solve_packing(instance)
        self.assertEqual(result.status, "SAT")
        validate_result(instance, result)


if __name__ == "__main__":
    unittest.main()

