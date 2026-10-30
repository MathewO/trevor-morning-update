"""Read public Booksy availability; never continue or submit a booking."""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
import re
import time
from zoneinfo import ZoneInfo

URL = "https://booksy.com/en-gb/6035_savills-barbers_barber_1419956_sheffield"
LONDON = ZoneInfo("Europe/London")
EMPTY = "There is no availability left on this date"
WORKDAYS = {1, 2, 3, 4, 5}  # Python Monday = 0.


def availability_text(state, slots):
    if state == "available":
        noun = "slot" if len(slots) == 1 else "slots"
        return f"{len(slots)} × 30-minute haircut {noun} available: {', '.join(slots)}."
    if state == "no_online_availability":
        return "No 30-minute haircut slots available online."
    if state == "day_off":
        return "Day off (regular working days: Tuesday–Saturday)."
    return "Couldn't verify availability. Please check Booksy."


def build_result(target: date, checked: datetime, state: str, slots=(), detail=""):
    clean = sorted(set(slots))
    if any(not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", t) for t in clean):
        raise ValueError("Unexpected time format; refusing to publish slots")
    if state == "available" and not clean:
        raise ValueError("Available result must contain at least one time")
    if state != "available" and clean:
        raise ValueError("Only an available result can contain times")
    header = f"Trevor · {target.strftime('%a %d %b')}"
    message = f"{header}\n{availability_text(state, clean)}"
    message += f"\nAI Checked @ {checked.astimezone(LONDON).strftime('%H:%M')} UK time"
    return {
        "schema_version": 1,
        "date": target.isoformat(),
        "checked_at": checked.astimezone(LONDON).isoformat(timespec="seconds"),
        "timezone": "Europe/London",
        "ok": state in {"available", "no_online_availability", "day_off"},
        "status": state,
        "staff": "Trevor",
        "service": "Hair Cut",
        "duration_minutes": 30,
        "available_start_times": clean,
        "available_start_count": len(clean) if state == "available" else (0 if state == "no_online_availability" else None),
        "message": message,
        "source_url": URL,
        "note": "Public bookable start times, not a count of confirmed bookings. Breaks and blocked time are not distinguishable.",
        "detail": detail,
    }


def build_feed(target: date, checked: datetime, days):
    expected_dates = [(target + timedelta(days=i)).isoformat() for i in range(2)]
    if [day["date"] for day in days] != expected_dates:
        raise ValueError("The feed must contain today and tomorrow, in order")
    ok = all(day["ok"] for day in days)
    sections = ["Trevor · Today & Tomorrow"]
    for label, day in zip(("Today", "Tomorrow"), days):
        day_date = date.fromisoformat(day["date"])
        sections.append(f"{label} · {day_date:%a %d %b}\n" + availability_text(day["status"], day["available_start_times"]))
    sections.append(f"AI Checked @ {checked.astimezone(LONDON):%H:%M} UK time")
    return {
        "schema_version": 2,
        "date": target.isoformat(),
        "checked_at": checked.astimezone(LONDON).isoformat(timespec="seconds"),
        "timezone": "Europe/London",
        "ok": ok,
        "status": "ok" if ok else ("partial_error" if any(day["ok"] for day in days) else "error"),
        "staff": "Trevor",
        "service": "Hair Cut",
        "duration_minutes": 30,
        "days": days,
        "message": "\n\n".join(sections),
        "source_url": URL,
        "note": "Public bookable start times, not a count of confirmed bookings. Breaks and blocked time are not distinguishable.",
    }


def validate_snapshot(snapshot, target, require_staff=True):
    expected = f"weekday-button-{target:%d-%m}"
    if snapshot["selected_date"] != expected:
        raise ValueError("The booking widget selected a different date")
    if str(target.year) not in snapshot["body"]:
        raise ValueError("The booking widget's year could not be verified")
    if require_staff and snapshot["staff"] != "Trevor":
        raise ValueError("Trevor's selected staff label could not be verified")
    if snapshot["empty"]:
        return []
    if "Hair Cut" not in snapshot["body"] or "30min" not in snapshot["body"]:
        raise ValueError("The selected service or its duration changed")
    times = snapshot["times"]
    if not times:
        raise ValueError("No times and no explicit empty-state message")
    if any(not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", t) for t in times):
        raise ValueError("Unexpected time format")
    return sorted(set(times))


def snapshot(frame):
    active = frame.locator('[data-testid^="weekday-button-"].active')
    staff = frame.get_by_test_id("participant-label-name")
    body = frame.locator("body").inner_text(timeout=5000)
    return {
        "selected_date": active.get_attribute("data-testid") if active.count() == 1 else None,
        "staff": staff.inner_text().strip() if staff.count() == 1 else None,
        "empty": EMPTY in body,
        "times": [s.strip() for s in frame.locator('.time-slot-container a[data-testid^="time-slot-"]').all_text_contents()],
        "body": body,
    }


def settle(frame, seconds=3, timeout=35):
    """Wait for the visible selection and results to remain stable after a change."""
    deadline = time.monotonic() + timeout
    last, stable_since = None, time.monotonic()
    while time.monotonic() < deadline:
        current = snapshot(frame)
        ready = current["selected_date"] and (current["empty"] or current["times"])
        if current != last or not ready:
            last, stable_since = current, time.monotonic()
        elif time.monotonic() - stable_since >= seconds:
            return current
        time.sleep(0.5)
    raise TimeoutError("Booking widget did not produce stable results")


def check(target, diagnostics):
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="en-GB", timezone_id="Europe/London", viewport={"width":1280,"height":900})
        page = context.new_page()
        page.set_default_timeout(25000)
        frame = None
        try:
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            deny = page.get_by_role("button", name="Deny", exact=True)
            try:
                deny.wait_for(state="visible", timeout=5000)
                deny.click()
            except PWTimeout:
                pass
            page.get_by_role("button", name="Book Hair Cut", exact=True).click()
            widget = page.locator('iframe[title="Booking widget"]')
            widget.wait_for(state="visible")
            frame = page.frame_locator('iframe[title="Booking widget"]')
            day = frame.get_by_test_id(f"weekday-button-{target:%d-%m}")
            day.wait_for(state="visible")
            initial = settle(frame)
            if initial["selected_date"] != f"weekday-button-{target:%d-%m}":
                day.click()
                initial = settle(frame)
            validate_snapshot(initial, target, require_staff=False)
            if initial["empty"]:
                # No preference has no slots: no barber offers this service today.
                return [], "No-preference search also returned no availability."
            frame.locator("button.change-button").click()
            frame.get_by_text("Choose Staffer", exact=True).wait_for(state="visible")
            frame.get_by_text("Trevor", exact=True).click()
            frame.get_by_text("Choose Staffer", exact=True).wait_for(state="hidden")
            selected = settle(frame)
            # Changing staff can change the date; explicitly reselect the target.
            if selected["selected_date"] != f"weekday-button-{target:%d-%m}":
                day.click()
                selected = settle(frame)
            times = validate_snapshot(selected, target, require_staff=not selected["empty"])
            diagnostics.mkdir(parents=True, exist_ok=True)
            widget.screenshot(path=str(diagnostics / "verified-widget.png"))
            return times, "Selected Trevor and verified date and 30-minute Hair Cut service."
        except Exception:
            diagnostics.mkdir(parents=True, exist_ok=True)
            try:
                page.screenshot(path=str(diagnostics / "failure.png"), full_page=False)
                # Only the public widget or a short error description is logged.
                if frame is not None:
                    widget_text = frame.locator("body").inner_text(timeout=3000)
                    (diagnostics / "widget.txt").write_text(widget_text, encoding="utf-8")
                    print("PUBLIC WIDGET AT FAILURE:\n" + widget_text[:4000])
                    print("VISIBLE BUTTON LABELS:", frame.locator("button").all_text_contents())
            except Exception:
                pass
            raise
        finally:
            browser.close()


def check_day(target, diagnostics):
    if target.weekday() not in WORKDAYS:
        return build_result(target, datetime.now(LONDON), "day_off")
    try:
        times, detail = check(target, diagnostics / target.isoformat())
        return build_result(target, datetime.now(LONDON), "available" if times else "no_online_availability", times, detail)
    except Exception as exc:
        # A failed day must not erase the other day or borrow its times.
        print(f"CHECK FAILED ({target}): {type(exc).__name__}: {exc}")
        return build_result(target, datetime.now(LONDON), "error", detail=type(exc).__name__)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=date.fromisoformat, help="Optional diagnostic start date; also checks the next day")
    parser.add_argument("--output", default="status.json")
    args = parser.parse_args()
    target = args.date or datetime.now(LONDON).date()
    days = [check_day(target + timedelta(days=i), Path("diagnostics")) for i in range(2)]
    result = build_feed(target, datetime.now(LONDON), days)
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(result["message"])
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write("## Trevor's public availability\n\n" + result["message"].replace("\n", "  \n") + "\n\nStatus: **" + result["status"] + "**\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
