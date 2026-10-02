import re
from datetime import date, datetime
from hashlib import sha256

ROLE_GROUPS = {
    "SOFTWARE_ENGINEERING": [
        "software engineer","software developer","sde","sde-1","associate software engineer",
        "graduate software engineer","software engineer trainee","junior software engineer",
        "full stack developer","full stack engineer","backend developer","backend engineer",
        "frontend developer","frontend engineer","mern developer","node.js developer",
        "react developer","web developer","web application developer","java developer",
        "java software engineer","spring boot developer","python developer","python software engineer",
        "django developer","flask developer","c++ developer","c++ software engineer","c developer",
        "php developer",".net developer","c# developer","mobile developer","android developer",
        "ios developer","flutter developer","react native developer"
    ],
    "DATA_ANALYTICS": [
        "data analyst","junior data analyst","business analyst","product analyst","data associate",
        "reporting analyst","business intelligence analyst","bi analyst","bi developer",
        "analytics engineer","research analyst","quantitative analyst"
    ],
    "DATA_ENGINEERING": [
        "data engineer","junior data engineer","analytics engineer","etl developer",
        "data warehouse engineer","big data engineer"
    ],
    "AI_ML": [
        "data scientist","junior data scientist","associate data scientist","machine learning engineer",
        "ml engineer","junior ml engineer","machine learning intern","ai/ml engineer","ai engineer",
        "ai developer","genai developer","generative ai engineer","llm engineer",
        "llm application developer","nlp engineer","computer vision engineer","deep learning engineer"
    ],
    "DEVOPS_CLOUD": [
        "devops engineer","junior devops engineer","cloud engineer","cloud support engineer",
        "site reliability engineer","sre","platform engineer","infrastructure engineer",
        "release engineer","build engineer"
    ],
    "CYBERSECURITY_NETWORKING": [
        "cybersecurity analyst","security analyst","soc analyst","information security analyst",
        "network engineer","network administrator","security engineer"
    ],
    "QA_TESTING": [
        "qa engineer","quality assurance engineer","software test engineer","test engineer",
        "automation test engineer","sdet","automation engineer"
    ],
    "IT_SYSTEMS_SUPPORT": [
        "technical support engineer","application support engineer","production support engineer",
        "technical analyst","systems analyst","systems engineer","system administrator",
        "database administrator","dba","solutions engineer","implementation engineer",
        "technical consultant","it consultant"
    ],
    "SPECIALIZED_TECH": [
        "embedded software engineer","firmware engineer","hardware engineer","iot engineer",
        "blockchain developer","web3 developer","rpa developer","salesforce developer",
        "servicenow developer","sap developer","oracle developer"
    ]
}

def normalize(s):
    """Normalize text safely even when an API returns a list/dict instead of a string."""
    if s is None:
        s = ""
    elif isinstance(s, (list, tuple, set)):
        s = " ; ".join(normalize(x) for x in s if x is not None)
    elif isinstance(s, dict):
        # Prefer human-readable values; API payloads sometimes return structured fields.
        s = " ; ".join(str(v) for v in s.values() if v is not None and not isinstance(v, (dict, list, tuple, set)))
    else:
        s = str(s)
    return re.sub(r"\s+", " ", s.strip().lower())

def canonical_id(job):
    # Cross-source deduplication: the same posting may appear on an ATS and an aggregator
    # with different URLs. Do not make the URL part of the identity.
    raw = "|".join([normalize(job.get("company")), normalize(job.get("title")),
                    normalize(job.get("location"))])
    return sha256(raw.encode()).hexdigest()[:24]

TECH_SIGNALS = [
    "software", "developer", "engineer", "engineering", "sde", "programmer",
    "data", "machine learning", "ml", "artificial intelligence", "ai ", "genai",
    "llm", "analytics", "cloud", "devops", "sre", "platform", "infrastructure",
    "cyber", "security", "soc", "network", "database", "qa", "quality assurance",
    "test automation", "sdet", "technical", "technology", "it ", "systems",
    "embedded", "firmware", "iot", "blockchain", "web3", "rpa", "salesforce",
    "servicenow", "sap", "oracle", "frontend", "backend", "full stack", "mobile",
    "android", "ios", "python", "java", "c++", ".net", "php", "react", "node"
]

def is_tech_role(title, description=""):
    t = normalize(title)
    d = normalize(description)
    category = categorize(t)
    if category != "OTHER_TECH":
        return True
    return any(signal in t for signal in TECH_SIGNALS) or any(signal in d[:2500] for signal in TECH_SIGNALS)

def categorize(title):
    t = normalize(title)
    for category, names in ROLE_GROUPS.items():
        if any(name in t for name in names):
            return category
    return "OTHER_TECH"

def parse_years(exp):
    t = normalize(exp)
    if not t:
        return None, None
    nums = [int(x) for x in re.findall(r"\d+", t)]
    if not nums:
        if any(x in t for x in ["fresher","entry","graduate","trainee","junior","intern"]):
            return 0, 0
        return None, None
    if len(nums) == 1:
        return nums[0], nums[0]
    return nums[0], nums[1]


ENTRY_LEVEL_TITLE_SIGNALS = [
    "fresher", "fresh graduate", "new grad", "new graduate", "graduate",
    "graduate trainee", "trainee", "entry level", "entry-level", "campus",
    "campus hire", "early career", "apprentice", "apprenticeship",
    "associate software engineer", "associate engineer", "associate developer",
    "software engineer i", "software developer i", "developer i", "engineer i",
    "analyst i", "junior software engineer", "junior developer", "junior engineer",
    "junior analyst", "0 years", "0-1 years", "0 - 1 years", "0-2 years", "0 - 2 years"
]

FRESHER_NEGATIVE_SIGNALS = [
    "senior", "sr.", "sr ", "lead", "principal", "staff", "manager",
    "director", "head of", "architect", "3+ years", "4+ years", "5+ years",
    "6+ years", "7+ years", "8+ years", "10+ years"
]

IMMEDIATE_JOINER_SIGNALS = [
    "immediate joiner", "immediate joining", "join immediately",
    "joining immediately", "can join immediately", "available immediately",
    "available to join immediately", "join within 7 days", "join within 15 days",
    "join within 30 days", "0 days notice", "zero notice period",
    "no notice period", "short notice period", "immediate availability"
]

BATCH_2027_SIGNALS = [
    "2027 graduate", "2027 graduates", "2027 batch", "class of 2027",
    "graduating in 2027", "graduating 2027", "expected graduation 2027",
    "expected to graduate in 2027", "pass out 2027", "passout 2027",
    "2027 passout", "2027 passing out"
]

def has_immediate_joiner_signal(text):
    return any(x in text for x in IMMEDIATE_JOINER_SIGNALS)

def has_2027_signal(text):
    return any(x in text for x in BATCH_2027_SIGNALS)

def fresher_eligible(job, max_years=2):
    """Accept entry-level roles for freshers, 2027 graduates, or immediate joiners.

    2027 eligibility is treated as a direct batch signal. Immediate-joiner roles
    are accepted when they do not require more than the fresher experience ceiling.
    Explicit senior/lead/manager roles remain excluded.
    """
    title = normalize(job.get("title"))
    exp = normalize(job.get("experience"))
    desc = normalize(job.get("description"))
    text = f"{title} {exp} {desc[:5000]}"

    # Explicit senior/experienced signals always disqualify a fresher result.
    # We also inspect the title first so phrases like "Senior ... Immediate Joiner"
    # do not get admitted merely because they mention immediate joining.
    if any(x in title for x in FRESHER_NEGATIVE_SIGNALS):
        return False

    # Parse explicit year requirements. If a posting asks for more than the
    # configured fresher ceiling, it is not a fresher job.
    nums = [int(x) for x in re.findall(r"(?<!\d)(\d{1,2})\s*(?:\+\s*)?(?:years?|yrs?)", text)]
    if nums and min(nums) > max_years:
        return False
    ranges = re.findall(r"(\d{1,2})\s*(?:-|to)\s*(\d{1,2})\s*(?:years?|yrs?)", text)
    for lo, hi in ranges:
        if int(lo) > max_years:
            return False
        if int(hi) > max_years and int(lo) > 0:
            return False

    # A 2027 batch signal is an explicit eligibility route even when the posting
    # does not use the word "fresher". This is important for campus/graduate roles.
    if has_2027_signal(text):
        return True

    # Immediate-joiner roles are useful to candidates who are already available.
    # Accept them only when the posting is otherwise entry-level/compatible.
    if has_immediate_joiner_signal(text):
        if not nums and not ranges:
            return True
        lo, hi = parse_years(exp)
        if lo is None or lo <= max_years:
            return True

    # Strong entry-level title/description evidence.
    if any(x in title for x in ENTRY_LEVEL_TITLE_SIGNALS):
        return True

    desc_signals = [
        "freshers can apply", "freshers eligible", "open to freshers",
        "fresh graduates", "recent graduates", "recent graduate",
        "new graduates", "new grad", "0 years experience",
        "no experience required", "no prior experience", "entry-level",
        "entry level", "graduate program", "graduate programme",
        "campus hiring", "campus recruitment", "2026 graduates",
        "2027 graduates", "2026 batch", "2027 batch",
        "class of 2027", "graduating in 2027", "expected graduation 2027",
        "immediate joiner", "immediate joining", "join immediately",
        "available immediately", "immediate availability"
    ]
    if any(x in text for x in desc_signals):
        return True

    # If the normalized experience field explicitly says 0/1/2 years, accept.
    if exp:
        lo, hi = parse_years(exp)
        if lo is not None and hi is not None and lo <= max_years and hi <= max_years:
            return True
        if any(x in exp for x in ["fresher", "entry", "graduate", "trainee", "intern", "junior"]):
            return True

    # Many ATS feeds omit the experience field even for entry-level roles.
    # If there is no explicit senior signal and no explicit >2-year requirement,
    # retain the posting as fresher-compatible instead of discarding it.
    if not exp and not any(x in title for x in FRESHER_NEGATIVE_SIGNALS):
        return True

    return False

def skill_list(s):
    if isinstance(s, (list, tuple, set)):
        parts = []
        for item in s:
            parts.extend(re.split(r"[;,|]", normalize(item)))
    else:
        parts = re.split(r"[;,|]", normalize(s))
    return {normalize(x) for x in parts if normalize(x)}

def profile_skill_set(profile):
    return {normalize(x) for x in profile["skills"] + profile.get("core_cs", [])}

def education_eligible(education):
    e = normalize(education)
    if not e:
        return True
    if "mca" in e or "computer science" in e or "computer applications" in e:
        return True
    if "btech only" in e or "be only" in e or "engineering only" in e:
        return False
    return True

def experience_eligible(exp):
    lo, hi = parse_years(exp)
    if lo is None:
        return True
    return lo <= 2

def location_match(location, profile):
    l = normalize(location)
    if not l:
        return 0.5
    targets = [normalize(x) for x in profile["locations"]]
    if "remote" in l and "remote" in targets:
        return 1.0
    if "india" in l:
        return 1.0
    return 1.0 if any(x in l for x in targets) else 0.5

def role_alignment(title, profile):
    t = normalize(title)
    primary = [normalize(x) for x in profile.get("primary_roles", [])]
    secondary = [normalize(x) for x in profile.get("secondary_roles", [])]
    other = [normalize(x) for x in profile.get("other_tech_roles", [])]
    if any(x in t for x in primary):
        return 1.0
    if any(x in t for x in secondary):
        return 0.85
    if any(x in t for x in other):
        return 0.75
    if any(x in t for x in ["engineer","developer","analyst","scientist","programmer","architect","administrator","consultant","technology","technical","it "]):
        return 0.60
    return 0.25

def calculate(job, profile):
    eligible = education_eligible(job.get("education")) and experience_eligible(job.get("experience"))
    job_skills = skill_list(job.get("skills"))
    profile_skills = profile_skill_set(profile)
    desc = normalize(job.get("description"))
    matched = {s for s in job_skills if s in profile_skills or s in desc}
    skill_match = len(matched) / len(job_skills) if job_skills else 0.5
    role = role_alignment(job.get("title"), profile)
    exp = 1.0 if experience_eligible(job.get("experience")) else 0.0
    loc = location_match(job.get("location"), profile)
    freshness = 0.5
    try:
        posted = datetime.fromisoformat((job.get("posted_date") or "").replace("Z","+00:00")).date()
        age = max(0, (date.today() - posted).days)
        freshness = 1.0 if age <= 2 else 0.8 if age <= 7 else 0.5 if age <= 14 else 0.2
    except Exception:
        pass
    w = profile["weights"]
    score = ((1.0 if eligible else 0.0)*w["eligibility"] + skill_match*w["required_skill_match"] +
             role*w["role_alignment"] + exp*w["experience_alignment"] + loc*w["location_alignment"] +
             freshness*w["freshness"])
    return {"category": categorize(job.get("title")), "is_tech": is_tech_role(job.get("title"), job.get("description")), "eligibility": "ELIGIBLE" if eligible else "REVIEW",
            "skill_match": round(skill_match*100,1), "match_score": round(score,1),
            "matched_skills": sorted(matched)}
