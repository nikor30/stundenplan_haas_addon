"""Polling: period times are fetched once a day, and a 429 makes the coordinator back off."""

from datetime import datetime
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stundenplan.api import StundenplanRateLimited
from custom_components.stundenplan.const import DOMAIN

from .test_init import ENTRY_DATA, OPTIONS, _setup

DEFAULTS_CALL = "custom_components.stundenplan.api.SchuleInternClient.async_get_defaults"


async def test_defaults_once_a_day_and_rate_limit(
    hass: HomeAssistant, mock_portal, freezer: FrozenDateTimeFactory
) -> None:
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to(datetime(2026, 10, 20, 9, 0, tzinfo=dt_util.get_default_time_zone()))
    entry = await _setup(hass)
    coordinator = entry.runtime_data.coordinator

    with patch(DEFAULTS_CALL) as get_defaults:
        await coordinator.async_refresh()
        assert coordinator.last_update_success
        get_defaults.assert_not_called()  # same day: the cached period times are used

    mock_portal.side_effect = StundenplanRateLimited(600)
    await coordinator.async_refresh()
    assert not coordinator.last_update_success
    await hass.async_block_till_done()
    assert hass.states.get("sensor.niko_timetable").state == "3"  # the last good plan stays on screen

    mock_portal.side_effect = None
    freezer.move_to(datetime(2026, 10, 21, 9, 0, tzinfo=dt_util.get_default_time_zone()))
    with patch(DEFAULTS_CALL, return_value=coordinator._defaults) as get_defaults:
        await coordinator.async_refresh()
        assert coordinator.last_update_success
        get_defaults.assert_called_once()  # new day: fetched again


async def test_rate_limit_at_setup_pauses_retries(
    hass: HomeAssistant, mock_portal, freezer: FrozenDateTimeFactory
) -> None:
    mock_portal.side_effect = StundenplanRateLimited(600)
    entry = MockConfigEntry(domain=DOMAIN, title="Niko", data=ENTRY_DATA, options=OPTIONS)
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert mock_portal.call_count == 1

    await hass.config_entries.async_reload(entry.entry_id)  # a retry inside the pause
    assert mock_portal.call_count == 1  # the portal was not asked again

    mock_portal.side_effect = None
    freezer.tick(601)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
