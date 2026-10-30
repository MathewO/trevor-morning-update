import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from checker import build_feed, build_result, check_day, validate_snapshot, LONDON


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.day = date(2026, 10, 30)
        self.now = datetime(2026, 10, 30, 6, 17, tzinfo=LONDON)
        self.snap = {"selected_date":"weekday-button-30-10", "staff":"Trevor", "empty":False, "times":["17:30", "13:30", "17:30"], "body":"October - November 2026 Hair Cut 30min"}

    def test_deduplicates_without_inventing_bookings(self):
        times = validate_snapshot(self.snap, self.day)
        self.assertEqual(times, ["13:30", "17:30"])
        result = build_result(self.day, self.now, "available", times)
        self.assertEqual(result["available_start_count"], 2)
        self.assertNotIn("booked", result["message"])

    def test_rejects_other_barber(self):
        self.snap["staff"] = "No preference"
        with self.assertRaises(ValueError):
            validate_snapshot(self.snap, self.day)

    def test_rejects_other_date_or_year(self):
        for key, value in [("selected_date", "weekday-button-31-10"), ("body", "October 2027 Hair Cut 30min")]:
            wrong = dict(self.snap, **{key:value})
            with self.assertRaises(ValueError):
                validate_snapshot(wrong, self.day)

    def test_unloaded_page_is_not_a_full_day(self):
        self.snap["times"] = []
        with self.assertRaises(ValueError):
            validate_snapshot(self.snap, self.day)
        self.snap["empty"] = True
        self.assertEqual(validate_snapshot(self.snap, self.day), [])

    def test_invalid_times_rejected(self):
        self.snap["times"] = ["29:99"]
        with self.assertRaises(ValueError):
            validate_snapshot(self.snap, self.day)

    def test_failure_is_explicit_and_has_no_stale_times(self):
        result = build_result(self.day, self.now, "error")
        self.assertFalse(result["ok"])
        self.assertEqual(result["available_start_times"], [])
        self.assertIsNone(result["available_start_count"])
        self.assertIn("Couldn't verify", result["message"])

    def test_london_daylight_saving_offsets(self):
        summer = build_result(date(2026, 7, 1), datetime(2026, 7, 1, 6, 17, tzinfo=LONDON), "day_off")
        winter = build_result(self.day, self.now, "day_off")
        self.assertTrue(summer["checked_at"].endswith("+01:00"))
        self.assertTrue(winter["checked_at"].endswith("+00:00"))

    def test_today_and_tomorrow_keep_their_own_times(self):
        days = [build_result(self.day, self.now, "available", ["17:30"]),
                build_result(self.day + timedelta(days=1), self.now, "available", ["11:30", "14:00"])]
        feed = build_feed(self.day, self.now, days)
        self.assertTrue(feed["ok"])
        self.assertEqual(feed["date"], "2026-10-30")
        self.assertIn("Today · Fri 30 Oct\n1 × 30-minute haircut slot available: 17:30.", feed["message"])
        self.assertIn("Tomorrow · Sat 31 Oct\n2 × 30-minute haircut slots available: 11:30, 14:00.", feed["message"])

    def test_tomorrow_failure_keeps_today_but_marks_feed_incomplete(self):
        with patch("checker.check", side_effect=[(["17:30"], "verified"), TimeoutError("test timeout")]):
            days = [check_day(self.day + timedelta(days=i), Path("diagnostics")) for i in range(2)]
        feed = build_feed(self.day, self.now, days)
        self.assertFalse(feed["ok"])
        self.assertEqual(feed["status"], "partial_error")
        self.assertEqual(feed["days"][0]["available_start_times"], ["17:30"])
        self.assertEqual(feed["days"][1]["available_start_times"], [])
        self.assertIn("Tomorrow · Sat 31 Oct\nCouldn't verify availability", feed["message"])

    def test_sunday_is_day_off_without_requesting_booksy(self):
        saturday = date(2026, 10, 31)
        with patch("checker.check") as browser_check:
            sunday = check_day(saturday + timedelta(days=1), Path("diagnostics"))
            browser_check.assert_not_called()
        feed = build_feed(saturday, self.now, [build_result(saturday, self.now, "available", ["11:30"]), sunday])
        self.assertTrue(feed["ok"])
        self.assertIn("Tomorrow · Sun 01 Nov\nDay off", feed["message"])

    def test_tomorrow_rolls_over_into_new_year(self):
        start = date(2026, 12, 31)
        days = [build_result(start + timedelta(days=i), self.now, "no_online_availability") for i in range(2)]
        feed = build_feed(start, self.now, days)
        self.assertEqual(feed["days"][1]["date"], "2027-01-01")

    def test_rejects_duplicate_day_in_two_day_feed(self):
        today = build_result(self.day, self.now, "available", ["17:30"])
        with self.assertRaises(ValueError):
            build_feed(self.day, self.now, [today, today])


if __name__ == "__main__":
    unittest.main()
