"""Timetable sensor: today's lesson count, with the full week as attributes for the card."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_ACCENT,
    CONF_CLASS,
    CONF_KID_NAME,
    CONF_POPUP_END,
    CONF_POPUP_START,
    DEFAULT_ACCENT,
    DEFAULT_POPUP_END,
    DEFAULT_POPUP_START,
    DOMAIN,
)
from .coordinator import StundenplanConfigEntry
from .entity import StundenplanEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StundenplanConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([TimetableSensor(entry)])


class TimetableSensor(StundenplanEntity, SensorEntity):
    """The card reads everything it renders from this sensor."""

    _attr_icon = "mdi:timetable"
    _attr_native_unit_of_measurement = "Stunden"
    # The week plan changes rarely and is large; keep it out of the history database.
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(self, entry: StundenplanConfigEntry) -> None:
        super().__init__(entry, "timetable")

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("today_lessons")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        options = self._entry.options
        popup_entity = er.async_get(self.hass).async_get_entity_id(
            "binary_sensor", DOMAIN, f"{self._entry.entry_id}_popup"
        )
        return {
            "kid": self._entry.data[CONF_KID_NAME],
            "school_class": self._entry.data[CONF_CLASS],
            "accent_color": options.get(CONF_ACCENT, DEFAULT_ACCENT),
            "popup_entity": popup_entity,
            "popup_start": options.get(CONF_POPUP_START, DEFAULT_POPUP_START)[:5],
            "popup_end": options.get(CONF_POPUP_END, DEFAULT_POPUP_END)[:5],
            **self.coordinator.data,
        }
