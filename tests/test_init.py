"""Entities and the pop-up window."""

from datetime import datetime, time

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.stundenplan.binary_sensor import in_window
from custom_components.stundenplan.const import DOMAIN

ENTRY_DATA = {
    "base_url": "https://portal.example",
    "username": "eltern@example.com",
    "password": "secret",
    "kid_name": "Niko",
    "school_class": "5A",
}
OPTIONS = {"popup_start": "07:00:00", "popup_end": "07:30:00", "popup_days": ["mon", "tue", "wed", "thu", "fri"]}


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, title="Niko", data=ENTRY_DATA, options=OPTIONS)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_entities_and_popup(hass: HomeAssistant, mock_portal, freezer: FrozenDateTimeFactory) -> None:
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to(datetime(2026, 10, 20, 6, 59, tzinfo=dt_util.get_default_time_zone()))
    await _setup(hass)

    sensor = hass.states.get("sensor.niko_timetable")
    assert sensor.state == "3"
    assert sensor.attributes["kid"] == "Niko"
    assert sensor.attributes["popup_entity"] == "binary_sensor.niko_pop_up"
    assert hass.states.get("binary_sensor.niko_pop_up").state == "off"

    freezer.move_to(datetime(2026, 10, 20, 7, 0, tzinfo=dt_util.get_default_time_zone()))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.niko_pop_up").state == "on"

    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.niko_scheduled_pop_up"}, blocking=True)
    assert hass.states.get("binary_sensor.niko_pop_up").state == "off"

    await hass.services.async_call("button", "press", {"entity_id": "button.niko_show_pop_up_now"}, blocking=True)
    first = hass.states.get("binary_sensor.niko_pop_up")
    assert first.state == "on"

    # Pressing again while it's still on starts a new showing, so a closed sheet reappears.
    freezer.tick(30)
    await hass.services.async_call("button", "press", {"entity_id": "button.niko_show_pop_up_now"}, blocking=True)
    second = hass.states.get("binary_sensor.niko_pop_up")
    assert second.state == "on"
    assert second.attributes["shown_since"] != first.attributes["shown_since"]


async def test_window_showing_is_stable(hass: HomeAssistant, mock_portal, freezer: FrozenDateTimeFactory) -> None:
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to(datetime(2026, 10, 20, 7, 5, tzinfo=dt_util.get_default_time_zone()))
    await _setup(hass)
    first = hass.states.get("binary_sensor.niko_pop_up").attributes["shown_since"]
    assert first.startswith("2026-10-20T07:00:00")

    freezer.move_to(datetime(2026, 10, 20, 7, 10, tzinfo=dt_util.get_default_time_zone()))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.niko_pop_up").attributes["shown_since"] == first


async def test_card_is_served(hass: HomeAssistant, mock_portal, hass_client) -> None:
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "http", {})
    await _setup(hass)
    client = await hass_client()
    resp = await client.get("/stundenplan_frontend/stundenplan-card.js")
    assert resp.status == 200
    assert "stundenplan-card" in await resp.text()

    from homeassistant.components.frontend import DATA_EXTRA_JS_URL_ES5, DATA_EXTRA_MODULE_URL

    # Old kiosk browsers get the es5 build and only load the es5 list.
    for key in (DATA_EXTRA_MODULE_URL, DATA_EXTRA_JS_URL_ES5):
        assert any("stundenplan-card.js" in url for url in hass.data[key].urls)


def test_window_across_midnight() -> None:
    days = ["fri"]
    friday_late = datetime(2026, 10, 23, 23, 30)
    saturday_early = datetime(2026, 10, 24, 0, 30)
    assert in_window(friday_late, time(23, 0), time(1, 0), days)
    assert in_window(saturday_early, time(23, 0), time(1, 0), days)
    assert not in_window(datetime(2026, 10, 24, 23, 30), time(23, 0), time(1, 0), days)
