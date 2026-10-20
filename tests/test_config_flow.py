"""Config and options flow."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.stundenplan.api import StundenplanAuthError
from custom_components.stundenplan.const import (
    CONF_BASE_URL,
    CONF_CLASS,
    CONF_HIDDEN,
    CONF_KID_NAME,
    CONF_POPUP_DAYS,
    CONF_POPUP_END,
    CONF_POPUP_START,
    CONF_SUBJECTS,
    DOMAIN,
)

from .conftest import DEFAULTS

LOGIN = {CONF_BASE_URL: "https://portal.example", CONF_USERNAME: "eltern@example.com", CONF_PASSWORD: "secret"}
KID = {
    CONF_KID_NAME: "Adrian",
    CONF_CLASS: "5A",
    CONF_POPUP_START: "06:30:00",
    CONF_POPUP_END: "07:00:00",
    CONF_POPUP_DAYS: ["mon", "tue", "wed", "thu", "fri"],
}
FETCH = "custom_components.stundenplan.config_flow._async_fetch_defaults"


async def test_user_flow(hass: HomeAssistant, mock_portal) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    with patch(FETCH, return_value=DEFAULTS):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], LOGIN)
    assert result["step_id"] == "kid"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], KID)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Adrian"
    assert result["data"][CONF_CLASS] == "5A"
    assert result["options"][CONF_POPUP_START] == "06:30:00"


async def test_invalid_auth(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    with patch(FETCH, side_effect=StundenplanAuthError("nope")):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], LOGIN)
    assert result["errors"] == {"base": "invalid_auth"}


async def test_options_flow(hass: HomeAssistant, mock_portal) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    with patch(FETCH, return_value=DEFAULTS):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], LOGIN)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], KID)
    await hass.async_block_till_done()
    entry = result["result"]

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "courses"})
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"taken_subjects": ["Ev", "Sm"]})
    assert result["type"] is FlowResultType.MENU

    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "subjects"})
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"subject": "M"})
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"name": "Mathematik", "icon": "🧮", "color": [255, 0, 0], "hint": "Zirkel", "reset": False},
    )
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "save"})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert sorted(entry.options[CONF_HIDDEN]) == ["Eth", "K", "Sw"]
    assert entry.options[CONF_SUBJECTS]["M"] == {"name": "Mathematik", "icon": "🧮", "color": "#ff0000", "hint": "Zirkel"}

    state = hass.states.get("sensor.adrian_timetable")
    tuesday_slot = next(d for d in state.attributes["days"] if d["short"] == "Di")["slots"][1]
    assert [l["code"] for l in tuesday_slot] == ["Ev"]
