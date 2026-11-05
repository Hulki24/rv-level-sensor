"""RV Level Sensor integration."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import RVLevelCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "button", "binary_sensor"]
STATIC_URL = "/rv-level-sensor"
CARD_PATH = f"{STATIC_URL}/rv-level-card.js"
CARD_URL = f"{CARD_PATH}?v=1.0.1-beta.13"
FRONTEND_DIR = Path(__file__).parent / "frontend"
DATA_FRONTEND_REGISTERED = "xparkle_rvlevel_frontend_registered"


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when vehicle dimensions are changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_register_lovelace_resource(hass: HomeAssistant) -> None:
    """Create or update the dashboard module resource in storage mode."""
    lovelace = hass.data.get(LOVELACE_DATA)
    if lovelace is None:
        _LOGGER.debug("Lovelace is not loaded yet; extra-js fallback remains active")
        return

    if lovelace.resource_mode != MODE_STORAGE:
        _LOGGER.info(
            "Lovelace resources are not in storage mode; automatic resource "
            "registration is unavailable, using extra-js fallback"
        )
        return

    resources = lovelace.resources
    existing = None
    for item in resources.async_items():
        url = str(item.get("url", ""))
        if url.split("?", 1)[0] == CARD_PATH:
            existing = item
            break

    data = {"url": CARD_URL, "res_type": "module"}
    if existing is None:
        await resources.async_create_item(data)
        _LOGGER.info("Registered RV Level dashboard resource: %s", CARD_URL)
        return

    if existing.get("url") != CARD_URL or existing.get("type") != "module":
        await resources.async_update_item(existing["id"], data)
        _LOGGER.info("Updated RV Level dashboard resource: %s", CARD_URL)


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve and automatically register the bundled dashboard card."""
    if hass.data.get(DATA_FRONTEND_REGISTERED):
        return

    await hass.http.async_register_static_paths(
        [StaticPathConfig(STATIC_URL, str(FRONTEND_DIR), False)]
    )

    # Keep the legacy autoload path as a fallback, while the Lovelace resource
    # registration below makes fresh HACS installs reliable.
    add_extra_js_url(hass, CARD_URL)

    try:
        await _async_register_lovelace_resource(hass)
    except Exception:  # Do not prevent the sensor integration from starting.
        _LOGGER.exception("Could not automatically register dashboard resource")

    hass.data[DATA_FRONTEND_REGISTERED] = True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await _async_register_frontend(hass)
    coordinator = RVLevelCoordinator(hass, entry)
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(async_update_listener))
    await coordinator.async_start()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.async_stop()
    return unload_ok
