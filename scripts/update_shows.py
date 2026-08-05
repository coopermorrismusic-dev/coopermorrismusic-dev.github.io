#!/usr/bin/env python3
"""Download Cooper's public Google Calendar and build events.json for the website."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

CALENDAR_ID = "6275cc80dd5d91174efcd894cb5f3d571762ccdc852eb62972a631c1bb124ee5@group.calendar.google.com"
LOCAL_ZONE = ZoneInfo("America/Los_Angeles")
PUBLIC_CALENDAR_URL = (
    "https://calendar.google.com/calendar/embed?"
    f"src={urllib.parse.quote(CALENDAR_ID, safe='')}&ctz=America%2FLos_Angeles"
)
ICAL_URL = (
    "https://calendar.google.com/calendar/ical/"
    f"{urllib.parse.quote(CALENDAR_ID, safe='')}/public/basic.ics"
)
OUTPUT_PATH = Path(__file__).resolve().parents[1] / "events.json"


def unfold_ics(text: str) -> list[str]:
    unfolded: list[str] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw_line.startswith((" ", "\t")) and unfolded:
            unfolded[-1] += raw_line[1:]
        else:
            unfolded.append(raw_line)
    return unfolded


def unescape_ics(value: str) -> str:
    return (
        value.replace("\\N", "\n")
        .replace("\\n", "\n")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
        .strip()
    )


def parse_property(line: str) -> tuple[str, dict[str, str], str]:
    left, value = line.split(":", 1)
    pieces = left.split(";")
    name = pieces[0].upper()
    params: dict[str, str] = {}
    for piece in pieces[1:]:
        if "=" in piece:
            key, param_value = piece.split("=", 1)
            params[key.upper()] = param_value.strip('"')
    return name, params, unescape_ics(value)


def parse_datetime(value: str, params: dict[str, str]) -> tuple[datetime, bool]:
    if params.get("VALUE", "").upper() == "DATE" or re.fullmatch(r"\d{8}", value):
        parsed_date = datetime.strptime(value[:8], "%Y%m%d").date()
        return datetime.combine(parsed_date, time.min, LOCAL_ZONE), True

    if value.endswith("Z"):
        parsed = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return parsed.astimezone(LOCAL_ZONE), False

    fmt = "%Y%m%dT%H%M%S" if len(value) >= 15 else "%Y%m%dT%H%M"
    parsed = datetime.strptime(value, fmt)
    tzid = params.get("TZID")
    zone = ZoneInfo(tzid) if tzid else LOCAL_ZONE
    return parsed.replace(tzinfo=zone).astimezone(LOCAL_ZONE), False


def project_details(summary: str) -> tuple[str, str, str, str]:
    normalized = summary.replace(" — ", " - ")
    if " - " in normalized:
        project, remainder = normalized.split(" - ", 1)
    else:
        project, remainder = "Cooper Morris", normalized

    if " @ " in remainder:
        title, venue = remainder.rsplit(" @ ", 1)
    else:
        title, venue = remainder, ""

    haystack = f"{project} {summary}".lower()
    if "tree house" in haystack:
        fallback = "trio-current.webp"
    elif "born of wildfires" in haystack or re.search(r"\bbow\b", haystack):
        fallback = "bow-bennett.webp"
    elif "jen & cooper" in haystack or "jen and cooper" in haystack or "cooper & jen" in haystack:
        fallback = "duo-smittys.webp"
    else:
        fallback = "solo-closeup.webp"

    return project.strip(), title.strip(), venue.strip(), fallback


def extract_directive(description: str, name: str) -> tuple[str, str]:
    pattern = re.compile(rf"(?im)^\s*{re.escape(name)}\s*:\s*(\S+)\s*$")
    match = pattern.search(description)
    value = match.group(1).strip() if match else ""
    cleaned = pattern.sub("", description).strip()
    return value, cleaned


def parse_events(ics_text: str) -> list[dict]:
    events: list[dict] = []
    current: dict[str, list[tuple[dict[str, str], str]]] | None = None

    for line in unfold_ics(ics_text):
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current:
                event = build_event(current)
                if event:
                    events.append(event)
            current = None
            continue
        if current is None or ":" not in line:
            continue

        name, params, value = parse_property(line)
        current.setdefault(name, []).append((params, value))

    now = datetime.now(LOCAL_ZONE) - timedelta(hours=2)
    events = [event for event in events if datetime.fromisoformat(event["end"]) >= now]
    events.sort(key=lambda event: event["start"])
    return events[:40]


def first(fields: dict, name: str) -> tuple[dict[str, str], str] | None:
    values = fields.get(name)
    return values[0] if values else None


def build_event(fields: dict) -> dict | None:
    status = first(fields, "STATUS")
    if status and status[1].upper() == "CANCELLED":
        return None

    start_property = first(fields, "DTSTART")
    if not start_property:
        return None

    start, all_day = parse_datetime(start_property[1], start_property[0])
    end_property = first(fields, "DTEND")
    if end_property:
        end, _ = parse_datetime(end_property[1], end_property[0])
    else:
        end = start + (timedelta(days=1) if all_day else timedelta(hours=2))

    summary_property = first(fields, "SUMMARY")
    summary = summary_property[1] if summary_property else "Live performance"
    location_property = first(fields, "LOCATION")
    location = location_property[1] if location_property else ""
    description_property = first(fields, "DESCRIPTION")
    description = description_property[1] if description_property else ""
    uid_property = first(fields, "UID")
    uid = uid_property[1] if uid_property else f"{summary}-{start.isoformat()}"
    url_property = first(fields, "URL")
    url = url_property[1] if url_property else PUBLIC_CALENDAR_URL

    image, description = extract_directive(description, "IMAGE")
    if not image:
        image, description = extract_directive(description, "PHOTO")
    ticket_url, description = extract_directive(description, "TICKETS")

    project, title, venue, fallback = project_details(summary)

    return {
        "id": uid,
        "summary": summary,
        "project": project,
        "title": title,
        "venue": venue,
        "location": location,
        "description": description,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "all_day": all_day,
        "url": ticket_url or url,
        "image": image,
        "fallback_image": fallback,
    }


def main() -> None:
    request = urllib.request.Request(
        ICAL_URL,
        headers={"User-Agent": "CooperMorrisMusicCalendarSync/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        ics_text = response.read().decode("utf-8-sig")

    payload = {
        "generated_at": datetime.now(LOCAL_ZONE).isoformat(),
        "calendar_id": CALENDAR_ID,
        "events": parse_events(ics_text),
    }

    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload['events'])} upcoming events to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
