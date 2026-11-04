import ast
import asyncio
import math
from pathlib import Path
from types import SimpleNamespace
import unittest

BASE=Path(__file__).resolve().parents[1]/"custom_components/xparkle_rvlevel"
ns={}
exec((BASE/"const.py").read_text(encoding="utf-8"),ns)
exec((BASE/"planner.py").read_text(encoding="utf-8"),ns)


class FlowBase:
    def async_show_form(self,**kw): return kw
    def async_create_entry(self,**kw): return kw


tree=ast.parse((BASE/"config_flow.py").read_text(encoding="utf-8"))
options=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="XparkleRVLevelOptionsFlow")
flow_ns={**ns,"config_entries":SimpleNamespace(OptionsFlow=FlowBase),
         "vol":SimpleNamespace(Required=lambda key,**kw:key,All=lambda *a:a,
             Coerce=lambda v:v,Range=lambda **kw:kw,In=lambda v:v,Schema=lambda d:d)}
exec(compile(ast.Module(body=[options],type_ignores=[]),"config_flow.py","exec"),flow_ns)


class TrackTests(unittest.TestCase):
    def test_legacy_single_width_and_checkbox(self):
        self.assertEqual(ns["track_widths"]({"transverse_width":1.81}),(1.81,1.81))
        self.assertEqual(ns["track_widths"]({"transverse_width":1.81,"rear_transverse_width":1.98,"equal_track_widths":True}),(1.81,1.81))
        self.assertEqual(ns["track_widths"]({"transverse_width":1.81,"rear_transverse_width":1.98,"equal_track_widths":False}),(1.81,1.98))

    def test_physical_heights_match_each_axle_width(self):
        heights=ns["corner_heights"](-.3,-3.7,4.332,1.81,1.98)
        slope=math.tan(math.radians(3.7))
        self.assertAlmostEqual(heights["front_left"]-heights["front_right"],181*slope)
        self.assertAlmostEqual(heights["rear_left"]-heights["rear_right"],198*slope)
        self.assertAlmostEqual((heights["front_left"]+heights["front_right"]-heights["rear_left"]-heights["rear_right"])/2,433.2*math.tan(math.radians(-.3)))

    def test_plan_residual_from_actual_wheel_coordinates(self):
        plan=ns["plan_wedges"](-.3,-3.7,4.332,1.81,[4,8,12,18],rear_width_m=1.98)
        x=[216.6,216.6,-216.6,-216.6]
        y=[-90.5,90.5,-99,99]
        h=list(plan["heights_cm"].values())
        pitch=math.tan(math.radians(-.3))+sum(a*b for a,b in zip(x,h))/sum(v*v for v in x)
        roll=math.tan(math.radians(-3.7))+sum(a*b for a,b in zip(y,h))/sum(v*v for v in y)
        self.assertAlmostEqual(plan["residual_longitudinal_angle"],math.degrees(math.atan(pitch)),delta=.00051)
        self.assertAlmostEqual(plan["residual_transverse_angle"],math.degrees(math.atan(roll)),delta=.00051)
        self.assertLessEqual(sum(v>0 for v in h),2)

    def test_options_profile_does_not_overwrite_widths(self):
        for custom in (False,True):
            for same in (False,True):
                flow=flow_ns["XparkleRVLevelOptionsFlow"]()
                flow.config_entry=SimpleNamespace(options={"transverse_width":1.74})
                flow._selection={"vehicle_manufacturer":"Benutzerdefiniert" if custom else "Ahorn Camp"}
                form=asyncio.run(flow.async_step_details())
                for field in ("transverse_width","equal_track_widths","rear_transverse_width"):
                    self.assertIn(field,form["data_schema"])
                inp={"transverse_width":1.81,"rear_transverse_width":1.98,"equal_track_widths":same,"wedge_profile":"milenco_quattro_2","sensor_orientation":"wall_right"}
                if custom: inp["longitudinal_length"]=4.332
                result=asyncio.run(flow.async_step_details(inp))["data"]
                self.assertEqual(result["transverse_width"],1.81)
                self.assertEqual(result["rear_transverse_width"],1.81 if same else 1.98)
                self.assertEqual(ns["track_widths"](result),(1.81,1.81 if same else 1.98))


if __name__=="__main__": unittest.main()
