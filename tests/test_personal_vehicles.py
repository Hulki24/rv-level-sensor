import asyncio
from copy import deepcopy
from types import SimpleNamespace
import unittest
from test_tracks import ns, flow_ns


def flow(options):
    f=flow_ns["XparkleRVLevelOptionsFlow"]()
    f.config_entry=SimpleNamespace(options=deepcopy(options))
    f._selection={"vehicle_manufacturer":"Benutzerdefiniert"}
    return f


def values(name, length, front, rear, top="", side=""):
    return {
        "vehicle_name":name,"longitudinal_length":length,
        "transverse_width":front,"rear_transverse_width":rear,"equal_track_widths":False,
        "top_image":top,"side_image":side,"body_length_m":7.5,"body_width_m":2.3,"body_height_m":3.1,
        "wedge_profile":"milenco_quattro_2","sensor_orientation":"wall_right",
    }


class PersonalVehicleTests(unittest.TestCase):
    def test_multiple_profiles_switch_edit_and_keep_dimensions_and_images(self):
        f=flow({})
        asyncio.run(f.async_step_custom_vehicle({"vehicle_profile":"new"}))
        a=asyncio.run(f.async_step_details(values("Wohnmobil A",4.332,1.81,1.98,"/local/a-top.png","/local/a-side.png")))["data"]
        a_id=a["vehicle_profile"]
        self.assertTrue(a_id.startswith("user_"))
        f=flow(a)
        asyncio.run(f.async_step_custom_vehicle({"vehicle_profile":"new"}))
        b=asyncio.run(f.async_step_details(values("Wohnmobil B",3.5,1.6,1.7,"https://example.org/b.png")))["data"]
        b_id=b["vehicle_profile"]
        self.assertNotEqual(a_id,b_id)
        self.assertEqual(len(b["custom_vehicles"]),2)
        f=flow(b)
        form=asyncio.run(f.async_step_custom_vehicle({"vehicle_profile":a_id}))
        defaults={str(k):k.default for k in form["data_schema"]}
        self.assertEqual(defaults["vehicle_name"],"Wohnmobil A")
        self.assertEqual(defaults["longitudinal_length"],4.332)
        self.assertEqual(defaults["transverse_width"],1.81)
        self.assertEqual(defaults["rear_transverse_width"],1.98)
        self.assertEqual(defaults["top_image"],"/local/a-top.png")
        c=asyncio.run(f.async_step_details(values("A umbenannt",4.4,1.82,1.99,"/local/new.png")))["data"]
        self.assertEqual(c["vehicle_profile"],a_id)
        self.assertEqual(len(c["custom_vehicles"]),2)
        self.assertEqual(c["custom_vehicles"][b_id],b["custom_vehicles"][b_id])
        self.assertEqual(ns["custom_vehicle_metadata"](c)["display_name"],"A umbenannt")
        self.assertEqual(ns["custom_vehicle_metadata"](c)["top_image"],"/local/new.png")

    def test_legacy_custom_migrates_only_when_saved(self):
        original={"vehicle_profile":"custom","longitudinal_length":4.1,
                  "transverse_width":1.81,"rear_transverse_width":1.98,"equal_track_widths":False}
        f=flow(original)
        self.assertEqual(f._current_vehicle()["manufacturer"],"Benutzerdefiniert")
        asyncio.run(f.async_step_custom_vehicle({"vehicle_profile":"custom"}))
        self.assertNotIn("custom_vehicles",f.config_entry.options)
        updated=asyncio.run(f.async_step_details(values("Bestandsfahrzeug",4.1,1.81,1.98)))["data"]
        self.assertTrue(updated["vehicle_profile"].startswith("user_"))
        self.assertEqual(updated["longitudinal_length"],4.1)

    def test_builtin_does_not_use_old_personal_images(self):
        meta=ns["custom_vehicle_metadata"]({"vehicle_profile":"ahorn_canada_ad_2019","top_image":"/local/old.png"})
        self.assertFalse(meta["custom_vehicle"])
        self.assertEqual(meta["top_image"],"")

    def test_invalid_images_keep_form_and_do_not_save(self):
        f=flow({})
        asyncio.run(f.async_step_custom_vehicle({"vehicle_profile":"new"}))
        response=asyncio.run(f.async_step_details(values("Name",4,1.8,1.9,"not-a-path")))
        self.assertEqual(response["step_id"],"details")
        self.assertEqual(response["errors"],{"top_image":"invalid_image"})
        self.assertNotIn("data",response)
        defaults={str(k):k.default for k in response["data_schema"]}
        self.assertEqual(defaults["vehicle_name"],"Name")
        self.assertEqual(defaults["top_image"],"not-a-path")

    def test_image_path_validation(self):
        for path in ["","/local/a.png","/api/image/serve/abc/original","https://example.org/a.png"]:
            self.assertEqual(flow_ns["image_path"](path),path)
        image_id="0123456789abcdef"*2
        original=f"/api/image/serve/{image_id}/original"
        self.assertEqual(flow_ns["image_path"](f"media-source://image_upload/{image_id}"),original)
        self.assertEqual(flow_ns["image_path"](original[1:]),original)
        for path in ["javascript:alert(1)","//example.org/a.png","C:/test.png","relative.png","data:image/png;base64,x"]:
            with self.assertRaises(ValueError):flow_ns["image_path"](path)


if __name__=="__main__": unittest.main()
