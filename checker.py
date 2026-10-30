"""Read public Booksy availability; never continue or submit a booking."""
from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime
from pathlib import Path
import re
import time
from zoneinfo import ZoneInfo

URL = "https://booksy.com/en-gb/6035_savills-barbers_barber_1419956_sheffield"
LONDON = ZoneInfo("Europe/London")
EMPTY = "There is no availability left on this date"
WORKDAYS = {1, 2, 3, 4, 5}  # Python Monday = 0.


def build_result(target: date, checked: datetime, state: str, slots=(), detail=""):
    clean = sorted(set(slots))
    if any(not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", t) for t in clean):
        raise ValueError("Unexpected time format; refusing to publish slots")
    if state == "available" and not clean:
        raise ValueError("Available result must contain at least one time")
    if state != "available" and clean:
        raise ValueError("Only an available result can contain times")
    header = f"Trevor · {target.strftime('%a %d %b')}"
    if state == "available":
        noun = "start time" if len(clean) == 1 else "start times"
        message = f"{header}\n{len(clean)} haircut {noun} available: {', '.join(clean)}."
    elif state == "no_online_availability":
        message = f"{header}\nNo online haircut availability showing for this date."
    elif state == "day_off":
        message = f"{header}\nNot a regular working day (Tuesday–Saturday)."
    else:
        message = f"{header}\nCouldn't verify today's availability. Please check Booksy."
    message += f"\nChecked {checked.astimezone(LONDON).strftime('%H:%M')} UK time."
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
            day.click()
            initial = settle(frame)
            validate_snapshot(initial, target, require_staff=False)
            if initial["empty"]:
                # No preference has no slots: no barber offers this service today.
                return [], "No-preference search also returned no availability."
            frame.get_by_role("button", name="Change", exact=True).click()
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
                    (diagnostics / "widget.txt").write_text(frame.locator("body").inner_text(timeout=3000), encoding="utf-8")
            except Exception:
                pass
            raise
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=date.fromisoformat, help="Optional diagnostic date within the displayed week")
    parser.add_argument("--output", default="status.json")
    args = parser.parse_args()
    started = datetime.now(LONDON)
    target = args.date or started.date()
    diagnostics = Path("diagnostics")
    if target.weekday() not in WORKDAYS:
        result = build_result(target, started, "day_off")
    else:
        try:
            times, detail = check(target, diagnostics)
            result = build_result(target, datetime.now(LONDON), "available" if times else "no_online_availability", times, detail)
        except Exception as exc:
            # Never substitute old data, another barber, or 'fully booked' for a failure.
            result = build_result(target, datetime.now(LONDON), "error", detail=type(exc).__name__)
            print(f"CHECK FAILED: {type(exc).__name__}: {exc}")
    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(result["message"])
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write("## Trevor's public availability\n\n" + result["message"] + "\n\nStatus: **" + result["status"] + "**\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
