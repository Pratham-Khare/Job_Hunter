import argparse, csv, json
from datetime import datetime
from database import init_db, get_conn, last_alert_run, record_alert_run
from matcher import canonical_id, calculate, fresher_eligible
from collectors import collect_all
from alerts import generate_daily_alert

PROFILE = "config/profile.json"

def load_profile():
    with open(PROFILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_jobs(jobs):
    profile = load_profile()
    conn = get_conn()
    new_count = 0
    updated_count = 0

    cols = [
        "canonical_id","company","title","category","location","work_mode",
        "experience","education","skills","description","salary",
        "posted_date","deadline","source","source_url","official_url",
        "status","eligibility","skill_match","match_score","is_tech","fresher_eligible",
        "discovered_at","last_verified","last_seen_at"
    ]

    for job in jobs:
        if not job.get("title") or not job.get("company"):
            continue

        result = calculate(job, profile)
        job["canonical_id"] = canonical_id(job)
        job["category"] = result["category"]
        job["eligibility"] = result["eligibility"]
        job["is_tech"] = 1 if result["is_tech"] else 0
        job["fresher_eligible"] = 1 if fresher_eligible(job, max_years=int(profile.get("search_policy", {}).get("fresher_max_years", 2))) else 0
        job["skill_match"] = result["skill_match"]
        job["match_score"] = result["match_score"]
        job["status"] = "ACTIVE"
        now = datetime.now().isoformat(timespec="seconds")

        # discovered_at is the FIRST time we ever saw this posting.
        # last_seen_at is updated on every collection. This lets the daily
        # alert identify genuinely new jobs without resetting their age daily.
        existing = conn.execute(
            "SELECT discovered_at FROM jobs WHERE canonical_id = ?",
            (job["canonical_id"],),
        ).fetchone()
        job["discovered_at"] = existing["discovered_at"] if existing and existing["discovered_at"] else now
        job["last_verified"] = now
        job["last_seen_at"] = now

        values = [job.get(c, "") for c in cols]
        placeholders = ",".join(["?"] * len(cols))
        # Preserve discovered_at on updates; everything else is refreshed.
        update_cols = [c for c in cols if c not in {"canonical_id", "discovered_at"}]
        update_sql = ",".join([f"{c}=excluded.{c}" for c in update_cols])

        sql = f"""
            INSERT INTO jobs ({','.join(cols)})
            VALUES ({placeholders})
            ON CONFLICT(canonical_id) DO UPDATE SET {update_sql}
        """
        before = conn.total_changes
        conn.execute(sql, values)
        if conn.total_changes > before:
            new_count += 1
        else:
            updated_count += 1

    conn.commit()
    conn.close()
    return new_count, updated_count

def import_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        jobs = list(csv.DictReader(f))
    new, updated = save_jobs(jobs)
    print(f"Imported jobs. New: {new}, Updated: {updated}")

def collect():
    print("Collecting live jobs from configured public sources...")
    jobs, errors, raw_count, source_stats = collect_all()
    print(f"Collected {raw_count} raw jobs; {len(jobs)} jobs remain after India/remote + tech + fresher-compatible filtering.")
    print("\nSource counts:")
    for source, count in sorted(source_stats.items(), key=lambda x: (-x[1], x[0])):
        print(f" - {source}: {count}")
    new, updated = save_jobs(jobs)
    print(f"Database: {new} new, {updated} updated.")
    if errors:
        print("\nSource errors:")
        for e in errors:
            print(" -", e)
    print("\nRun: streamlit run dashboard.py")

def daily_alert():
    print("Running daily job collection + alert...")
    collect()
    now = datetime.now().isoformat(timespec="seconds")
    previous = last_alert_run()
    path, count, email_sent = generate_daily_alert(previous)
    record_alert_run(now, count, email_sent)
    print(f"Daily alert: {count} new un-applied jobs.")
    print(f"Alert file: {path}")
    if email_sent:
        print("Email alert sent.")
    else:
        print("Email not configured/sent. The HTML alert file is available locally.")

def demo():
    import_csv("data/sample_jobs.csv")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--init", action="store_true")
    p.add_argument("--demo", action="store_true")
    p.add_argument("--collect", action="store_true")
    p.add_argument("--import-csv")
    p.add_argument("--reset", action="store_true", help="Delete and recreate the SQLite database")
    p.add_argument("--daily-alert", action="store_true", help="Collect jobs and generate the daily new-job alert")
    args = p.parse_args()

    if args.reset:
        from database import DB_PATH
        if DB_PATH.exists():
            DB_PATH.unlink()
        print("Database reset.")
    init_db()

    if args.daily_alert:
        daily_alert()
    elif args.demo:
        demo()
    elif args.collect:
        collect()
    elif args.import_csv:
        import_csv(args.import_csv)
    elif args.init:
        print("Database initialized.")
    else:
        p.print_help()

if __name__ == "__main__":
    main()
