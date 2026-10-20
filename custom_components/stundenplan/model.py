"""Turn raw SchuleIntern responses into the timetable shown in Home Assistant.

Kept free of Home Assistant imports so it can be tested on its own.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from .const import DEFAULT_SUBJECTS

DAY_LABELS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
DAY_SHORT = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]

# Used for subjects that have no default and no user colour.
FALLBACK_COLORS = ["#0a84ff", "#30d158", "#ff9f0a", "#bf5af2", "#ff375f", "#64d2ff", "#ffd60a"]

_GROUP_SUFFIX = re.compile(r"_\d+$")


def base_code(code: str) -> str:
    """Strip group suffixes like ``Ph_2`` -> ``Ph``."""
    return _GROUP_SUFFIX.sub("", code)


def subject_codes(plan: list[Any]) -> list[str]:
    """All subject codes that appear in the plan."""
    codes = {
        lesson.get("subject", "")
        for day in plan
        for slot in day
        for lesson in slot
    }
    codes.discard("")
    return sorted(codes, key=str.casefold)


def alternative_codes(plan: list[Any]) -> list[str]:
    """Subject codes taught in parallel with another subject (religion, sport groups, ...)."""
    codes = {
        lesson.get("subject", "")
        for day in plan
        for slot in day
        if len(slot) > 1
        for lesson in slot
    }
    codes.discard("")
    return sorted(codes, key=str.casefold)


def resolve_subject(code: str, overrides: dict[str, dict[str, str]]) -> dict[str, str]:
    """Readable name, icon, colour and hint for a subject code."""
    default = DEFAULT_SUBJECTS.get(code) or DEFAULT_SUBJECTS.get(base_code(code)) or {}
    color = FALLBACK_COLORS[sum(map(ord, base_code(code))) % len(FALLBACK_COLORS)]
    result = {
        "name": default.get("name", code),
        "icon": default.get("icon", ""),
        "color": default.get("color", color),
        "hint": "",
    }
    result.update({k: v for k, v in overrides.get(code, {}).items() if v is not None})
    return result


def _parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%d.%m.%Y").date()
    except (TypeError, ValueError):
        return None


def _clean(value: Any) -> str:
    return str(value or "").replace("\xa0", " ").strip()


def build_timetable(
    defaults: dict[str, Any],
    plan_response: dict[str, Any],
    overrides: dict[str, dict[str, str]],
    hidden: list[str],
    today: date,
) -> dict[str, Any]:
    """Build the timetable for the current week with today's substitutions applied."""
    plan: list[Any] = plan_response.get("plan") or []
    times: list[dict[str, str]] = defaults.get("zeiten") or []

    days: list[dict[str, Any]] = []
    for weekday, raw_day in enumerate(plan[:7]):
        slots = []
        for raw_slot in raw_day:
            slot = []
            for raw in raw_slot:
                code = raw.get("subject", "")
                if not code or code in hidden:
                    continue
                slot.append(
                    {
                        "code": code,
                        **resolve_subject(code, overrides),
                        "room": _clean(raw.get("room")),
                        "teacher": _clean(raw.get("teacher")),
                    }
                )
            slots.append(slot)
        days.append(
            {
                "weekday": weekday,
                "label": DAY_LABELS[weekday],
                "short": DAY_SHORT[weekday],
                "date": None,
                "slots": slots,
            }
        )

    monday = date.fromordinal(today.toordinal() - today.weekday())
    for day in days:
        day["date"] = date.fromordinal(monday.toordinal() + day["weekday"]).isoformat()

    _apply_substitutions(days, plan_response.get("vplan") or [], monday, overrides)

    # Weekends only show up when something is scheduled.
    days = [d for d in days if d["weekday"] < 5 or any(d["slots"])]

    last_period = max(
        (i for d in days for i, slot in enumerate(d["slots"]) if slot),
        default=-1,
    )
    periods = [
        {
            "number": i + 1,
            "start": (times[i] if i < len(times) else {}).get("begin", ""),
            "end": (times[i] if i < len(times) else {}).get("ende", ""),
        }
        for i in range(last_period + 1)
    ]
    for day in days:
        day["slots"] = day["slots"][: last_period + 1]

    today_day = next((d for d in days if d["weekday"] == today.weekday()), None)
    today_lessons = [slot for slot in (today_day or {}).get("slots", []) if slot]
    hints = sorted(
        {lesson["hint"] for slot in today_lessons for lesson in slot if lesson.get("hint")}
    )

    return {
        "title": _clean(plan_response.get("title")),
        "periods": periods,
        "days": days,
        "today": today.isoformat(),
        "today_weekday": today.weekday(),
        "today_lessons": len(today_lessons),
        "today_hints": hints,
        "substitutions": sum(
            1 for d in days for slot in d["slots"] for lesson in slot if lesson.get("change")
        ),
    }


def _apply_substitutions(
    days: list[dict[str, Any]],
    vplan: list[dict[str, Any]],
    monday: date,
    overrides: dict[str, dict[str, str]],
) -> None:
    for entry in vplan:
        entry_date = _parse_date(entry.get("date", ""))
        if entry_date is None:
            continue
        offset = entry_date.toordinal() - monday.toordinal()
        if not 0 <= offset < len(days):
            continue
        try:
            index = int(entry.get("stunde")) - 1
        except (TypeError, ValueError):
            continue
        day = next((d for d in days if d["weekday"] == offset), None)
        if day is None or not 0 <= index < len(day["slots"]):
            continue

        slot = day["slots"][index]
        old_code = _clean(entry.get("fach_alt_kurz"))
        targets = [
            lesson
            for lesson in slot
            if old_code and base_code(lesson["code"]) == base_code(old_code)
        ]
        if not targets and not old_code and len(slot) == 1:
            targets = slot
        if not targets:
            continue

        kind = _clean(entry.get("info_1")) or "Änderung"
        new_code = _clean(entry.get("fach_neu_kurz") or entry.get("fach_neu"))
        change = {
            "kind": kind,
            "cancelled": any(w in kind.casefold() for w in ("entfall", "fällt aus", "frei")),
            "teacher": _clean(entry.get("user_neu_kurz")),
            "room": _clean(entry.get("raum_neu")),
            "subject": resolve_subject(new_code, overrides)["name"] if new_code else "",
            "note": _clean(entry.get("info_2")),
        }
        for lesson in targets:
            lesson["change"] = change
