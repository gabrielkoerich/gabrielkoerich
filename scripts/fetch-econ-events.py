#!/usr/bin/env python3
"""Generate a subscribable iCalendar feed of US economic events.

Sources (official, machine-readable):
  - FRED release/dates API  -> CPI, PPI, Employment Situation (NFP) release dates
  - Federal Reserve FOMC calendar page -> rate-decision meeting dates

Output: static/us-econ-events.ics  (served at https://gabrielkoerich.com/us-econ-events.ics)

Requires FRED_API_KEY (free: https://fred.stlouisfed.org/docs/api/api_key.html).
Without it, FOMC events are still emitted and FRED-sourced events are skipped.
"""

import datetime as dt
import os
import re
import sys
from pathlib import Path

import requests

OUT = Path(__file__).resolve().parent.parent / "static" / "us-econ-events.ics"
DOMAIN = "gabrielkoerich.com"
TZID = "America/New_York"
HEADERS = {"User-Agent": "Mozilla/5.0 (econ-events-ics; +https://gabrielkoerich.com)"}

# FRED release_id -> (calendar summary, release time in ET, category)
FRED_RELEASES = {
    10: ("CPI — Consumer Price Index", "0830", "Inflation"),
    46: ("PPI — Producer Price Index", "0830", "Inflation"),
    50: ("Employment Situation (NFP)", "0830", "Jobs"),
}

MONTHS = {
    m: i
    for i, m in enumerate(
        ["January", "February", "March", "April", "May", "June", "July",
         "August", "September", "October", "November", "December"], 1)
}

# Standard America/New_York VTIMEZONE (EST/EDT with US DST rules).
VTIMEZONE = """BEGIN:VTIMEZONE
TZID:America/New_York
X-LIC-LOCATION:America/New_York
BEGIN:DAYLIGHT
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
TZNAME:EDT
DTSTART:19700308T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
TZNAME:EST
DTSTART:19701101T020000
RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU
END:STANDARD
END:VTIMEZONE"""


def fred_release_dates(release_id: int, api_key: str) -> list[dt.date]:
    r = requests.get(
        "https://api.stlouisfed.org/fred/release/dates",
        params={
            "release_id": release_id,
            "api_key": api_key,
            "file_type": "json",
            "include_release_dates_with_no_data": "true",
            "sort_order": "asc",
            "limit": 1000,
        },
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    return [dt.date.fromisoformat(x["date"]) for x in r.json().get("release_dates", [])]


def fomc_meeting_dates() -> list[dt.date]:
    """Parse rate-decision dates (second day of each meeting) from the Fed page."""
    html = requests.get(
        "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
        headers=HEADERS,
        timeout=30,
    ).text
    dates: list[dt.date] = []
    for panel in re.finditer(r"(20\d{2}) FOMC Meetings", html):
        year = int(panel.group(1))
        nxt = re.search(r"20\d{2} FOMC Meetings", html[panel.end():])
        chunk = html[panel.end(): panel.end() + nxt.start()] if nxt else html[panel.end():]
        months = [
            re.sub(r"<[^>]+>", " ", m.group(1)).split()[0]
            for m in re.finditer(r"fomc-meeting__month[^>]*>(.*?)</div>", chunk, re.S)
            if re.sub(r"<[^>]+>", " ", m.group(1)).split()
        ]
        ranges = re.findall(r"fomc-meeting__date[^>]*>\s*([0-9/\-]+)", chunk)
        for month_name, rng in zip(months, ranges):
            month = MONTHS.get(month_name)
            day = int(re.findall(r"\d+", rng)[-1])  # decision day = end of range
            if month:
                try:
                    dates.append(dt.date(year, month, day))
                except ValueError:
                    continue
    return dates


def vevent(uid: str, day: dt.date, time_hhmm: str, summary: str, category: str, desc: str) -> str:
    start = f"{day:%Y%m%d}T{time_hhmm}00"
    end_h = f"{int(time_hhmm[:2]) + 1:02d}{time_hhmm[2:]}"
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return "\n".join([
        "BEGIN:VEVENT",
        f"UID:{uid}@{DOMAIN}",
        f"DTSTAMP:{stamp}",
        f"DTSTART;TZID={TZID}:{start}",
        f"DTEND;TZID={TZID}:{end_h}00",
        f"SUMMARY:{summary}",
        f"CATEGORIES:{category}",
        f"DESCRIPTION:{desc}",
        "END:VEVENT",
    ])


def main() -> int:
    api_key = os.environ.get("FRED_API_KEY", "").strip()
    cutoff = dt.date.today() - dt.timedelta(days=30)
    events: list[str] = []

    if api_key:
        for rid, (summary, time_et, cat) in FRED_RELEASES.items():
            try:
                for day in fred_release_dates(rid, api_key):
                    if day >= cutoff:
                        events.append(vevent(
                            f"fred-{rid}-{day:%Y%m%d}", day, time_et, summary, cat,
                            f"{summary} release. Source: FRED release {rid}. Time approximate (ET).",
                        ))
            except Exception as e:  # noqa: BLE001
                print(f"warning: FRED release {rid} failed: {e}", file=sys.stderr)
    else:
        print("warning: FRED_API_KEY not set; skipping CPI/PPI/Employment", file=sys.stderr)

    try:
        for day in fomc_meeting_dates():
            if day >= cutoff:
                events.append(vevent(
                    f"fomc-{day:%Y%m%d}", day, "1400", "FOMC Rate Decision", "Rates",
                    "FOMC policy statement & rate decision (2:00 PM ET), press conference follows.",
                ))
    except Exception as e:  # noqa: BLE001
        print(f"warning: FOMC fetch failed: {e}", file=sys.stderr)

    if not events:
        print("error: no events generated", file=sys.stderr)
        return 1

    cal = "\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//gabrielkoerich//us-econ-events//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:US Economic Events",
        "X-WR-CALDESC:CPI, PPI, Jobs & FOMC rate decisions (official BLS/Fed schedules)",
        f"X-WR-TIMEZONE:{TZID}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
        VTIMEZONE,
        *events,
        "END:VCALENDAR",
        "",
    ])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(cal.replace("\n", "\r\n"))  # RFC 5545 CRLF line endings
    print(f"wrote {len(events)} events -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
