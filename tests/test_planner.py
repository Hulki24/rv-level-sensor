import importlib.util
import itertools
import math
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("planner", Path(__file__).resolve().parents[1] / "custom_components/xparkle_rvlevel/planner.py")
planner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(planner)


class PlannerTests(unittest.TestCase):
    def test_exact_side_and_axle_corrections(self):
        for angle, expected in [
            ((0, -math.degrees(math.atan(12/174))), (0, 12, 0, 12)),
            ((0, math.degrees(math.atan(12/174))), (12, 0, 12, 0)),
            ((-math.degrees(math.atan(8/433.2)), 0), (8, 8, 0, 0)),
            ((math.degrees(math.atan(8/433.2)), 0), (0, 0, 8, 8)),
        ]:
            plan=planner.plan_wedges(*angle, 4.332, 1.74, [4,8,12,16])
            self.assertEqual(tuple(plan["heights_cm"].values()), expected)
            self.assertEqual(plan["residual_total_angle"], 0)

    def test_user_right_low_case(self):
        plan=planner.plan_wedges(-.23,-3.70,3.735,2.04,[4,8,12,16])
        self.assertEqual(plan["heights_cm"], dict(zip(planner.CORNERS,[0,16,0,12])))
        self.assertLess(plan["residual_total_angle"], .3)

    def test_level_and_below_smallest_useful_step(self):
        for angle in [(0,0),(.01,-.01),(.05,0)]:
            plan=planner.plan_wedges(*angle,4.332,1.74,[4,8,12])
            self.assertFalse(any(plan["heights_cm"].values()))

    def test_global_minimum_against_full_cartesian_search(self):
        # Independent exhaustive reference includes zero at every wheel;
        # production instead enumerates wheel subsets.
        stages=[4,8,12,16]
        for pitch,roll in itertools.product([-5,-1,0,1,5],repeat=2):
            plan=planner.plan_wedges(pitch,roll,4.332,1.74,stages)
            chosen=list(plan["heights_cm"].values())
            def score(h):
                fl,fr,rl,rr=h
                p=math.atan(math.tan(math.radians(pitch))+(fl+fr-rl-rr)/866.4)
                q=math.atan(math.tan(math.radians(roll))+(fr+rr-fl-rl)/348)
                return p*p+q*q
            reference=min(score(h) for h in itertools.product([0]+stages,repeat=4)
                          if sum(v>0 for v in h)<=2)
            self.assertAlmostEqual(score(chosen),reference,places=10)
            self.assertLessEqual(sum(v>0 for v in chosen),2)
            self.assertTrue(set(chosen)<=set([0]+stages))
            self.assertLessEqual(score(chosen),score([0]*4)+1e-12)

    def test_insufficient_height_leaves_visible_residual(self):
        plan=planner.plan_wedges(0,-10,4.332,1.74,[4,8,12])
        self.assertEqual(tuple(plan["heights_cm"].values()),(0,12,0,12))
        self.assertGreater(plan["residual_total_angle"],5)

    def test_invalid_inputs(self):
        for args in [(float("nan"),0,4,2,[4]),(0,0,0,2,[4]),
                     (0,0,4,2,[]),(0,0,4,2,[0]),(0,0,4,2,[float("inf")])]:
            with self.assertRaises(ValueError):
                planner.plan_wedges(*args)


if __name__=="__main__":
    unittest.main()
