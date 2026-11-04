"""Config flow for RV Level Sensor."""
from __future__ import annotations
from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak, async_discovered_service_info
from homeassistant.data_entry_flow import FlowResult
from .const import (
    CONF_ADDRESS, CONF_NAME, DOMAIN, SERVICE_FFF0,
    CONF_LONGITUDINAL_LENGTH, CONF_TRANSVERSE_WIDTH, CONF_REAR_WIDTH, CONF_EQUAL_WIDTHS,
    DEFAULT_LONGITUDINAL_LENGTH, DEFAULT_TRANSVERSE_WIDTH,
    CONF_VEHICLE_PROFILE, CONF_VEHICLE_MANUFACTURER, CONF_VEHICLE_MODEL, CONF_VEHICLE_YEAR,
    CONF_WEDGE_PROFILE, DEFAULT_VEHICLE_PROFILE, DEFAULT_WEDGE_PROFILE,
    CONF_SENSOR_ORIENTATION, DEFAULT_SENSOR_ORIENTATION,
    SENSOR_ORIENTATION_NORMAL, SENSOR_ORIENTATION_ROTATED_180,
    SENSOR_WALL_RIGHT, SENSOR_WALL_LEFT, SENSOR_WALL_FRONT, SENSOR_WALL_REAR,
    VEHICLE_PROFILES, WEDGE_PROFILES,
)

class XparkleRVLevelConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    @staticmethod
    def async_get_options_flow(config_entry): return XparkleRVLevelOptionsFlow()
    def __init__(self): self._discovery = None
    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> FlowResult:
        name = discovery_info.name or discovery_info.device.name or ""
        if not name.startswith("RVLevel-") or SERVICE_FFF0 not in [u.lower() for u in discovery_info.service_uuids]: return self.async_abort(reason="not_supported")
        await self.async_set_unique_id(discovery_info.address); self._abort_if_unique_id_configured(); self._discovery=discovery_info
        self.context["title_placeholders"]={"name":name}; return await self.async_step_bluetooth_confirm()
    async def async_step_bluetooth_confirm(self,user_input=None):
        assert self._discovery is not None
        name=self._discovery.name or self._discovery.device.name or "RVLevel"
        if user_input is not None: return self.async_create_entry(title=name,data={CONF_ADDRESS:self._discovery.address,CONF_NAME:name})
        return self.async_show_form(step_id="bluetooth_confirm",description_placeholders={"name":name})
    async def async_step_user(self,user_input=None):
        devices={}
        for info in async_discovered_service_info(self.hass,connectable=True):
            name=info.name or info.device.name or ""
            if name.startswith("RVLevel-") and SERVICE_FFF0 in [u.lower() for u in info.service_uuids]: devices[info.address]=f"{name} ({info.address})"
        if user_input is not None:
            address=user_input[CONF_ADDRESS]; await self.async_set_unique_id(address); self._abort_if_unique_id_configured(); title=devices.get(address,address)
            return self.async_create_entry(title=title.split(" (")[0],data={CONF_ADDRESS:address,CONF_NAME:title.split(" (")[0]})
        if not devices:return self.async_abort(reason="no_devices_found")
        return self.async_show_form(step_id="user",data_schema=vol.Schema({vol.Required(CONF_ADDRESS):vol.In(devices)}))

class XparkleRVLevelOptionsFlow(config_entries.OptionsFlow):
    """Hierarchical vehicle selection: manufacturer -> model -> model year."""
    def __init__(self): self._selection={}
    def _current_profile(self):
        return self.config_entry.options.get(CONF_VEHICLE_PROFILE, DEFAULT_VEHICLE_PROFILE)
    def _current_vehicle(self):
        return VEHICLE_PROFILES.get(self._current_profile(), VEHICLE_PROFILES[DEFAULT_VEHICLE_PROFILE])
    async def async_step_init(self,user_input=None):
        current=self._current_vehicle(); manufacturers=sorted({v.get("manufacturer") for k,v in VEHICLE_PROFILES.items() if k!="custom"})+["Benutzerdefiniert"]
        if user_input is not None:
            self._selection[CONF_VEHICLE_MANUFACTURER]=user_input[CONF_VEHICLE_MANUFACTURER]
            if user_input[CONF_VEHICLE_MANUFACTURER]=="Benutzerdefiniert": return await self.async_step_details()
            return await self.async_step_model()
        default=current.get("manufacturer","Ahorn Camp")
        return self.async_show_form(step_id="init",data_schema=vol.Schema({vol.Required(CONF_VEHICLE_MANUFACTURER,default=default):vol.In(manufacturers)}))
    async def async_step_model(self,user_input=None):
        manufacturer=self._selection[CONF_VEHICLE_MANUFACTURER]
        models=sorted({v["model"] for k,v in VEHICLE_PROFILES.items() if k!="custom" and v.get("manufacturer")==manufacturer})
        current=self._current_vehicle(); default=current.get("model") if current.get("model") in models else models[0]
        if user_input is not None:
            self._selection[CONF_VEHICLE_MODEL]=user_input[CONF_VEHICLE_MODEL]; return await self.async_step_year()
        return self.async_show_form(step_id="model",data_schema=vol.Schema({vol.Required(CONF_VEHICLE_MODEL,default=default):vol.In(models)}))
    async def async_step_year(self,user_input=None):
        manufacturer=self._selection[CONF_VEHICLE_MANUFACTURER]; model=self._selection[CONF_VEHICLE_MODEL]
        profiles={k:v for k,v in VEHICLE_PROFILES.items() if k!="custom" and v.get("manufacturer")==manufacturer and v.get("model")==model}
        years=sorted({int(v["year"]) for v in profiles.values()})
        current=self._current_vehicle(); default=int(current.get("year")) if current.get("model")==model and int(current.get("year",0)) in years else years[-1]
        if user_input is not None:
            year=int(user_input[CONF_VEHICLE_YEAR]); self._selection[CONF_VEHICLE_YEAR]=year
            key=next(k for k,v in profiles.items() if int(v["year"])==year); self._selection[CONF_VEHICLE_PROFILE]=key
            return await self.async_step_details()
        return self.async_show_form(step_id="year",data_schema=vol.Schema({vol.Required(CONF_VEHICLE_YEAR,default=default):vol.In(years)}))
    async def async_step_details(self,user_input=None):
        o=self.config_entry.options; custom=self._selection.get(CONF_VEHICLE_MANUFACTURER)=="Benutzerdefiniert"
        profile=self._selection.get(CONF_VEHICLE_PROFILE,"custom" if custom else self._current_profile())
        vehicle=VEHICLE_PROFILES.get(profile,{})
        current_wedge=o.get(CONF_WEDGE_PROFILE,DEFAULT_WEDGE_PROFILE)
        current_orientation=o.get(CONF_SENSOR_ORIENTATION,DEFAULT_SENSOR_ORIENTATION)
        # Keep legacy behavior while displaying the corresponding wall.
        current_orientation={SENSOR_ORIENTATION_NORMAL:SENSOR_WALL_LEFT,
                             SENSOR_ORIENTATION_ROTATED_180:SENSOR_WALL_RIGHT}.get(current_orientation,current_orientation)
        current_length=o.get(CONF_LONGITUDINAL_LENGTH,DEFAULT_LONGITUDINAL_LENGTH)
        same_profile=profile==self._current_profile()
        current_width=o.get(CONF_TRANSVERSE_WIDTH,DEFAULT_TRANSVERSE_WIDTH) if same_profile else vehicle.get("track",DEFAULT_TRANSVERSE_WIDTH)
        current_rear=o.get(CONF_REAR_WIDTH,current_width) if same_profile else current_width
        current_equal=o.get(CONF_EQUAL_WIDTHS,True) if same_profile else True
        if user_input is not None:
            data=dict(o); data.update(user_input); data.update(self._selection); data[CONF_VEHICLE_PROFILE]=profile
            if not custom:
                data[CONF_LONGITUDINAL_LENGTH]=vehicle["wheelbase"]
            if data.get(CONF_EQUAL_WIDTHS,True):
                data[CONF_REAR_WIDTH]=data[CONF_TRANSVERSE_WIDTH]
            return self.async_create_entry(title="",data=data)
        fields={}
        if custom:
            fields[vol.Required(CONF_LONGITUDINAL_LENGTH,default=current_length)]=vol.All(vol.Coerce(float),vol.Range(min=.5,max=20))
        fields.update({
            vol.Required(CONF_TRANSVERSE_WIDTH,default=current_width):vol.All(vol.Coerce(float),vol.Range(min=.5,max=5)),
            vol.Required(CONF_EQUAL_WIDTHS,default=current_equal):bool,
            vol.Required(CONF_REAR_WIDTH,default=current_rear):vol.All(vol.Coerce(float),vol.Range(min=.5,max=5)),
            vol.Required(CONF_WEDGE_PROFILE,default=current_wedge):vol.In({k:v["label"] for k,v in WEDGE_PROFILES.items()}),
            vol.Required(CONF_SENSOR_ORIENTATION,default=current_orientation):vol.In({SENSOR_WALL_RIGHT:"Wand in Fahrtrichtung rechts",SENSOR_WALL_LEFT:"Wand in Fahrtrichtung links",SENSOR_WALL_FRONT:"Wand vorne",SENSOR_WALL_REAR:"Wand hinten"}),
        })
        return self.async_show_form(step_id="details",data_schema=vol.Schema(fields),description_placeholders={"vehicle":vehicle.get("label","Benutzerdefiniert")})
