# Trevor's morning update

A free cloud check of Trevor's **public 30-minute Hair Cut availability** at [Savills Barbers on Booksy](https://booksy.com/en-gb/6035_savills-barbers_barber_1419956_sheffield). An iPhone Shortcut reads the result and shows a native notification.

This is public availability, not Trevor's private calendar. Available start times can overlap; their count is not a count of customers or capacity. Breaks, blocked time and actual bookings cannot be distinguished. The checker never presses Continue or submits a booking, signs in to Booksy, or accesses customer details.

## Live feed

Use this URL in Shortcuts:

```
https://raw.githubusercontent.com/MathewO/trevor-morning-update/main/status.json
```

The feed is publicly readable and contains the date, check time, service, available start times and a notification message. No account token is needed on the phone. Always check its date before using it.

GitHub runs the checker at **06:17, 06:47 and 07:17 UK time, Tuesday–Saturday**. London daylight saving is handled by the workflow timezone. GitHub schedules can be delayed or dropped. Run it manually under **Actions → Update Trevor availability → Run workflow** whenever a fresh test is needed.

## First iPhone test (latest iOS)

Create a normal shortcut named **Trevor's day** with these actions:

1. **URL** — paste the feed URL above.
2. **Get Contents of URL** — use the URL, method GET.
3. **Get Dictionary Value** — get the value for key `message` from Contents of URL.
4. **Show Notification** — use Dictionary Value as the body; set the title to `Trevor's day`.

Run once with the phone unlocked and allow the request to `raw.githubusercontent.com` when asked. Check the displayed date and check time against the current feed. This first test has no schedule and no stale-data protection; add the checks below before scheduling it.

## Add freshness protection before scheduling

After **Get Contents of URL**, save its output with **Set Variable** named `Feed`. Then:

1. **Current Date**, then **Format Date** with Custom format `yyyy-MM-dd`. Save that result as `Today`. Use the UK date; keep the phone on UK time for this setup.
2. **Get Dictionary Value** for `date` from `Feed`.
3. **If** Dictionary Value **is** `Today`:
   - **Get Dictionary Value** for `checked_at` from `Feed`.
   - **Get Dates from Input**, using that value.
   - **Get Time Between Dates**, from that date to Current Date, in minutes.
   - **If** the time difference **is between** `0` and `180`:
     - Get `message` from `Feed` and **Show Notification** with that message.
   - **Otherwise:** show `Today's update needs refreshing. Please check Booksy.`
4. **Otherwise:** show `Today's update isn't ready. Please check Booksy.`

An explicit checker failure has `ok: false`, `status: error` and a clear failure message. It must not be treated as a successful daily update for the backup logic below. An internet/request failure may stop the Shortcut with an iOS error; do not mark that attempt successful.

## Morning automation

On the iPhone: **Shortcuts → Automation → + → Time of Day → 07:00 → Weekly → Tuesday, Wednesday, Thursday, Friday, Saturday → Run Immediately → choose Trevor's day**. Depending on iOS wording, turn off Ask Before Running instead. Choose Show Notification, not Show Alert (which waits for interaction).

Test using a time a few minutes ahead, lock the phone and check that the notification appears. Focus and notification settings can silence or hide it. The actual on-device test must be done on the iPhone; creating this repository does not install a Shortcut or personal automation.

## Optional missed-run backup

Use a separate **Trevor morning check** shortcut for automatic runs, keeping **Trevor's day** available for manual viewing:

- Store a local text file such as `Shortcuts/Trevor/last-success.txt`, initially `never`. Set file actions to this fixed location and disable Ask Where to Save.
- At the start of the automatic shortcut, read this file. If its contents equal today's `yyyy-MM-dd` date, stop the shortcut.
- Perform the same fetch, date and age checks. Show the message. Only when `Feed.ok` is true, save today's date to `last-success.txt` (overwrite enabled). Never save success after an error or stale result.
- Run this automatic shortcut at 07:00 and again at 07:30 on working days. The 07:30 run follows the 07:17 cloud retry. Optionally also run it when a chosen app is opened, before 10:00, to catch a phone that was off earlier.
- Test the local file access while locked. A completed notification action does not prove the notification was read. iOS does not guarantee replay of missed time-based runs.

For a first test, establish the basic scheduled notification before adding duplicate suppression.

## Share with Trevor

Long-press the normal shortcut → **Share → Copy iCloud Link**. Trevor opens the link, adds it, runs it once and approves its web access. He must create the personal automation on his own phone; automations are not shared with the shortcut. If using backup storage, initialize the local file on his phone too. Do not share GitHub credentials.

## Verification and maintenance

The cloud run checks the selected date, year, staff and 30-minute service. It requires an explicit no-availability message before reporting no online availability. Unexpected content, page failures or format changes produce an error result with no old times. The workflow fails visibly while publishing that explicit error when possible.

Public widget screenshots are retained as GitHub Actions artifacts for three days for troubleshooting. Public-repository schedules may be disabled after 60 days without repository activity; the generated status commits normally provide activity, but check the Actions page if updates stop. No paid runner or AI service is used.

Local validation:

```
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m unittest -v
python checker.py
```

The repository and feed are a prototype until a successful cloud run and the actual iPhone notification test have both been verified.
