"""Sensors for RV Level Sensor Alpha 4."""
from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, PERCENTAGE, UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import RVLevelCoordinator, SIGNAL_UPDATE

DESCRIPTIONS = (
    SensorEntityDescription(key="longitudinal_angle", name="Längsneigung", native_unit_of_measurement="°"),
    SensorEntityDescription(key="transverse_angle", name="Querneigung", native_unit_of_measurement="°"),
    SensorEntityDescription(key="battery", name="Batterie", native_unit_of_measurement=PERCENTAGE, device_class=SensorDeviceClass.BATTERY),
    SensorEntityDescription(key="configured_length_m", name="Berechnungslänge", native_unit_of_measurement="m", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="configured_width_m", name="Berechnungsbreite", native_unit_of_measurement="m", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="vehicle_profile", name="Fahrzeugprofil", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="wedge_profile", name="Keilprofil", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="wedge_count", name="Keilanzahl", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="auto_disconnect_remaining", name="Auto-Disconnect Restzeit", native_unit_of_measurement="s", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="longitudinal_lift_cm", name="Längskorrektur", native_unit_of_measurement=UnitOfLength.CENTIMETERS),
    SensorEntityDescription(key="transverse_lift_cm", name="Querkorrektur", native_unit_of_measurement=UnitOfLength.CENTIMETERS),
    SensorEntityDescription(key="front_left_lift_cm", name="Vorne links anheben", native_unit_of_measurement=UnitOfLength.CENTIMETERS),
    SensorEntityDescription(key="front_right_lift_cm", name="Vorne rechts anheben", native_unit_of_measurement=UnitOfLength.CENTIMETERS),
    SensorEntityDescription(key="rear_left_lift_cm", name="Hinten links anheben", native_unit_of_measurement=UnitOfLength.CENTIMETERS),
    SensorEntityDescription(key="rear_right_lift_cm", name="Hinten rechts anheben", native_unit_of_measurement=UnitOfLength.CENTIMETERS),
    SensorEntityDescription(key="front_left_high_cm", name="Vorne links zu hoch", native_unit_of_measurement=UnitOfLength.CENTIMETERS),
    SensorEntityDescription(key="front_right_high_cm", name="Vorne rechts zu hoch", native_unit_of_measurement=UnitOfLength.CENTIMETERS),
    SensorEntityDescription(key="rear_left_high_cm", name="Hinten links zu hoch", native_unit_of_measurement=UnitOfLength.CENTIMETERS),
    SensorEntityDescription(key="rear_right_high_cm", name="Hinten rechts zu hoch", native_unit_of_measurement=UnitOfLength.CENTIMETERS),
    SensorEntityDescription(key="level_status", name="Nivellierstatus"),
    SensorEntityDescription(key="wedge_front_left_cm", name="Keil vorne links", native_unit_of_measurement=UnitOfLength.CENTIMETERS),
    SensorEntityDescription(key="wedge_front_right_cm", name="Keil vorne rechts", native_unit_of_measurement=UnitOfLength.CENTIMETERS),
    SensorEntityDescription(key="wedge_rear_left_cm", name="Keil hinten links", native_unit_of_measurement=UnitOfLength.CENTIMETERS),
    SensorEntityDescription(key="wedge_rear_right_cm", name="Keil hinten rechts", native_unit_of_measurement=UnitOfLength.CENTIMETERS),
    SensorEntityDescription(key="wedge_instruction", name="Keilempfehlung"),
    SensorEntityDescription(key="triple_front_left", name="Milenco vorne links"),
    SensorEntityDescription(key="triple_front_right", name="Milenco vorne rechts"),
    SensorEntityDescription(key="triple_rear_left", name="Milenco hinten links"),
    SensorEntityDescription(key="triple_rear_right", name="Milenco hinten rechts"),

    SensorEntityDescription(key="raw_fff4", name="FFF4 raw", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="raw_fff8", name="FFF8 raw", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="read_fff1", name="FFF1 read", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="read_fff2", name="FFF2 live read", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="previous_fff2", name="FFF2 previous", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="fff2_change_count", name="FFF2 change count", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="read_fff6", name="FFF6 read", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="notification_count", name="Notification count", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="read_count", name="Read count", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="last_source", name="Last data source", entity_category=EntityCategory.DIAGNOSTIC),
    SensorEntityDescription(key="last_error", name="Last BLE error", entity_category=EntityCategory.DIAGNOSTIC),
)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: RVLevelCoordinator = entry.runtime_data
    async_add_entities(RVLevelSensor(coordinator, d) for d in DESCRIPTIONS)

class RVLevelSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: RVLevelCoordinator, description: SensorEntityDescription) -> None:
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            connections={(CONNECTION_BLUETOOTH, coordinator.address)},
            name=coordinator.name,
            manufacturer="RVLevel compatible",
            model="RV Level 410 / RVS01",
        )

    @property
    def native_value(self):
        if self.entity_description.key == "configured_length_m":
            from .const import CONF_LONGITUDINAL_LENGTH, DEFAULT_LONGITUDINAL_LENGTH
            return self.coordinator.entry.options.get(CONF_LONGITUDINAL_LENGTH, DEFAULT_LONGITUDINAL_LENGTH)
        if self.entity_description.key == "configured_width_m":
            from .const import CONF_TRANSVERSE_WIDTH, DEFAULT_TRANSVERSE_WIDTH
            return self.coordinator.entry.options.get(CONF_TRANSVERSE_WIDTH, DEFAULT_TRANSVERSE_WIDTH)
        if self.entity_description.key == "vehicle_profile":
            from .const import CONF_VEHICLE_PROFILE, DEFAULT_VEHICLE_PROFILE, VEHICLE_PROFILES
            key = self.coordinator.entry.options.get(CONF_VEHICLE_PROFILE, DEFAULT_VEHICLE_PROFILE)
            return VEHICLE_PROFILES.get(key, {}).get("label", key)
        if self.entity_description.key == "wedge_profile":
            from .const import CONF_WEDGE_PROFILE, DEFAULT_WEDGE_PROFILE, WEDGE_PROFILES
            key = self.coordinator.entry.options.get(CONF_WEDGE_PROFILE, DEFAULT_WEDGE_PROFILE)
            return WEDGE_PROFILES.get(key, {}).get("label", key)
        if self.entity_description.key == "wedge_count":
            return 2
        return getattr(self.coordinator.state, self.entity_description.key)

    @property
    def extra_state_attributes(self):
        if self.entity_description.key == "wedge_instruction":
            return self.coordinator.state.wedge_plan
        return None

    @property
    def available(self) -> bool:
        return True

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_UPDATE, self._handle_update)
        )

    @callback
    def _handle_update(self, address: str) -> None:
        if address == self.coordinator.address:
            self.async_write_ha_state()
