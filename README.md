# Job Hunter V2.1 — Broad Tech Job Discovery

Free/local-first job discovery system tailored to Pratham's resume.

## V2.1 sources

1. **Remote OK public JSON feed** — remote jobs; source requires credit/link-back.
2. **Arbeitnow public API** — used as one supplementary feed; default collection is only 1 page, then India/remote + tech filtering is applied.
3. **Remotive public API** — remote jobs; listings are delayed by 24h and the source requires attribution/link-back.
4. **Greenhouse public Job Board API** — add company board tokens in `config/sources.json`.
5. **Lever public Postings API** — add company site slugs in `config/sources.json`.

Greenhouse's public GET job-board endpoints do not require authentication. Lever's public postings feed is intended for published public postings. See the official documentation links in the project's `SOURCES.md`.

## Important coverage limitation

There is no single free API that contains every job on LinkedIn, Naukri, Indeed, every company career site, etc. V2 therefore uses legitimate/public feeds and ATS APIs. We will expand coverage source-by-source rather than relying on brittle or unauthorized scraping.

## Install

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Initialize

```powershell
python main.py --init
```

## Test with demo data

```powershell
python main.py --demo
streamlit run dashboard.py
```

## Collect live public feeds

```powershell
python main.py --collect
```

This pulls public feeds, normalizes them, scores them against your profile, deduplicates them, and stores them in SQLite.

Then:

```powershell
streamlit run dashboard.py
```

## Add company career pages

Edit:

`config/sources.json`

Example:

```json
{
  "greenhouse": [
    {"company": "Example", "board_token": "example"}
  ],
  "lever": [
    {"company": "Example", "site": "example"}
  ]
}
```

Do not guess tokens. Add them only when verified from the company's public careers URL.

## Daily automation on Windows

The provided `scripts/run_daily.bat` runs collection.

Use Windows Task Scheduler:

1. Open Task Scheduler.
2. Create Basic Task.
3. Trigger: Daily.
4. Action: Start a program.
5. Program: `D:\job hunting\job_hunter_v2\.venv\Scripts\python.exe`
6. Arguments: `main.py --collect`
7. Start in: `D:\job hunting\job_hunter_v2`

Adjust the path to your actual folder.

## What V2 does not do

It does not automatically submit applications. It finds and scores jobs; you remain in control of applications.


## Broad-role policy

The system intentionally searches broadly across:
- Software engineering and development
- Java / Python / C / C++ / .NET / PHP development
- Frontend / backend / full stack / mobile
- Data analyst / data science / data engineering / BI
- AI / ML / GenAI / NLP / computer vision
- DevOps / cloud / SRE / infrastructure
- Cybersecurity / SOC / networking
- QA / testing / SDET / automation
- IT systems / support / technical analyst / implementation
- Specialized technology such as embedded, IoT, Salesforce, ServiceNow, SAP, Web3 and RPA

A missing skill lowers the match score; it does not automatically exclude the job.


## Why this fixes the Arbeitnow problem

The previous build pulled 5 full Arbeitnow pages, while Greenhouse/Lever lists were empty. That could make one source dominate the database. V2.1:
- reduces Arbeitnow to 1 page by default;
- filters the collected set to India + remote jobs;
- keeps tech roles broadly, not only resume-matching roles;
- shows source distribution in the dashboard;
- deduplicates the same company/title/location across different sources even when their URLs differ.

Greenhouse's public Job Board API exposes published jobs without authentication for GET endpoints, so it is a useful direct-company source when company board tokens are configured. citeturn0search0turn0search1 Lever likewise provides public published postings through its Postings API. citeturn0search2

## Fresh start after upgrading

Because the old database already contains the 1,066-job collection, reset it once:

```powershell
python main.py --reset
python main.py --collect
streamlit run dashboard.py
```

Do this from the folder containing `main.py`.


## V2.2 ATS layer

This version adds direct ATS collectors for Greenhouse, Lever, Ashby, and SmartRecruiters. Greenhouse and Ashby publish public job-board JSON endpoints; SmartRecruiters exposes a public postings endpoint per company. The starter registry includes several ATS boards known to contain India/remote technical roles; edit `config/sources.json` to add more company slugs.

Arbeitnow remains only one supplemental feed (1 page). The objective is source diversity, not maximizing one aggregator.


## V2.3 all-source coverage

This release broadens the collector beyond Greenhouse/Lever/Ashby/SmartRecruiters. It supports public or publicly readable job-board surfaces for BambooHR, Workable, Recruitee, Breezy HR, Personio, Teamtailor, Rippling, Workday board URLs, generic career pages with Schema.org JobPosting JSON-LD, plus public remote/startup feeds from Himalayas, Jobicy, and the YC jobs directory.

Some major portals/ATS products do **not** expose a general public jobs API (or require employer/customer credentials), so the project does not pretend to scrape them as if an API existed. For those, use `career_pages` with an official employer careers URL where the page exposes JobPosting structured data. This includes many Workday/iCIMS/Oracle/Taleo/SuccessFactors/Jobvite/custom ATS pages.

The system intentionally keeps first-party employer/ATS sources separate from aggregators, deduplicates across sources, and retains only India/remote tech roles in the main dataset.


## V2.3.1 bug fix

Some ATS feeds return fields such as experience/location/skills as JSON arrays or objects. V2.3.1 safely converts those values to text before matching and SQLite storage, preventing `AttributeError: 'list' object has no attribute 'strip'` during collection.


## Candidate eligibility policy

The default feed is for entry-level tech candidates. It includes: (1) fresher/entry-level roles, (2) roles explicitly accepting the 2027 graduating batch, and (3) immediate-joiner roles when they do not require more than the configured 0–2 years fresher ceiling. Explicit senior/lead/principal/manager roles remain excluded.


## Location policy
The fresher-compatible collector keeps India jobs and remote jobs even when a remote listing names another country (for example Remote - US, Remote - UK, Remote - Germany, Worldwide). The dashboard should be used to verify whether the employer actually accepts applicants from India; remote does not automatically mean worldwide.


## V2.4 automatic company/ATS discovery

V2.4 adds an official-company career registry and automatic ATS discovery. During collection, the tool checks configured employer career pages (respecting robots.txt where available), extracts Schema.org JobPosting data, and detects public Greenhouse, Lever, Ashby, SmartRecruiters, Workday, Teamtailor, Recruitee, Personio, BambooHR, Workable and Breezy job-board links. This removes the need to manually know every ATS board token.

The starter registry includes a broad set of large Indian/global technology employers. It is a seed, not a claim of complete internet coverage; public career systems differ and some pages require JavaScript or authentication.
