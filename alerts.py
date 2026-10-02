import os
import html
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from database import get_conn

ALERT_DIR = Path("data/alerts")


def _email_settings():
    return {
        "host": os.getenv("JOB_ALERT_SMTP_HOST", ""),
        "port": int(os.getenv("JOB_ALERT_SMTP_PORT", "587")),
        "user": os.getenv("JOB_ALERT_SMTP_USER", ""),
        "password": os.getenv("JOB_ALERT_SMTP_PASSWORD", ""),
        "from": os.getenv("JOB_ALERT_FROM", ""),
        "to": os.getenv("JOB_ALERT_TO", ""),
        "tls": os.getenv("JOB_ALERT_SMTP_TLS", "1") != "0",
    }


def _unapplied_statuses():
    return ("NOT_APPLIED", "SAVED", "")


def fetch_new_unapplied(previous_run):
    conn = get_conn()
    params = []
    query = """
        SELECT j.*, COALESCE(a.status, 'NOT_APPLIED') AS application_status
        FROM jobs j
        LEFT JOIN applications a ON a.job_id = j.id
        WHERE j.status = 'ACTIVE'
          AND j.is_tech = 1
          AND j.fresher_eligible = 1
          AND COALESCE(a.status, 'NOT_APPLIED') IN ('NOT_APPLIED', 'SAVED', '')
    """
    if previous_run:
        query += " AND j.discovered_at > ?"
        params.append(previous_run)
    query += " ORDER BY j.match_score DESC, j.discovered_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def _render_html(rows, previous_run):
    generated = datetime.now().strftime("%d %b %Y, %I:%M %p")
    period = f"since {previous_run}" if previous_run else "first alert run"
    cards = []
    for r in rows[:100]:
        url = r["official_url"] or r["source_url"] or ""
        link = f'<a href="{html.escape(url, quote=True)}">Open job</a>' if url else ""
        cards.append(f"""
        <tr>
          <td><strong>{html.escape(r['title'] or '')}</strong><br>{html.escape(r['company'] or '')}</td>
          <td>{html.escape(r['location'] or '')}<br>{html.escape(r['work_mode'] or '')}</td>
          <td>{html.escape(r['category'] or '')}<br>{html.escape(r['experience'] or '')}</td>
          <td><strong>{float(r['match_score'] or 0):.0f}%</strong><br>Skills {float(r['skill_match'] or 0):.0f}%</td>
          <td>{html.escape(r['source'] or '')}<br>{link}</td>
        </tr>
        """)
    body = "".join(cards) or '<tr><td colspan="5">No new un-applied jobs.</td></tr>'
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Job Hunter Daily Alert</title>
<style>body{{font-family:Arial,sans-serif;max-width:1200px;margin:30px auto;padding:0 16px}}table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid #ddd;padding:10px;text-align:left;vertical-align:top}}th{{background:#f4f4f4}}.count{{font-size:28px;font-weight:700}}</style></head>
<body><h1>Job Hunter Daily Alert</h1><p>Generated {html.escape(generated)} · New jobs {html.escape(period)}</p>
<p class="count">{len(rows)} new un-applied jobs</p>
<table><thead><tr><th>Job</th><th>Location</th><th>Category / Experience</th><th>Match</th><th>Source</th></tr></thead><tbody>{body}</tbody></table>
</body></html>"""


def _render_text(rows, previous_run):
    lines = ["JOB HUNTER DAILY ALERT", "", f"New un-applied jobs: {len(rows)}", f"Since: {previous_run or 'first alert run'}", ""]
    for r in rows[:100]:
        url = r["official_url"] or r["source_url"] or ""
        lines.extend([
            f"{r['title']} — {r['company']}",
            f"Location: {r['location']} | {r['work_mode']}",
            f"Match: {float(r['match_score'] or 0):.0f}% | Skills: {float(r['skill_match'] or 0):.0f}% | Source: {r['source']}",
            f"Apply: {url}", ""
        ])
    return "\n".join(lines)


def _send_email(subject, text_body, html_body):
    cfg = _email_settings()
    if not all([cfg["host"], cfg["user"], cfg["password"], cfg["from"], cfg["to"]]):
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["from"]
    msg["To"] = cfg["to"]
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as server:
        if cfg["tls"]:
            server.starttls()
        server.login(cfg["user"], cfg["password"])
        server.send_message(msg)
    return True


def generate_daily_alert(previous_run):
    rows = fetch_new_unapplied(previous_run)
    ALERT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_path = ALERT_DIR / f"daily_alert_{stamp}.html"
    text_path = ALERT_DIR / f"daily_alert_{stamp}.txt"
    html_body = _render_html(rows, previous_run)
    text_body = _render_text(rows, previous_run)
    html_path.write_text(html_body, encoding="utf-8")
    text_path.write_text(text_body, encoding="utf-8")
    sent = False
    try:
        sent = _send_email(f"Job Hunter: {len(rows)} new un-applied jobs", text_body, html_body)
    except Exception as exc:
        print(f"Email alert failed: {exc}")
    return str(html_path), len(rows), sent
