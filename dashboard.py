import sqlite3
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
from database import init_db, DB_PATH

st.set_page_config(page_title="Job Hunter", layout="wide")
init_db()

@st.cache_data(ttl=30)
def load_jobs():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT j.id, j.company, j.title, j.category, j.location, j.work_mode,
               j.experience, j.education, j.eligibility, j.skill_match, j.match_score,
               j.posted_date, j.deadline, j.source, j.official_url, j.status,
               j.is_tech, j.fresher_eligible, j.discovered_at, j.last_seen_at,
               COALESCE(a.status, 'NOT_APPLIED') AS application_status,
               a.date_applied, a.oa_date, a.interview_date, a.hr_date, a.result, a.notes AS application_notes
        FROM jobs j
        LEFT JOIN applications a ON a.job_id = j.id
        ORDER BY j.match_score DESC, j.posted_date DESC
    """, conn)
    conn.close()
    return df


def save_application(job_id, status, date_applied, oa_date, interview_date, hr_date, result, notes):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO applications(job_id, date_applied, status, oa_date, interview_date, hr_date, result, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id) DO UPDATE SET
          date_applied=excluded.date_applied,
          status=excluded.status,
          oa_date=excluded.oa_date,
          interview_date=excluded.interview_date,
          hr_date=excluded.hr_date,
          result=excluded.result,
          notes=excluded.notes
    """, (job_id, date_applied, status, oa_date, interview_date, hr_date, result, notes))
    conn.commit()
    conn.close()
    st.cache_data.clear()

st.title("Job Hunter — Fresher Tech Jobs")
st.caption("India + worldwide remote · fresher/0–2 years · 2027 graduates · compatible immediate joiners")
df = load_jobs()

if df.empty:
    st.info("No jobs yet. Run `python main.py --collect` to collect live public feeds.")
    st.stop()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Jobs", len(df))
c2.metric("Not Applied", int(df["application_status"].isin(["NOT_APPLIED", "SAVED"]).sum()))
c3.metric("Applied", int(df["application_status"].isin(["APPLIED", "OA", "INTERVIEW", "HR", "OFFER", "REJECTED", "WITHDRAWN"]).sum()))
c4.metric("80+ Match", int((df["match_score"] >= 80).sum()))
c5.metric("Sources", int(df["source"].nunique()))

st.divider()

with st.sidebar:
    st.header("Filters")
    categories = st.multiselect("Category", sorted(df["category"].dropna().unique()))
    locations = st.multiselect("Location", sorted(df["location"].dropna().unique()))
    sources = st.multiselect("Source", sorted(df["source"].dropna().unique()))
    statuses = st.multiselect("Application status", sorted(df["application_status"].unique()))
    minimum = st.slider("Minimum match score", 0, 100, 60)
    eligible_only = st.checkbox("Eligible only", True)
    tech_only = st.checkbox("Tech jobs only", True)
    fresher_only = st.checkbox("Fresher compatible only", True)

filtered = df.copy()
if categories:
    filtered = filtered[filtered["category"].isin(categories)]
if locations:
    filtered = filtered[filtered["location"].isin(locations)]
if sources:
    filtered = filtered[filtered["source"].isin(sources)]
if statuses:
    filtered = filtered[filtered["application_status"].isin(statuses)]
filtered = filtered[filtered["match_score"] >= minimum]
if eligible_only:
    filtered = filtered[filtered["eligibility"] == "ELIGIBLE"]
if tech_only:
    filtered = filtered[filtered["is_tech"] == 1]
if fresher_only:
    filtered = filtered[filtered["fresher_eligible"] == 1]

st.subheader("New jobs")
last_24 = datetime.now() - timedelta(days=1)
new_df = filtered[pd.to_datetime(filtered["discovered_at"], errors="coerce") >= last_24]
new_unapplied = new_df[new_df["application_status"].isin(["NOT_APPLIED", "SAVED"])]
st.metric("New in last 24 hours and not applied", len(new_unapplied))

st.subheader("Source balance")
st.dataframe(df["source"].value_counts().rename_axis("Source").reset_index(name="Jobs"), hide_index=True, use_container_width=True)

st.subheader(f"Matching jobs ({len(filtered)})")

statuses_options = ["NOT_APPLIED", "SAVED", "APPLIED", "OA", "INTERVIEW", "HR", "OFFER", "REJECTED", "WITHDRAWN"]

for _, row in filtered.head(150).iterrows():
    with st.container(border=True):
        col1, col2, col3 = st.columns([5, 1, 1])
        with col1:
            st.markdown(f"### {row['title']}")
            st.write(f"**{row['company']}** · {row['location']} · {row['work_mode']}")
            st.caption(f"{row['category']} · {row['experience']} · {row['source']}")
        with col2:
            st.metric("Match", f"{row['match_score']:.0f}%")
        with col3:
            st.metric("Skills", f"{row['skill_match']:.0f}%")
        if row["official_url"]:
            st.link_button("Open job", row["official_url"])

        with st.expander("Application tracker"):
            current_status = row["application_status"] if row["application_status"] in statuses_options else "NOT_APPLIED"
            form_key = f"app_{int(row['id'])}"
            with st.form(form_key):
                a1, a2, a3 = st.columns(3)
                with a1:
                    status = st.selectbox("Status", statuses_options, index=statuses_options.index(current_status), key=f"status_{row['id']}")
                    date_applied = st.text_input("Applied date (YYYY-MM-DD)", value=str(row["date_applied"] or ""), key=f"applied_{row['id']}")
                with a2:
                    oa_date = st.text_input("OA date", value=str(row["oa_date"] or ""), key=f"oa_{row['id']}")
                    interview_date = st.text_input("Interview date", value=str(row["interview_date"] or ""), key=f"int_{row['id']}")
                with a3:
                    hr_date = st.text_input("HR date", value=str(row["hr_date"] or ""), key=f"hr_{row['id']}")
                    result = st.text_input("Result", value=str(row["result"] or ""), key=f"result_{row['id']}")
                notes = st.text_area("Notes", value=str(row["application_notes"] or ""), key=f"notes_{row['id']}")
                submitted = st.form_submit_button("Save application status")
                if submitted:
                    save_application(int(row["id"]), status, date_applied, oa_date, interview_date, hr_date, result, notes)
                    st.success("Application status saved.")

st.divider()
st.subheader("Application pipeline")
pipeline = df["application_status"].value_counts().reindex(statuses_options, fill_value=0).rename_axis("Status").reset_index(name="Jobs")
st.dataframe(pipeline, hide_index=True, use_container_width=True)
