"""Constants for the Stundenplan integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "stundenplan"

DEFAULT_BASE_URL: Final = "https://www.rsdintern.de"
UPDATE_INTERVAL: Final = timedelta(minutes=15)

CONF_BASE_URL: Final = "base_url"
CONF_KID_NAME: Final = "kid_name"
CONF_CLASS: Final = "school_class"

# Options
CONF_POPUP_START: Final = "popup_start"
CONF_POPUP_END: Final = "popup_end"
CONF_POPUP_DAYS: Final = "popup_days"
CONF_ACCENT: Final = "accent_color"
CONF_SUBJECTS: Final = "subjects"
CONF_HIDDEN: Final = "hidden_subjects"

DEFAULT_POPUP_START: Final = "06:30:00"
DEFAULT_POPUP_END: Final = "07:00:00"
DEFAULT_POPUP_DAYS: Final = ["mon", "tue", "wed", "thu", "fri"]
DEFAULT_ACCENT: Final = "#0a84ff"

WEEKDAYS: Final = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

FRONTEND_URL: Final = "/stundenplan_frontend"
CARD_FILENAME: Final = "stundenplan-card.js"

# Readable defaults for subject codes used at Bavarian Realschulen. Every value
# can be overridden per kid in the integration options.
DEFAULT_SUBJECTS: Final[dict[str, dict[str, str]]] = {
    "B": {"name": "Biologie", "icon": "🌱", "color": "#30d158"},
    "BWR": {"name": "BwR", "icon": "📊", "color": "#64d2ff"},
    "Ch": {"name": "Chemie", "icon": "⚗️", "color": "#bf5af2"},
    "D": {"name": "Deutsch", "icon": "📖", "color": "#ff453a"},
    "D-Diff": {"name": "Deutsch Förderung", "icon": "📖", "color": "#ff6961"},
    "E": {"name": "Englisch", "icon": "🇬🇧", "color": "#0a84ff"},
    "Eth": {"name": "Ethik", "icon": "💭", "color": "#ac8e68"},
    "Ev": {"name": "Ev. Religion", "icon": "✝️", "color": "#ac8e68"},
    "F": {"name": "Französisch", "icon": "🇫🇷", "color": "#5e5ce6"},
    "G": {"name": "Geschichte", "icon": "🏛️", "color": "#ff9f0a"},
    "Geo": {"name": "Erdkunde", "icon": "🌍", "color": "#32ade6"},
    "IR": {"name": "Islam. Unterricht", "icon": "☪️", "color": "#ac8e68"},
    "IT": {"name": "IT", "icon": "💻", "color": "#5e5ce6"},
    "K": {"name": "Kath. Religion", "icon": "✝️", "color": "#ac8e68"},
    "Ku": {"name": "Kunst", "icon": "🎨", "color": "#ff375f"},
    "M": {"name": "Mathe", "icon": "📐", "color": "#0a84ff"},
    "Mu": {"name": "Musik", "icon": "🎵", "color": "#ff375f"},
    "Ph": {"name": "Physik", "icon": "🧲", "color": "#bf5af2"},
    "Sm": {"name": "Sport (Jungen)", "icon": "⚽", "color": "#ffd60a"},
    "Sw": {"name": "Sport (Mädchen)", "icon": "🏐", "color": "#ffd60a"},
    "WR": {"name": "Wirtschaft & Recht", "icon": "⚖️", "color": "#64d2ff"},
}
