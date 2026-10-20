"""Shared fixtures: a small made-up class timetable in the portal's response format."""

from __future__ import annotations

from unittest.mock import patch

import pytest

DEFAULTS = {
    "zeiten": [
        {"begin": "08:00", "ende": "08:45"},
        {"begin": "08:45", "ende": "09:30"},
        {"begin": "09:45", "ende": "10:30"},
    ],
    "myKlassen": ["5A"],
    "daynum": "2",
    "userType": "isEltern",
}


def _lesson(subject: str, teacher: str = "ABC", room: str = "101") -> dict[str, str]:
    return {"subject": subject, "teacher": teacher, "room": room, "grade": "5A"}


PLAN = {
    "title": "Klasse: 5A",
    "plan": [
        [[_lesson("M")], [_lesson("D")], []],
        [[_lesson("E")], [_lesson("Ev"), _lesson("Eth"), _lesson("K")], [_lesson("Ph_2")]],
        [[_lesson("Sm"), _lesson("Sw")], [], []],
        [[_lesson("XY")], [], []],
        [[_lesson("M")], [_lesson("M")], []],
        [[], [], []],
        [[], [], []],
    ],
    "vplan": [],
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture
def mock_portal():
    with (
        patch(
            "custom_components.stundenplan.api.SchuleInternClient.async_login",
            return_value=None,
        ),
        patch(
            "custom_components.stundenplan.api.SchuleInternClient.async_get_defaults",
            return_value=DEFAULTS,
        ),
        patch(
            "custom_components.stundenplan.api.SchuleInternClient.async_get_plan",
            return_value=PLAN,
        ) as get_plan,
    ):
        yield get_plan
