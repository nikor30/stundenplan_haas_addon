"""Timetable building, independent of Home Assistant."""

from datetime import date

from custom_components.stundenplan.model import alternative_codes, build_timetable

from .conftest import DEFAULTS, PLAN

TUESDAY = date(2026, 10, 20)


def test_week_layout() -> None:
    t = build_timetable(DEFAULTS, PLAN, {}, [], TUESDAY)
    assert [d["short"] for d in t["days"]] == ["Mo", "Di", "Mi", "Do", "Fr"]
    assert t["days"][0]["date"] == "2026-10-19"
    assert [p["start"] for p in t["periods"]] == ["08:00", "08:45", "09:45"]
    assert t["today_weekday"] == 1
    assert t["today_lessons"] == 3


def test_names_overrides_and_unknown_codes() -> None:
    t = build_timetable(DEFAULTS, PLAN, {"M": {"name": "Mathematik", "hint": "Zirkel"}}, [], date(2026, 10, 23))
    friday = t["days"][4]
    assert friday["slots"][0][0]["name"] == "Mathematik"
    assert t["today_hints"] == ["Zirkel"]
    # Group suffixes fall back to the base subject, unknown codes stay as they are.
    assert t["days"][1]["slots"][2][0]["name"] == "Physik"
    assert t["days"][3]["slots"][0][0]["name"] == "XY"


def test_hidden_courses() -> None:
    assert alternative_codes(PLAN["plan"]) == ["Eth", "Ev", "K", "Sm", "Sw"]
    t = build_timetable(DEFAULTS, PLAN, {}, ["Eth", "K", "Sw"], TUESDAY)
    assert [l["code"] for l in t["days"][1]["slots"][1]] == ["Ev"]
    assert [l["code"] for l in t["days"][2]["slots"][0]] == ["Sm"]


def test_substitution_applied_to_matching_lesson() -> None:
    plan = {
        **PLAN,
        "vplan": [
            {
                "date": "20.10.2026",
                "stunde": "2",
                "fach_alt_kurz": "Eth",
                "info_1": "Entfall",
                "user_neu_kurz": "",
                "raum_neu": "",
            },
            {"date": "27.10.2026", "stunde": "1", "fach_alt_kurz": "E", "info_1": "Vertretung"},
        ],
    }
    t = build_timetable(DEFAULTS, plan, {}, [], TUESDAY)
    slot = {l["code"]: l for l in t["days"][1]["slots"][1]}
    assert slot["Eth"]["change"]["cancelled"] is True
    assert "change" not in slot["Ev"]
    # Next week's entry is ignored.
    assert "change" not in t["days"][1]["slots"][0][0]
    assert t["substitutions"] == 1
