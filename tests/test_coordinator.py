"""Polling: period times are fetched once a day, and a 429 makes the coordinator back off."""

from datetime import datetime
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from custom_components.stundenplan.api import StundenplanRateLimited

from .test_init import _setup

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
    assert coordinator.data["today_lessons"] == 3  # the last good plan stays visible

    mock_portal.side_effect = None
    freezer.move_to(datetime(2026, 10, 21, 9, 0, tzinfo=dt_util.get_default_time_zone()))
    with patch(DEFAULTS_CALL, return_value=coordinator._defaults) as get_defaults:
        await coordinator.async_refresh()
        assert coordinator.last_update_success
        get_defaults.assert_called_once()  # new day: fetched again
