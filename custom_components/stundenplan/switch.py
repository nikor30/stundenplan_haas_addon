"""Turns the scheduled pop-up on or off, e.g. during school holidays."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .coordinator import StundenplanConfigEntry
from .entity import StundenplanEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StundenplanConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([PopupSwitch(entry)])


class PopupSwitch(StundenplanEntity, SwitchEntity, RestoreEntity):
    """Scheduled pop-up enabled."""

    _attr_icon = "mdi:calendar-clock"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, entry: StundenplanConfigEntry) -> None:
        super().__init__(entry, "popup_enabled")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self._set(last.state != STATE_OFF)

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self._entry.runtime_data.popup_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._set(False)

    def _set(self, enabled: bool) -> None:
        runtime = self._entry.runtime_data
        runtime.popup_enabled = enabled
        runtime.notify()
        self.async_write_ha_state()
