"""Config and options flow: one entry per kid."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    ColorRGBSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
)

from .api import SchuleInternClient, StundenplanAuthError, StundenplanError
from .const import (
    CONF_ACCENT,
    CONF_BASE_URL,
    CONF_CLASS,
    CONF_HIDDEN,
    CONF_KID_NAME,
    CONF_POPUP_DAYS,
    CONF_POPUP_END,
    CONF_POPUP_START,
    CONF_SUBJECTS,
    DEFAULT_ACCENT,
    DEFAULT_BASE_URL,
    DEFAULT_POPUP_DAYS,
    DEFAULT_POPUP_END,
    DEFAULT_POPUP_START,
    DOMAIN,
    WEEKDAYS,
)
from .model import alternative_codes, resolve_subject

CONF_SUBJECT = "subject"
CONF_TAKEN = "taken_subjects"
CONF_RESET = "reset"


async def _async_fetch_defaults(
    hass: HomeAssistant, base_url: str, username: str, password: str
) -> dict[str, Any]:
    """Log in once and return the portal defaults (including the user's classes)."""
    # A short-lived session of our own: Home Assistant's shared sessions must not be closed.
    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar()) as session:
        client = SchuleInternClient(session, base_url, username, password)
        await client.async_login()
        return await client.async_get_defaults()


def _hex_to_rgb(value: str) -> list[int]:
    value = value.lstrip("#")
    try:
        return [int(value[i : i + 2], 16) for i in (0, 2, 4)]
    except ValueError:
        return [10, 132, 255]


def _rgb_to_hex(value: list[int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*value)


def _popup_schema(options: Mapping[str, Any]) -> dict[Any, Any]:
    return {
        vol.Required(
            CONF_POPUP_START, default=options.get(CONF_POPUP_START, DEFAULT_POPUP_START)
        ): TimeSelector(),
        vol.Required(
            CONF_POPUP_END, default=options.get(CONF_POPUP_END, DEFAULT_POPUP_END)
        ): TimeSelector(),
        vol.Required(
            CONF_POPUP_DAYS, default=options.get(CONF_POPUP_DAYS, DEFAULT_POPUP_DAYS)
        ): SelectSelector(
            SelectSelectorConfig(
                options=WEEKDAYS,
                multiple=True,
                mode=SelectSelectorMode.LIST,
                translation_key="weekday",
            )
        ),
    }


class StundenplanConfigFlow(ConfigFlow, domain=DOMAIN):
    """Log in, then pick the kid's class and pop-up time."""

    VERSION = 1

    def __init__(self) -> None:
        self._login: dict[str, Any] = {}
        self._classes: list[str] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                defaults = await _async_fetch_defaults(
                    self.hass,
                    user_input[CONF_BASE_URL],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except StundenplanAuthError:
                errors["base"] = "invalid_auth"
            except StundenplanError:
                errors["base"] = "cannot_connect"
            else:
                self._login = user_input
                self._classes = [str(c) for c in defaults.get("myKlassen") or []]
                return await self.async_step_kid()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): TextSelector(
                            TextSelectorConfig(type=TextSelectorType.URL)
                        ),
                        vol.Required(CONF_USERNAME): TextSelector(
                            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
                        ),
                        vol.Required(CONF_PASSWORD): TextSelector(
                            TextSelectorConfig(
                                type=TextSelectorType.PASSWORD, autocomplete="current-password"
                            )
                        ),
                    }
                ),
                user_input or self._login,
            ),
            errors=errors,
        )

    async def async_step_kid(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            name = user_input[CONF_KID_NAME].strip()
            await self.async_set_unique_id(f"{self._login[CONF_USERNAME]}_{name}".casefold())
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=name,
                data={
                    **self._login,
                    CONF_KID_NAME: name,
                    CONF_CLASS: user_input[CONF_CLASS].strip(),
                },
                options={
                    CONF_POPUP_START: user_input[CONF_POPUP_START],
                    CONF_POPUP_END: user_input[CONF_POPUP_END],
                    CONF_POPUP_DAYS: user_input[CONF_POPUP_DAYS],
                    CONF_ACCENT: DEFAULT_ACCENT,
                },
            )

        return self.async_show_form(
            step_id="kid",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_KID_NAME): TextSelector(),
                    vol.Required(
                        CONF_CLASS, default=self._classes[0] if self._classes else vol.UNDEFINED
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=self._classes,
                            custom_value=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    **_popup_schema({}),
                }
            ),
            description_placeholders={"classes": ", ".join(self._classes) or "–"},
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await _async_fetch_defaults(
                    self.hass,
                    entry.data[CONF_BASE_URL],
                    entry.data[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except StundenplanAuthError:
                errors["base"] = "invalid_auth"
            except StundenplanError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    )
                }
            ),
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return StundenplanOptionsFlow()


class StundenplanOptionsFlow(OptionsFlow):
    """Menu: pop-up window, courses the kid takes, and subject names/colours."""

    def __init__(self) -> None:
        self._options: dict[str, Any] = {}
        self._subject: str = ""

    @property
    def _codes(self) -> list[str]:
        runtime = getattr(self.config_entry, "runtime_data", None)
        return runtime.coordinator.subject_codes if runtime else []

    @property
    def _raw_plan(self) -> list[Any]:
        runtime = getattr(self.config_entry, "runtime_data", None)
        return runtime.coordinator.raw_plan if runtime else []

    def _subject_info(self, code: str) -> dict[str, str]:
        return resolve_subject(code, self._options.get(CONF_SUBJECTS, {}))

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if not self._options:
            self._options = {
                **self.config_entry.options,
                CONF_SUBJECTS: dict(self.config_entry.options.get(CONF_SUBJECTS, {})),
            }
        return self.async_show_menu(
            step_id="init",
            menu_options=["popup", "courses", "subjects", "save"],
            description_placeholders={"kid": self.config_entry.title},
        )

    async def async_step_save(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_create_entry(data=self._options)

    async def async_step_popup(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            self._options.update(user_input)
            self._options[CONF_ACCENT] = _rgb_to_hex(user_input[CONF_ACCENT])
            return await self.async_step_init()

        return self.async_show_form(
            step_id="popup",
            data_schema=vol.Schema(
                {
                    **_popup_schema(self._options),
                    vol.Required(
                        CONF_ACCENT,
                        default=_hex_to_rgb(self._options.get(CONF_ACCENT, DEFAULT_ACCENT)),
                    ): ColorRGBSelector(),
                }
            ),
        )

    async def async_step_courses(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        alternatives = alternative_codes(self._raw_plan)
        if not alternatives:
            return self.async_abort(reason="no_courses")
        if user_input is not None:
            taken = set(user_input[CONF_TAKEN])
            self._options[CONF_HIDDEN] = [c for c in alternatives if c not in taken]
            return await self.async_step_init()

        hidden = set(self._options.get(CONF_HIDDEN, []))
        return self.async_show_form(
            step_id="courses",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TAKEN, default=[c for c in alternatives if c not in hidden]
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=c, label=f"{self._subject_info(c)['name']} ({c})"
                                )
                                for c in alternatives
                            ],
                            multiple=True,
                            mode=SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
            description_placeholders={"kid": self.config_entry.title},
        )

    async def async_step_subjects(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        codes = self._codes
        if not codes:
            return self.async_abort(reason="no_subjects")
        if user_input is not None:
            self._subject = user_input[CONF_SUBJECT]
            return await self.async_step_subject()

        return self.async_show_form(
            step_id="subjects",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SUBJECT): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=c,
                                    label=f"{info['icon']} {info['name']} ({c})".strip(),
                                )
                                for c in codes
                                if (info := self._subject_info(c))
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_subject(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        code = self._subject
        subjects: dict[str, Any] = self._options[CONF_SUBJECTS]
        if user_input is not None:
            if user_input.get(CONF_RESET):
                subjects.pop(code, None)
            else:
                subjects[code] = {
                    "name": user_input["name"].strip() or code,
                    "icon": user_input.get("icon", "").strip(),
                    "color": _rgb_to_hex(user_input["color"]),
                    "hint": user_input.get("hint", "").strip(),
                }
            return await self.async_step_init()

        info = self._subject_info(code)
        return self.async_show_form(
            step_id="subject",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required("name"): TextSelector(),
                        vol.Optional("icon"): TextSelector(),
                        vol.Required("color"): ColorRGBSelector(),
                        vol.Optional("hint"): TextSelector(),
                        vol.Optional(CONF_RESET, default=False): BooleanSelector(),
                    }
                ),
                {**info, "color": _hex_to_rgb(info["color"])},
            ),
            description_placeholders={"code": code},
        )
