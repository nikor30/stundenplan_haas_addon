"""Shared entity base for one kid's timetable."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CLASS, CONF_KID_NAME, DOMAIN
from .coordinator import StundenplanConfigEntry, StundenplanCoordinator


class StundenplanEntity(CoordinatorEntity[StundenplanCoordinator]):
    """Groups all entities of a kid under one device."""

    _attr_has_entity_name = True

    def __init__(self, entry: StundenplanConfigEntry, key: str) -> None:
        super().__init__(entry.runtime_data.coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_KID_NAME],
            model=f"Klasse {entry.data[CONF_CLASS]}",
            manufacturer="SchuleIntern",
            entry_type=DeviceEntryType.SERVICE,
        )
