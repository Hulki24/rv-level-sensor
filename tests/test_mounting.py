import ast
import importlib.util
import math
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "custom_components/xparkle_rvlevel"
namespace = {}
exec(compile((BASE / "const.py").read_text(encoding="utf-8"), "const.py", "exec"), namespace)
tree = ast.parse((BASE / "orientation.py").read_text(encoding="utf-8"))
tree.body = [node for node in tree.body if not isinstance(node, ast.ImportFrom)]
exec(compile(tree, "orientation.py", "exec"), namespace)
exec(compile((BASE / "planner.py").read_text(encoding="utf-8"), "planner.py", "exec"), namespace)
coordinator = ast.parse((BASE / "coordinator.py").read_text(encoding="utf-8"))
cls = next(node for node in coordinator.body if isinstance(node, ast.ClassDef) and node.name == "RVLevelCoordinator")
decode = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "_decode_fff2")
exec(compile(ast.Module(body=[decode], type_ignores=[]), "coordinator.py", "exec"), {**namespace, "math": math}, namespace)


class MountingTests(unittest.TestCase):
    def test_all_walls_and_tilt_directions_reach_vehicle_coordinates(self):
        # Independently synthesize local readings for an inward-facing sensor
        # rotated from the verified right-wall reference about the upright axis.
        for wall, rotation in [("wall_right", 0), ("wall_front", 90),
                               ("wall_left", 180), ("wall_rear", 270)]:
            for pitch, roll in [(2, 0), (-2, 0), (0, 1), (0, -1),
                                (2, 1), (-2, -1), (0, 0)]:
                theta = math.radians(rotation)
                raw_a = -pitch * math.cos(theta) + roll * math.sin(theta)
                raw_b = -pitch * math.sin(theta) - roll * math.cos(theta)
                with self.subTest(wall=wall, pitch=pitch, roll=roll):
                    a = round(raw_a * 100).to_bytes(2, "big", signed=True)
                    b = round(raw_b * 100).to_bytes(2, "big", signed=True)
                    obj = SimpleNamespace(
                        entry=SimpleNamespace(options={"sensor_orientation": wall}),
                        state=SimpleNamespace())
                    namespace["_decode_fff2"](obj, b"\x00" + a + b"\x00" + b + bytes([96]))
                    self.assertEqual(obj.state.longitudinal_angle, pitch)
                    self.assertEqual(obj.state.transverse_angle, roll)
                    # Theoretical lifts must retain their orientation independently of the plan.
                    long_cm = 433.2 * math.tan(math.radians(pitch))
                    trans_cm = 174 * math.tan(math.radians(roll))
                    expected = {
                        "front_left": max(0, -long_cm) + max(0, trans_cm),
                        "front_right": max(0, -long_cm) + max(0, -trans_cm),
                        "rear_left": max(0, long_cm) + max(0, trans_cm),
                        "rear_right": max(0, long_cm) + max(0, -trans_cm),
                    }
                    for corner, lift in expected.items():
                        self.assertAlmostEqual(getattr(obj.state, corner + "_lift_cm"), lift, delta=.11)

                    self.assertLessEqual(sum(v > 0 for v in obj.state.wedge_plan["heights_cm"].values()), 2)

    def test_legacy_options_preserve_behavior(self):
        fn = namespace["vehicle_angles"]
        self.assertEqual(fn(2, -1, "normal"), (2, -1))
        self.assertEqual(fn(2, -1, "rotated_180"), (-2, 1))

    def test_unknown_mount_rejected(self):
        with self.assertRaises(ValueError):
            namespace["vehicle_angles"](1, 2, "unknown")


if __name__ == "__main__":
    unittest.main()
