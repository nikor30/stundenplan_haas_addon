"""Polls the timetable for one kid."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import SchuleInternClient, StundenplanAuthError, StundenplanError
from .const import CONF_CLASS, CONF_HIDDEN, CONF_SUBJECTS, DOMAIN, UPDATE_INTERVAL
from .model import build_timetable, subject_codes

_LOGGER = logging.getLogger(__name__)


@dataclass
class StundenplanRuntime:
    """Objects shared by the entities of one config entry."""

    client: SchuleInternClient
    coordinator: StundenplanCoordinator
    popup_enabled: bool = True
    popup_forced_until: Any = None
    _listeners: list[Callable[[], None]] = field(default_factory=list)

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    def notify(self) -> None:
        for listener in list(self._listeners):
            listener()


type StundenplanConfigEntry = ConfigEntry[StundenplanRuntime]


class StundenplanCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches the plan and keeps the raw responses for the options flow."""

    config_entry: StundenplanConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: StundenplanConfigEntry,
        client: SchuleInternClient,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.raw_plan: list[Any] = []

    @property
    def subject_codes(self) -> list[str]:
        return subject_codes(self.raw_plan)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            defaults = await self.client.async_get_defaults()
            plan = await self.client.async_get_plan(self.config_entry.data[CONF_CLASS])
        except StundenplanAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except StundenplanError as err:
            raise UpdateFailed(str(err)) from err

        self.raw_plan = plan.get("plan") or []
        options = self.config_entry.options
        return build_timetable(
            defaults,
            plan,
            options.get(CONF_SUBJECTS, {}),
            options.get(CONF_HIDDEN, []),
            dt_util.now().date(),
        )
