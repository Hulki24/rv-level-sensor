"""Config flow for RV Level Sensor."""
from __future__ import annotations
from typing import Any
from uuid import uuid4
from urllib.parse import urlsplit
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
    CONF_CUSTOM_VEHICLES, CONF_VEHICLE_NAME, CONF_TOP_IMAGE, CONF_SIDE_IMAGE,
    CONF_BODY_LENGTH, CONF_BODY_WIDTH, CONF_BODY_HEIGHT, CUSTOM_PROFILE_PREFIX,

)

def image_path(value):
    """Accept HA-relative paths or web image URLs, and allow blank defaults."""
    value = value.strip()
    media_prefix = "media-source://image_upload/"
    if value.startswith(media_prefix):
        image_id = value[len(media_prefix):]
        if len(image_id) == 32 and all(char in "0123456789abcdef" for char in image_id):
            return f"/api/image/serve/{image_id}/original"
    if value.startswith(("local/", "api/image/serve/")):
        value = "/" + value
    if not value or (value.startswith("/") and not value.startswith("//")):
        return value
    try:
        parsed = urlsplit(value)
        if parsed.scheme in ("http", "https") and parsed.hostname:
            return value
    except ValueError:
        pass
    raise vol.Invalid("Bildpfad muss mit / beginnen oder eine HTTP(S)-URL sein")


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
    def _personal_profiles(self):
        options = self.config_entry.options
        profiles = dict(options.get(CONF_CUSTOM_VEHICLES, {}))
        if self._current_profile() == "custom":
            profiles["custom"] = options
        return profiles

    def _current_vehicle(self):
        key = self._current_profile()
        saved = self._personal_profiles().get(key)
        if saved is not None:
            return {
                "manufacturer": saved.get(CONF_VEHICLE_MANUFACTURER, "Benutzerdefiniert"),
                "label": saved.get(CONF_VEHICLE_NAME, "Eigenes Wohnmobil"),
            }
        return VEHICLE_PROFILES.get(key, VEHICLE_PROFILES[DEFAULT_VEHICLE_PROFILE])

    def _manufacturers(self):
        names = {vehicle["manufacturer"] for key, vehicle in VEHICLE_PROFILES.items() if key != "custom"}
        names.add("Carthago")
        names.update(profile.get(CONF_VEHICLE_MANUFACTURER, "Benutzerdefiniert")
                     for profile in self._personal_profiles().values())
        return sorted(names, key=str.casefold)

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            manufacturer = user_input[CONF_VEHICLE_MANUFACTURER]
            if manufacturer == "__new__":
                return await self.async_step_manufacturer()
            self._selection[CONF_VEHICLE_MANUFACTURER] = manufacturer
            return await self.async_step_model()
        choices = {name: name for name in self._manufacturers()}
        choices["__new__"] = "Neuen Hersteller hinzufügen"
        return self.async_show_form(step_id="init", data_schema=vol.Schema({
            vol.Required(CONF_VEHICLE_MANUFACTURER, default=self._current_vehicle()["manufacturer"]): vol.In(choices)
        }))

    async def async_step_manufacturer(self, user_input=None):
        name = ""
        errors = {}
        if user_input is not None:
            name = user_input[CONF_VEHICLE_MANUFACTURER].strip()
            if not name or name.casefold() in ("__new__", "benutzerdefiniert"):
                errors[CONF_VEHICLE_MANUFACTURER] = "invalid_manufacturer"
            elif name.casefold() in {item.casefold() for item in self._manufacturers()}:
                errors[CONF_VEHICLE_MANUFACTURER] = "manufacturer_exists"
            else:
                self._selection[CONF_VEHICLE_MANUFACTURER] = name
                return await self.async_step_model()
        return self.async_show_form(step_id="manufacturer", errors=errors, data_schema=vol.Schema({
            vol.Required(CONF_VEHICLE_MANUFACTURER, default=name): vol.All(str, vol.Length(min=1, max=100))
        }))

    async def async_step_model(self, user_input=None):
        manufacturer = self._selection[CONF_VEHICLE_MANUFACTURER]
        if user_input is not None:
            selected = user_input[CONF_VEHICLE_PROFILE]
            if selected.startswith("builtin:"):
                self._selection[CONF_VEHICLE_MODEL] = selected.removeprefix("builtin:")
                return await self.async_step_year()
            self._selection[CONF_VEHICLE_PROFILE] = (
                CUSTOM_PROFILE_PREFIX + uuid4().hex if selected == "new" else selected
            )
            return await self.async_step_details()

        models = {vehicle["model"] for key, vehicle in VEHICLE_PROFILES.items()
                  if key != "custom" and vehicle["manufacturer"] == manufacturer}
        choices = {f"builtin:{model}": model for model in sorted(models, key=str.casefold)}
        choices.update({
            key: profile.get(CONF_VEHICLE_NAME, "Eigenes Wohnmobil")
            for key, profile in self._personal_profiles().items()
            if profile.get(CONF_VEHICLE_MANUFACTURER, "Benutzerdefiniert") == manufacturer
        })
        choices["new"] = "Neuen Typ anlegen"
        current = self._current_profile()
        if current not in choices:
            current = f"builtin:{self._current_vehicle().get('model', '')}"
        return self.async_show_form(step_id="model", data_schema=vol.Schema({
            vol.Required(CONF_VEHICLE_PROFILE, default=current if current in choices else next(iter(choices))): vol.In(choices)
        }), description_placeholders={"manufacturer": manufacturer})

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
        o=self.config_entry.options
        profile=self._selection.get(CONF_VEHICLE_PROFILE,self._current_profile())
        manufacturer=self._selection.get(CONF_VEHICLE_MANUFACTURER,self._current_vehicle()["manufacturer"])
        if CONF_VEHICLE_PROFILE not in self._selection and manufacturer=="Benutzerdefiniert":
            profile="custom"
        custom=profile=="custom" or profile.startswith(CUSTOM_PROFILE_PREFIX)
        reassign_manufacturer=custom and manufacturer=="Benutzerdefiniert"
        vehicle=VEHICLE_PROFILES.get(profile,{})
        current_wedge=o.get(CONF_WEDGE_PROFILE,DEFAULT_WEDGE_PROFILE)
        current_orientation=o.get(CONF_SENSOR_ORIENTATION,DEFAULT_SENSOR_ORIENTATION)
        # Keep legacy behavior while displaying the corresponding wall.
        current_orientation={SENSOR_ORIENTATION_NORMAL:SENSOR_WALL_LEFT,
                             SENSOR_ORIENTATION_ROTATED_180:SENSOR_WALL_RIGHT}.get(current_orientation,current_orientation)
        saved=o.get(CONF_CUSTOM_VEHICLES,{}).get(profile,{}) if custom else {}
        source=saved or o
        errors={}
        if user_input is not None and custom:
            for key in (CONF_TOP_IMAGE,CONF_SIDE_IMAGE):
                try:
                    user_input[key]=image_path(user_input.get(key,""))
                except vol.Invalid:
                    errors[key]="invalid_image"
            if not user_input.get(CONF_VEHICLE_NAME,"Mein Wohnmobil").strip():
                errors[CONF_VEHICLE_NAME]="invalid_name"
            if reassign_manufacturer:
                name=user_input.get(CONF_VEHICLE_MANUFACTURER,manufacturer).strip()
                if not name or name=="__new__":
                    errors[CONF_VEHICLE_MANUFACTURER]="invalid_manufacturer"
                else:
                    manufacturer=next((item for item in self._manufacturers() if item.casefold()==name.casefold()),name)
            if errors:
                source={**source,**user_input}
        current_length=source.get(CONF_LONGITUDINAL_LENGTH,DEFAULT_LONGITUDINAL_LENGTH)
        same_profile=profile==self._current_profile()
        current_width=source.get(CONF_TRANSVERSE_WIDTH,DEFAULT_TRANSVERSE_WIDTH) if custom or same_profile else vehicle.get("track",DEFAULT_TRANSVERSE_WIDTH)
        current_rear=source.get(CONF_REAR_WIDTH,current_width) if custom or same_profile else current_width
        current_equal=source.get(CONF_EQUAL_WIDTHS,True) if custom or same_profile else True
        personal=saved or (o if profile=="custom" else {})
        if errors:
            personal={**personal,**user_input}
            current_wedge=user_input.get(CONF_WEDGE_PROFILE,current_wedge)
            current_orientation=user_input.get(CONF_SENSOR_ORIENTATION,current_orientation)
        current_name=personal.get(CONF_VEHICLE_NAME,"Mein Wohnmobil")
        if user_input is not None and not errors:
            data=dict(o); data.update(user_input); data.update(self._selection); data[CONF_VEHICLE_PROFILE]=profile
            if not custom:
                data[CONF_LONGITUDINAL_LENGTH]=vehicle["wheelbase"]
            if data.get(CONF_EQUAL_WIDTHS,True):
                data[CONF_REAR_WIDTH]=data[CONF_TRANSVERSE_WIDTH]
            if custom:
                # Keep stable IDs when renaming/editing; legacy custom migrates on save.
                if profile=="custom":
                    profile=CUSTOM_PROFILE_PREFIX+uuid4().hex
                    data[CONF_VEHICLE_PROFILE]=profile
                data[CONF_VEHICLE_NAME]=user_input.get(CONF_VEHICLE_NAME,current_name).strip()
                data[CONF_VEHICLE_MANUFACTURER]=manufacturer
                personal_keys=(CONF_VEHICLE_MANUFACTURER,CONF_VEHICLE_NAME,CONF_LONGITUDINAL_LENGTH,CONF_TRANSVERSE_WIDTH,
                               CONF_REAR_WIDTH,CONF_EQUAL_WIDTHS,CONF_TOP_IMAGE,CONF_SIDE_IMAGE,
                               CONF_BODY_LENGTH,CONF_BODY_WIDTH,CONF_BODY_HEIGHT)
                for key in (CONF_TOP_IMAGE,CONF_SIDE_IMAGE):
                    data[key]=user_input.get(key,"").strip()
                for key in (CONF_BODY_LENGTH,CONF_BODY_WIDTH,CONF_BODY_HEIGHT):
                    data[key]=user_input.get(key,0)
                profiles=dict(o.get(CONF_CUSTOM_VEHICLES,{}))
                profiles[profile]={key:data[key] for key in personal_keys}
                data[CONF_CUSTOM_VEHICLES]=profiles
            return self.async_create_entry(title="",data=data)
        fields={}
        if reassign_manufacturer:
            fields[vol.Required(CONF_VEHICLE_MANUFACTURER,default=manufacturer)]=vol.All(str,vol.Length(min=1,max=100))
        if custom:
            fields[vol.Required(CONF_VEHICLE_NAME,default=current_name)]=vol.All(str,vol.Length(min=1,max=100))
            fields[vol.Required(CONF_LONGITUDINAL_LENGTH,default=current_length)]=vol.All(vol.Coerce(float),vol.Range(min=.5,max=20))
        fields.update({
            vol.Required(CONF_TRANSVERSE_WIDTH,default=current_width):vol.All(vol.Coerce(float),vol.Range(min=.5,max=5)),
            vol.Required(CONF_EQUAL_WIDTHS,default=current_equal):bool,
            vol.Required(CONF_REAR_WIDTH,default=current_rear):vol.All(vol.Coerce(float),vol.Range(min=.5,max=5)),
            vol.Required(CONF_WEDGE_PROFILE,default=current_wedge):vol.In({k:v["label"] for k,v in WEDGE_PROFILES.items()}),
            vol.Required(CONF_SENSOR_ORIENTATION,default=current_orientation):vol.In({SENSOR_WALL_RIGHT:"Wand in Fahrtrichtung rechts",SENSOR_WALL_LEFT:"Wand in Fahrtrichtung links",SENSOR_WALL_FRONT:"Wand vorne",SENSOR_WALL_REAR:"Wand hinten"}),
        })
        if custom:
            for key in (CONF_BODY_LENGTH,CONF_BODY_WIDTH,CONF_BODY_HEIGHT):
                fields[vol.Optional(key,default=personal.get(key,0))]=vol.All(vol.Coerce(float),vol.Range(min=0,max=25))
            for key in (CONF_TOP_IMAGE,CONF_SIDE_IMAGE):
                fields[vol.Optional(key,default=personal.get(key,""))]=str
        return self.async_show_form(step_id="details",data_schema=vol.Schema(fields),errors=errors,description_placeholders={"vehicle":vehicle.get("label",manufacturer)})
