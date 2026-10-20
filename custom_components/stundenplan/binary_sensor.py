"""On while the timetable pop-up should be shown on the dashboard."""

from __future__ import annotations

from datetime import datetime, time

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import (
    CONF_POPUP_DAYS,
    CONF_POPUP_END,
    CONF_POPUP_START,
    DEFAULT_POPUP_DAYS,
    DEFAULT_POPUP_END,
    DEFAULT_POPUP_START,
    WEEKDAYS,
)
from .coordinator import StundenplanConfigEntry
from .entity import StundenplanEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StundenplanConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([PopupBinarySensor(entry)])


def in_window(now: datetime, start: time, end: time, days: list[str]) -> bool:
    """Whether ``now`` falls inside the daily window; windows may cross midnight."""
    if start <= end:
        return WEEKDAYS[now.weekday()] in days and start <= now.time() < end
    if now.time() >= start:
        return WEEKDAYS[now.weekday()] in days
    # After midnight: the window belongs to the previous day.
    return WEEKDAYS[(now.weekday() - 1) % 7] in days and now.time() < end


class PopupBinarySensor(StundenplanEntity, BinarySensorEntity):
    """Drives the pop-up of the Stundenplan card."""

    _attr_icon = "mdi:tablet-dashboard"

    def __init__(self, entry: StundenplanConfigEntry) -> None:
        super().__init__(entry, "popup")
        options = entry.options
        self._start = time.fromisoformat(options.get(CONF_POPUP_START, DEFAULT_POPUP_START))
        self._end = time.fromisoformat(options.get(CONF_POPUP_END, DEFAULT_POPUP_END))
        self._days = options.get(CONF_POPUP_DAYS, DEFAULT_POPUP_DAYS)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        runtime = self._entry.runtime_data
        self.async_on_remove(runtime.add_listener(self.async_write_ha_state))
        self.async_on_remove(
            async_track_time_change(self.hass, self._tick, second=0)
        )

    @callback
    def _tick(self, _now: datetime) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        # The window is local; it does not depend on the portal being reachable.
        return True

    @property
    def is_on(self) -> bool:
        runtime = self._entry.runtime_data
        now = dt_util.now()
        if runtime.popup_forced_until and now < runtime.popup_forced_until:
            return True
        return runtime.popup_enabled and in_window(now, self._start, self._end, self._days)
