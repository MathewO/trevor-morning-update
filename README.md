# Trevor's morning update

A free cloud check of Trevor's **public 30-minute Hair Cut availability for today and tomorrow** at [Savills Barbers on Booksy](https://booksy.com/en-gb/6035_savills-barbers_barber_1419956_sheffield). An iPhone Shortcut reads the result and shows a native notification.

This is public availability, not Trevor's private calendar. Available start times can overlap; their count is not a count of customers or capacity. Breaks, blocked time and actual bookings cannot be distinguished. The checker never presses Continue or submits a booking, signs in to Booksy, or accesses customer details.

## Live feed

Use this URL in Shortcuts:

```
https://raw.githubusercontent.com/MathewO/trevor-morning-update/main/status.json
```

The feed is publicly readable and contains the date, check time, service, a `days` list with separate results for today and tomorrow, and one combined `message`. Sunday and Monday are labelled as regular days off. No account token is needed on the phone. Always check its date before using it.

GitHub is scheduled to run the checker **every 15 minutes, all day Tuesday–Saturday**, at minutes **02, 17, 32 and 47** of each hour in UK time. London daylight saving is handled by the workflow timezone. GitHub schedules can be delayed or dropped, and the public file may take a few minutes to refresh through GitHub's cache; this is not a guaranteed maximum data age. Each message includes its check time. Run it manually under **Actions → Update Trevor availability → Run workflow** whenever a fresh test is needed.

Run the existing Shortcut whenever you want to see the latest saved result. It automatically displays both days as long as **Show Notification uses the `message` Dictionary Value**. No GitHub token or extra hosting is needed. The cloud checks do not trigger phone notifications themselves; keep the morning phone automation and use the Shortcut manually during the day. For a longer result, expand the notification or use **Show Result** in a separate manual shortcut.

## First iPhone test (latest iOS)

Create a normal shortcut named **Trevor's day** with these actions:

1. **URL** — paste the feed URL above.
2. **Get Contents of URL** — use the URL, method GET.
3. **Get Dictionary from Input** — use Contents of URL. This explicitly parses GitHub's JSON text.
4. **Get Dictionary Value** — get the value for key `message` from Dictionary.
5. **Show Notification** — use the output of Get Dictionary Value as the body; set the title to `Trevor's day`. Do not use Contents of URL or the whole Dictionary, which would display raw JSON.

Run once with the phone unlocked and allow the request to `raw.githubusercontent.com` when asked. Check the displayed date and check time against the current feed. This first test has no schedule and no stale-data protection; add the checks below before scheduling it.

## Add freshness protection before scheduling

After **Get Dictionary from Input**, save its output with **Set Variable** named `Feed`. Then:

1. **Current Date**, then **Format Date** with Custom format `yyyy-MM-dd`. Save that result as `Today`. Use the UK date; keep the phone on UK time for this setup.
2. **Get Dictionary Value** for `date` from `Feed`.
3. **If** Dictionary Value **is** `Today`:
   - **Get Dictionary Value** for `checked_at` from `Feed`.
   - **Get Dates from Input**, using that value.
   - **Get Time Between Dates**, from that date to Current Date, in minutes.
   - **If** the time difference **is between** `0` and `45`:
     - Get `message` from `Feed` and **Show Notification** with that message.
   - **Otherwise:** show `Today's update needs refreshing. Please check Booksy.`
4. **Otherwise:** show `Today's update isn't ready. Please check Booksy.`

An explicit checker failure has `ok: false` and a clear failure message beside the affected day. The overall status is `partial_error` when one day succeeds, or `error` when both fail. A successful day's times remain visible even if the other day fails, but the combined report must not be treated as a successful daily update for the backup logic below. An internet/request failure may stop the Shortcut with an iOS error; do not mark that attempt successful.

## Morning automation

On the iPhone: **Shortcuts → Automation → + → Time of Day → 07:00 → Weekly → Tuesday, Wednesday, Thursday, Friday, Saturday → Run Immediately → choose Trevor's day**. Depending on iOS wording, turn off Ask Before Running instead. Choose Show Notification, not Show Alert (which waits for interaction).

Test using a time a few minutes ahead, lock the phone and check that the notification appears. Focus and notification settings can silence or hide it. The actual on-device test must be done on the iPhone; creating this repository does not install a Shortcut or personal automation.

## Optional missed-run backup

Use a separate **Trevor morning check** shortcut for automatic runs, keeping **Trevor's day** available for manual viewing:

- Store a local text file such as `Shortcuts/Trevor/last-success.txt`, initially `never`. Set file actions to this fixed location and disable Ask Where to Save.
- At the start of the automatic shortcut, read this file. If its contents equal today's `yyyy-MM-dd` date, stop the shortcut.
- Perform the same fetch, date and age checks. Show the message. Only when `Feed.ok` is true, save today's date to `last-success.txt` (overwrite enabled). Never save success after an error or stale result.
- Run this automatic shortcut at 07:00 and again at 07:30 on working days. Regular cloud checks continue between these attempts. Optionally also run it when a chosen app is opened, before 10:00, to catch a phone that was off earlier.
- Test the local file access while locked. A completed notification action does not prove the notification was read. iOS does not guarantee replay of missed time-based runs.

For a first test, establish the basic scheduled notification before adding duplicate suppression.

## Share with Trevor

Long-press the normal shortcut → **Share → Copy iCloud Link**. Trevor opens the link, adds it, runs it once and approves its web access. He must create the personal automation on his own phone; automations are not shared with the shortcut. If using backup storage, initialize the local file on his phone too. Do not share GitHub credentials.

## Verification and maintenance

For each working day, the cloud run checks the selected date, year, staff and 30-minute service. It requires an explicit no-availability message before reporting no online availability. Unexpected content, page failures or format changes produce an error result for that day with no old times. The workflow fails visibly while publishing any partial results and explicit errors when possible. Diagnostics are stored separately by date.

Public widget screenshots are retained as GitHub Actions artifacts for three days for troubleshooting. Public-repository schedules may be disabled after 60 days without repository activity; the generated status commits normally provide activity, but check the Actions page if updates stop. No paid runner or AI service is used.

Local validation:

```
python -m pip install -r requirements.txt
python -m playwright install chromium
python -m unittest -v
python checker.py
```

Cloud verification passed on **30 October 2026 at 15:29 UK time**: the checker selected Trevor separately for each date and reported **17:30 today**, and **11:30, 13:30 and 14:00 tomorrow**, for the 30-minute Hair Cut. All **12** safeguard tests passed, including separate dates, partial failures, days off and date rollover. [Successful two-day cloud run](https://github.com/MathewO/trevor-morning-update/actions/runs/41080962455).

The actual iPhone notification and locked-screen automation test are still to be completed on the phone. Treat this as a prototype until those pass.
