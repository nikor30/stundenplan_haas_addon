"""Stundenplan: school timetables from SchuleIntern portals in Home Assistant."""

from __future__ import annotations

from pathlib import Path

import aiohttp
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .api import SchuleInternClient
from .const import CARD_FILENAME, CONF_BASE_URL, DOMAIN, FRONTEND_URL
from .coordinator import StundenplanConfigEntry, StundenplanCoordinator, StundenplanRuntime

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR, Platform.SWITCH]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the dashboard card and load it on every dashboard."""
    integration = await async_get_integration(hass, DOMAIN)
    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_URL, str(Path(__file__).parent / "frontend"), False)]
    )
    add_extra_js_url(hass, f"{FRONTEND_URL}/{CARD_FILENAME}?v={integration.version}")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: StundenplanConfigEntry) -> bool:
    """Set up one kid's timetable."""
    # Own cookie jar: the portal session must not leak into other integrations.
    session = async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar())
    client = SchuleInternClient(
        session,
        entry.data[CONF_BASE_URL],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    coordinator = StundenplanCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = StundenplanRuntime(client=client, coordinator=coordinator)
    # The timetable sensor points the card at the pop-up sensor, so that one must exist first.
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.BINARY_SENSOR])
    await hass.config_entries.async_forward_entry_setups(
        entry, [p for p in PLATFORMS if p is not Platform.BINARY_SENSOR]
    )
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: StundenplanConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass: HomeAssistant, entry: StundenplanConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
