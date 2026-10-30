import unittest
from datetime import date, datetime
from checker import build_result, validate_snapshot, LONDON


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


if __name__ == "__main__":
    unittest.main()
