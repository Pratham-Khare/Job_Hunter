# Daily alerts + application tracking

V2.5 adds two things without changing the existing job-discovery rules:

1. **Application tracker** in the Streamlit dashboard.
2. **Daily new-job alert** containing jobs first discovered since the previous alert run and not marked as applied.

## Manual daily run

From the project folder:

```powershell
python main.py --daily-alert
```

This collects jobs, updates the database, creates an HTML and TXT digest under `data/alerts/`, and sends an email only when SMTP settings are configured.

## Windows automatic daily run

Run `scripts/setup_daily_task.bat` once. Windows Task Scheduler can run the existing `scripts/run_daily.bat` every day. Microsoft documents `schtasks /create` for creating recurring local tasks.

To test immediately:

```powershell
schtasks /Run /TN "Job Hunter Daily Alerts"
```

To inspect the task:

```powershell
schtasks /Query /TN "Job Hunter Daily Alerts" /V /FO LIST
```

## Optional email alerts

Set these environment variables before running the daily task:

```text
JOB_ALERT_SMTP_HOST
JOB_ALERT_SMTP_PORT=587
JOB_ALERT_SMTP_USER
JOB_ALERT_SMTP_PASSWORD
JOB_ALERT_FROM
JOB_ALERT_TO
JOB_ALERT_SMTP_TLS=1
```

For Gmail, use an App Password rather than your normal account password.

If email is not configured, the alert is still written locally to `data/alerts/`.

## Application statuses

The dashboard supports:

`NOT_APPLIED`, `SAVED`, `APPLIED`, `OA`, `INTERVIEW`, `HR`, `OFFER`, `REJECTED`, `WITHDRAWN`

Each job can store application date, OA/interview/HR dates, result and notes.

## New-job logic

`discovered_at` is now the **first time the system saw the job** and is not reset on every collection. `last_seen_at` tracks later collection runs. This prevents a job from being incorrectly treated as brand new every day.
