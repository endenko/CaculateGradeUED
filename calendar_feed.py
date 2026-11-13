# -*- coding: utf-8 -*-
"""Private ICS feed and optional Google Calendar OAuth.

The feed token is the only server copy of a schedule. OAuth runs only when
GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are set.
"""
from __future__ import annotations

import json
import os
import secrets
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

import db

SCOPES = "https://www.googleapis.com/auth/calendar.events"


def ensure_tables():
    conn = db.get_db()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS calendar_feed (
                token TEXT PRIMARY KEY,
                schedule_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS google_calendar (
                session_id TEXT PRIMARY KEY,
                refresh_token TEXT NOT NULL,
                calendar_id TEXT,
                updated_at TEXT NOT NULL
            );
        """)
        conn.commit()
    finally:
        conn.close()


def oauth_enabled() -> bool:
    return bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"))


def save_feed(schedule: dict, previous: str = "") -> str:
    ensure_tables()
    token = secrets.token_urlsafe(24)
    conn = db.get_db()
    try:
        if previous:
            conn.execute("UPDATE calendar_feed SET revoked=1 WHERE token=?", (previous,))
        conn.execute(
            "INSERT INTO calendar_feed (token, schedule_json, created_at, revoked) VALUES (?,?,?,0)",
            (token, json.dumps(schedule, ensure_ascii=False), datetime.utcnow().isoformat(timespec="seconds")),
        )
        conn.commit()
    finally:
        conn.close()
    return token


def revoke_feed(token: str) -> None:
    ensure_tables()
    conn = db.get_db()
    try:
        conn.execute("UPDATE calendar_feed SET revoked=1 WHERE token=?", (token,))
        conn.commit()
    finally:
        conn.close()


def load_feed(token: str):
    ensure_tables()
    conn = db.get_db()
    try:
        row = conn.execute(
            "SELECT schedule_json FROM calendar_feed WHERE token=? AND revoked=0",
            (token,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return json.loads(row["schedule_json"])


def _ics_escape(value) -> str:
    return str(value or "").replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y%m%dT%H%M%S")


def _monday(day: int, week_start: datetime, week: int) -> datetime:
    """Tuần 1 bắt đầu từ week_start, treated as Thứ 2 of that week."""
    base = week_start + timedelta(days=7 * (week - 1))
    offset = 6 if day == 8 else day - 2
    return base + timedelta(days=offset)


def _parse_date(text: str):
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _clock(text: str, fallback: str) -> tuple[int, int]:
    raw = text or fallback
    hour, minute = raw.split(":")
    return int(hour), int(minute)


def iter_events(schedule: dict):
    """Yield dated events. Week 1's Thứ 2 is week_start."""
    week_start = _parse_date(schedule.get("week_start") or schedule.get("start") or "") or datetime(2026, 8, 17)
    for item in schedule.get("classes") or []:
        weeks = item.get("weeks") or item.get("tuan") or list(range(1, 16))
        day = int(item.get("day") or item.get("thu") or 2)
        sh, sm = _clock(item.get("start"), "07:00")
        eh, em = _clock(item.get("end"), "07:50")
        for week in weeks:
            day_date = _monday(day, week_start, int(week))
            begin = day_date.replace(hour=sh, minute=sm, second=0)
            end = day_date.replace(hour=eh, minute=em, second=0)
            yield {
                "uid": f"{item.get('id') or 'class'}-w{week}",
                "summary": item.get("name") or item.get("ten_mon") or "Lịch học",
                "location": item.get("room") or item.get("phong") or "",
                "description": item.get("lecturer") or item.get("giang_vien") or "",
                "start": begin,
                "end": end,
                "alarms": ["-PT15M"],
            }
    for item in schedule.get("exams") or []:
        moment = None
        if item.get("at"):
            try:
                moment = datetime.fromisoformat(item["at"])
            except ValueError:
                moment = None
        if moment is None and item.get("ngay"):
            moment = _parse_date(item["ngay"])
            if moment and item.get("gio"):
                hour, minute = _clock(item["gio"], "07:30")
                moment = moment.replace(hour=hour, minute=minute)
        if moment is None:
            continue
        yield {
            "uid": str(item.get("id") or "exam"),
            "summary": ("Thi " + (item.get("name") or item.get("ten_mon") or "")).strip(),
            "location": item.get("room") or item.get("phong") or "",
            "description": item.get("hinh_thuc") or "",
            "start": moment,
            "end": moment + timedelta(minutes=90),
            "alarms": ["-P1D", "-PT1H"],
        }


def build_ics(schedule: dict) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//UED//Tinh diem//VI",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:UED",
    ]
    for event in iter_events(schedule):
        lines += [
            "BEGIN:VEVENT",
            f"UID:{_ics_escape(event['uid'])}@ued-tinh-diem",
            f"SUMMARY:{_ics_escape(event['summary'])}",
            f"LOCATION:{_ics_escape(event['location'])}",
            f"DESCRIPTION:{_ics_escape(event['description'])}",
            f"DTSTART:{_stamp(event['start'])}",
            f"DTEND:{_stamp(event['end'])}",
        ]
        for trigger in event["alarms"]:
            lines += [
                "BEGIN:VALARM",
                f"TRIGGER:{trigger}",
                "ACTION:DISPLAY",
                "DESCRIPTION:Nhắc lịch UED",
                "END:VALARM",
            ]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def _post(url, data, headers=None):
    body = urllib.parse.urlencode(data).encode()
    request = urllib.request.Request(url, data=body, headers=headers or {})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode())


def _json_request(url, payload, token):
    body = json.dumps(payload).encode()
    request = urllib.request.Request(
        url, data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read().decode()
        return json.loads(raw) if raw else {}


def auth_url(redirect_uri: str, state: str) -> str:
    query = urllib.parse.urlencode({
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    })
    return "https://accounts.google.com/o/oauth2/v2/auth?" + query


def exchange_code(code: str, redirect_uri: str) -> dict:
    return _post("https://oauth2.googleapis.com/token", {
        "code": code,
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    })


def refresh_access(refresh_token: str) -> str:
    data = _post("https://oauth2.googleapis.com/token", {
        "refresh_token": refresh_token,
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
        "grant_type": "refresh_token",
    })
    return data["access_token"]


def save_google(session_id: str, refresh_token: str, calendar_id: str = ""):
    ensure_tables()
    conn = db.get_db()
    try:
        conn.execute(
            """INSERT INTO google_calendar (session_id, refresh_token, calendar_id, updated_at)
               VALUES (?,?,?,?)
               ON CONFLICT(session_id) DO UPDATE SET
                 refresh_token=excluded.refresh_token,
                 calendar_id=COALESCE(NULLIF(excluded.calendar_id, ''), google_calendar.calendar_id),
                 updated_at=excluded.updated_at""",
            (session_id, refresh_token, calendar_id or "", datetime.utcnow().isoformat(timespec="seconds")),
        )
        conn.commit()
    finally:
        conn.close()


def google_session(session_id: str):
    ensure_tables()
    conn = db.get_db()
    try:
        return conn.execute("SELECT * FROM google_calendar WHERE session_id=?", (session_id,)).fetchone()
    finally:
        conn.close()


def ensure_ued_calendar(access_token: str, current: str = "") -> str:
    if current:
        return current
    request = urllib.request.Request(
        "https://www.googleapis.com/calendar/v3/users/me/calendarList",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        listing = json.loads(response.read().decode())
    for item in listing.get("items") or []:
        if item.get("summary") == "UED":
            return item["id"]
    created = _json_request(
        "https://www.googleapis.com/calendar/v3/calendars",
        {"summary": "UED", "timeZone": "Asia/Ho_Chi_Minh"},
        access_token,
    )
    return created["id"]


def sync_events(session_id: str, schedule: dict) -> int:
    row = google_session(session_id)
    if not row:
        raise PermissionError("Chưa kết nối Google Calendar")
    access = refresh_access(row["refresh_token"])
    calendar_id = ensure_ued_calendar(access, row["calendar_id"] or "")
    if calendar_id != (row["calendar_id"] or ""):
        save_google(session_id, row["refresh_token"], calendar_id)
    count = 0
    for block in iter_events(schedule):
        _json_request(
            f"https://www.googleapis.com/calendar/v3/calendars/{urllib.parse.quote(calendar_id)}/events",
            {
                "summary": block["summary"],
                "location": block["location"],
                "description": block["description"],
                "start": {"dateTime": block["start"].isoformat(), "timeZone": "Asia/Ho_Chi_Minh"},
                "end": {"dateTime": block["end"].isoformat(), "timeZone": "Asia/Ho_Chi_Minh"},
                "reminders": {"useDefault": False, "overrides": [
                    {"method": "popup", "minutes": 15 if trigger == "-PT15M" else (60 if trigger == "-PT1H" else 24 * 60)}
                    for trigger in block["alarms"]
                ]},
            },
            access,
        )
        count += 1
    return count
