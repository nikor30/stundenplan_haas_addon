# Stundenplan for Home Assistant

A Home Assistant integration that reads your kids' school timetables from a
[SchuleIntern](https://www.schule-intern.de/) parent portal (for example
[RSDintern](https://www.rsdintern.de)) and shows them as a pop-up on a wall
tablet at fixed times: Adrian's plan from 06:30 to 07:00, Niko's from 07:00 to
07:30, with today highlighted and today's substitutions marked.

## Features

- **One entry per kid**, each with its own class and pop-up time window.
- **Pop-up card**: a frosted sheet slides up over the dashboard while the window
  is open, highlights today's column and the current lesson, and closes by itself
  at the end of the window. Swipe it down or tap ✕ to close it early; it stays
  closed until the next day.
- **Substitutions** (Vertretungen, Entfall, room changes) from the portal are shown
  in today's column, plus a count in the header.
- **Readable subjects**: codes like `BWR` or `Ph_2` become names with an emoji and
  colour. You can rename and recolour every subject, and add a hint such as
  "Sportsachen mitnehmen" that appears on days with that subject.
- **Courses taken**: parallel courses (religion/ethics, sport groups, ...) can be
  reduced to the ones your kid actually attends.
- Works on phones too: the sheet becomes a bottom sheet, and it supports
  dark mode, reduced motion, reduced transparency and increased contrast.

## Installation

### HACS (recommended)

1. In Home Assistant, open **HACS**.
2. Open the menu (⋮) in the top right and choose **Custom repositories**.
3. Add `https://github.com/nikor30/stundenplan_haas_addon` with the category **Integration**.
4. Search for **Stundenplan**, download it, and restart Home Assistant.

### Manual

Copy `custom_components/stundenplan` into the `custom_components` folder of your
Home Assistant configuration and restart Home Assistant.

## Setup

1. **Settings → Devices & services → Add integration → Stundenplan.**
2. Enter the portal address (default `https://www.rsdintern.de`) and the parent
   login.
3. Enter the kid's name, pick the class, and set the pop-up window and weekdays.
4. For another kid, add the integration again (the same login works).

The password is stored in Home Assistant's config entry like any other
integration's credentials. It is only sent to the portal you entered.

### Add the card to the tablet's dashboard

Add a card in YAML mode to the dashboard the kitchen tablet shows:

```yaml
type: custom:stundenplan-card
```

The card is invisible on the dashboard (you only see a placeholder while editing)
and slides up during each kid's window. Only dashboards that contain the card
show the pop-up, so other devices aren't interrupted. The card is loaded
automatically; you don't need to add a resource.

Options:

| Option     | Default       | Description                                                    |
| ---------- | ------------- | -------------------------------------------------------------- |
| `mode`     | `popup`       | `popup` for the timed sheet, `inline` for a normal card        |
| `entities` | all timetable | List of `sensor.*` timetable entities to include               |
| `scale`    | `1`           | Size factor for the pop-up and its width, e.g. `1.5`           |

```yaml
# A regular timetable card, e.g. for a parent's phone dashboard
type: custom:stundenplan-card
mode: inline
```

### Customise subjects

**Settings → Devices & services → Stundenplan → Configure** on a kid's entry opens
a menu:

- **Pop-up & colour**: time window, weekdays, accent colour.
- **Courses taken**: tick the parallel courses the kid attends.
- **Rename & colour subjects**: pick a subject, then set its name, emoji, colour
  and hint.
- **Save** applies all changes.

## Entities

For each kid (the entity IDs depend on the kid's name and your language):

| Entity                                 | Purpose                                                       |
| -------------------------------------- | ------------------------------------------------------------- |
| `sensor.<kid>_stundenplan`             | Number of lessons today; the full week is in its attributes   |
| `binary_sensor.<kid>_pop_up`           | On while the pop-up window is open; usable in automations     |
| `switch.<kid>_pop_up_nach_zeitplan`    | Turn the scheduled pop-up off, e.g. during school holidays    |
| `button.<kid>_pop_up_jetzt_zeigen`     | Show the pop-up now for five minutes (handy for testing)      |

The timetable is refreshed every 15 minutes.

## Development

```bash
python -m venv .venv
.venv/bin/pip install -r requirements_test.txt
.venv/bin/pytest
```

## License

_TBD_
