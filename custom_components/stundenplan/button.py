"""Shows the pop-up right now, outside the scheduled window."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import StundenplanConfigEntry
from .entity import StundenplanEntity

SHOW_FOR = timedelta(minutes=5)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: StundenplanConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([ShowPopupButton(entry)])


class ShowPopupButton(StundenplanEntity, ButtonEntity):
    """Show the pop-up for five minutes."""

    _attr_icon = "mdi:play-box-outline"

    def __init__(self, entry: StundenplanConfigEntry) -> None:
        super().__init__(entry, "show_popup")

    @property
    def available(self) -> bool:
        return True

    async def async_press(self) -> None:
        runtime = self._entry.runtime_data
        runtime.popup_forced_until = dt_util.now() + SHOW_FOR
        runtime.notify()
