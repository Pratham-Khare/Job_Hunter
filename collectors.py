import json
import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from company_discovery import discover

TIMEOUT = 30
HEADERS = {"User-Agent": "JobHunterV2.2/1.0 (personal job discovery tool)"}

def clean_html(html):
    if not html: return ""
    soup = BeautifulSoup(unescape(html), "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

def get_json(url, params=None):
    r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status(); return r.json()

def _text(value):
    """Convert common API field shapes to SQLite-safe human-readable text."""
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return "; ".join(_text(v) for v in value if v is not None and _text(v))
    if isinstance(value, dict):
        vals = []
        for v in value.values():
            if isinstance(v, (str, int, float)) and str(v).strip():
                vals.append(str(v).strip())
        return "; ".join(vals)
    return str(value)

def normalize(company,title,location,work_mode,experience,education,skills,description,salary,posted,source,url):
    return {"company":_text(company),"title":_text(title),"location":_text(location),"work_mode":_text(work_mode),
            "experience":_text(experience),"education":_text(education),"skills":_text(skills),
            "description":_text(description),"salary":_text(salary),"posted_date":_text(posted),
            "deadline":"","source":_text(source),"source_url":_text(url),"official_url":_text(url)}

def remoteok():
    data=get_json("https://remoteok.com/api"); data=data.get("jobs",[]) if isinstance(data,dict) else data
    return [normalize(x.get("company",""),x.get("position",""),x.get("location") or "Remote","Remote","","",";".join(x.get("tags") or []),clean_html(x.get("description","")),x.get("salary",""),x.get("date","")[:10],"Remote OK",x.get("url","")) for x in data if isinstance(x,dict) and x.get("position")]

def arbeitnow(max_pages=1):
    out=[]
    for page in range(1,max_pages+1):
        data=get_json("https://www.arbeitnow.com/api/job-board-api",params={"page":page}); jobs=data.get("data") if isinstance(data,dict) else data
        if not jobs: break
        for x in jobs:
            out.append(normalize(x.get("company_name",""),x.get("title",""),x.get("location") or ("Remote" if x.get("remote") else ""),"Remote" if x.get("remote") else "","","",";".join(x.get("tags") or []),clean_html(x.get("description","")),"",x.get("created_at_iso","")[:10],"Arbeitnow",x.get("url","")))
    return out

def remotive():
    data=get_json("https://remotive.com/api/remote-jobs")
    return [normalize(x.get("company_name",""),x.get("title",""),x.get("candidate_required_location") or "Remote","Remote",x.get("job_type",""),"",";".join(x.get("tags") or []),clean_html(x.get("description","")),x.get("salary",""),x.get("publication_date","")[:10],"Remotive",x.get("url","")) for x in data.get("jobs",[])]

def greenhouse(company, board_token):
    data=get_json(f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs",params={"content":"true"}); out=[]
    for x in data.get("jobs",[]):
        offices=x.get("offices") or []; loc=", ".join(o.get("location","") for o in offices if o.get("location"))
        out.append(normalize(company,x.get("title",""),loc,"","","","",clean_html(x.get("content","")),"",x.get("updated_at","")[:10],f"Greenhouse:{company}",x.get("absolute_url","")))
    return out

def lever(company,site):
    data=get_json(f"https://api.lever.co/v0/postings/{site}",params={"mode":"json"}); out=[]
    for x in data:
        c=x.get("categories") or {}; created=x.get("createdAt")
        posted=datetime.fromtimestamp(created/1000,tz=timezone.utc).date().isoformat() if created else ""
        urls=x.get("urls") or {}; url=urls.get("show","")
        out.append(normalize(company,x.get("text",""),c.get("location","") ,x.get("workplaceType","") ,c.get("level","") ,"",";".join(x.get("tags") or []),clean_html(x.get("descriptionPlain") or x.get("description","")),x.get("salaryDescription",""),posted,f"Lever:{company}",url))
    return out

def ashby(company,board_name):
    data=get_json(f"https://api.ashbyhq.com/posting-api/job-board/{board_name}",params={"includeCompensation":"true"}); out=[]
    for x in data.get("jobs",[]):
        loc=x.get("location",""); secondary=x.get("secondaryLocations") or []
        if secondary: loc="; ".join([loc]+[s.get("location","") if isinstance(s,dict) else str(s) for s in secondary])
        comp=x.get("compensation") or {}; salary=comp.get("summary") if isinstance(comp,dict) else ""
        desc=clean_html(x.get("descriptionHtml") or x.get("descriptionPlain") or x.get("description", ""))
        posted=(x.get("publishedAt") or x.get("postedAt") or "")[:10]
        url=x.get("jobUrl") or x.get("applyUrl") or x.get("url") or ""
        out.append(normalize(company,x.get("title",""),loc,x.get("workplaceType","") or x.get("employmentType",""),x.get("jobType",""),"",x.get("department",""),desc,salary,posted,f"Ashby:{company}",url))
    return out

def smartrecruiters(company,identifier,limit=100):
    out=[]; offset=0
    while True:
        data=get_json(f"https://api.smartrecruiters.com/v1/companies/{identifier}/postings",params={"limit":limit,"offset":offset})
        items=data.get("content",[])
        if not items: break
        for x in items:
            loc=x.get("location") or {}; locs=", ".join(str(v) for v in [loc.get("city"),loc.get("region"),loc.get("country")] if v)
            url=x.get("ref") or ""
            out.append(normalize(company,x.get("name",""),locs,"",x.get("experienceLevel",""),"",x.get("department",{}).get("label","") if isinstance(x.get("department"),dict) else "",clean_html(x.get("jobAd","")),"",(x.get("releasedDate") or "")[:10],f"SmartRecruiters:{company}",url))
        if len(items)<limit: break
        offset += limit
        if offset>=1000: break
    return out


def bamboohr(company, subdomain):
    data=get_json(f"https://{subdomain}.bamboohr.com/careers/list")
    jobs=data.get("jobs",[]) if isinstance(data,dict) else data
    out=[]
    for x in jobs:
        loc=x.get("location") or x.get("city") or ""
        url=x.get("jobUrl") or x.get("url") or f"https://{subdomain}.bamboohr.com/careers/{x.get('id','')}"
        out.append(normalize(company,x.get("jobOpeningName") or x.get("title","") ,loc,"",x.get("employmentStatus",""),"",x.get("departmentLabel") or x.get("department",""),clean_html(x.get("description","")),"",str(x.get("datePosted", ""))[:10],f"BambooHR:{company}",url))
    return out

def workable(company, subdomain):
    data=get_json(f"https://apply.workable.com/api/v1/widget/accounts/{subdomain}",params={"details":"true"})
    jobs=data.get("jobs",[]) if isinstance(data,dict) else data
    out=[]
    for x in jobs:
        loc=x.get("location") or x.get("locations") or ""
        if isinstance(loc,list): loc=", ".join(str(a.get("city") or a.get("name") or a) if isinstance(a,dict) else str(a) for a in loc)
        url=x.get("url") or x.get("shortlink") or x.get("application_url") or ""
        out.append(normalize(company,x.get("title","") ,loc,x.get("workplace_type") or x.get("workplaceType") or "",x.get("experience") or "", "", x.get("department") or "", clean_html(x.get("description") or x.get("description_text") or ""),x.get("salary") or "",str(x.get("published") or x.get("created_at") or "")[:10],f"Workable:{company}",url))
    return out

def recruitee(company, subdomain):
    data=get_json(f"https://{subdomain}.recruitee.com/api/offers/")
    jobs=data.get("offers",[]) if isinstance(data,dict) else data
    out=[]
    for x in jobs:
        loc=x.get("location") or ""
        if isinstance(loc,dict): loc=", ".join(str(v) for v in [loc.get("city"),loc.get("country") ] if v)
        url=x.get("careers_url") or x.get("url") or x.get("slug") and f"https://{subdomain}.recruitee.com/o/{x.get('slug')}" or ""
        out.append(normalize(company,x.get("title","") ,loc,x.get("remote") and "Remote" or "",x.get("experience") or "", "", x.get("department") or "", clean_html(x.get("description") or ""),x.get("salary") or "",str(x.get("published_at") or x.get("created_at") or "")[:10],f"Recruitee:{company}",url))
    return out

def breezy(company, subdomain):
    data=get_json(f"https://{subdomain}.breezy.hr/json")
    jobs=data if isinstance(data,list) else data.get("jobs",[])
    out=[]
    for x in jobs:
        loc=x.get("location") or ""
        if isinstance(loc,dict): loc=", ".join(str(v) for v in [loc.get("city"),loc.get("state"),loc.get("country") ] if v)
        url=x.get("url") or x.get("apply_url") or ""
        out.append(normalize(company,x.get("name") or x.get("title","") ,loc,"",x.get("type") or "", "",x.get("category") or "",clean_html(x.get("description") or ""),x.get("salary") or "",str(x.get("published_date") or "")[:10],f"Breezy:{company}",url))
    return out

def personio(company, subdomain):
    import xml.etree.ElementTree as ET
    r=requests.get(f"https://{subdomain}.jobs.personio.de/xml",headers=HEADERS,timeout=TIMEOUT); r.raise_for_status()
    root=ET.fromstring(r.text); out=[]
    for item in root.findall('.//position') + root.findall('.//job'):
        def tx(name):
            n=item.find(name); return n.text.strip() if n is not None and n.text else ""
        url=tx('jobUrl') or tx('url')
        out.append(normalize(company,tx('name') or tx('title'),tx('office') or tx('location'),"",tx('employmentType'),"",tx('department'),clean_html(tx('description')),tx('salary'),tx('createdAt')[:10],f"Personio:{company}",url))
    return out

def rippling(company, slug):
    data=get_json(f"https://api.rippling.com/platform/api/ats/v1/board/{slug}/jobs")
    jobs=data.get("jobs",[]) if isinstance(data,dict) else data; out=[]
    for x in jobs:
        loc=x.get("location") or x.get("locations") or ""
        if isinstance(loc,list): loc=", ".join(str(a.get("name") or a) if isinstance(a,dict) else str(a) for a in loc)
        url=x.get("url") or x.get("applyUrl") or ""
        out.append(normalize(company,x.get("title","") ,loc,x.get("workplaceType") or "",x.get("experience") or "", "",x.get("department") or "",clean_html(x.get("description") or ""),x.get("salary") or "",str(x.get("postedAt") or x.get("createdAt") or "")[:10],f"Rippling:{company}",url))
    return out

def teamtailor(company, subdomain):
    data=get_json(f"https://{subdomain}.teamtailor.com/jobs.json")
    jobs=data.get("jobs",[]) if isinstance(data,dict) else data; out=[]
    for x in jobs:
        loc=x.get("location") or ""
        if isinstance(loc,dict): loc=", ".join(str(v) for v in [loc.get("city"),loc.get("country") ] if v)
        url=x.get("url") or ""
        out.append(normalize(company,x.get("title","") ,loc,x.get("employment_type") or "",x.get("seniority") or "", "",x.get("department") or "",clean_html(x.get("description") or ""),x.get("salary") or "",str(x.get("created_at") or "")[:10],f"Teamtailor:{company}",url))
    return out

def workday(company, url, limit=100):
    # url should be the company's public myworkdayjobs.com board URL.
    from urllib.parse import urlparse
    u=urlparse(url); parts=[p for p in u.path.split('/') if p]
    if len(parts)<1 or 'myworkdayjobs.com' not in u.netloc: raise ValueError('Workday board URL required')
    site=parts[-1]
    # Common form: https://tenant.wdN.myworkdayjobs.com/site
    tenant=u.netloc.split('.')[0]
    api=f"https://{u.netloc}/wday/cxs/{tenant}/{site}/jobs"
    out=[]; offset=0
    while True:
        r=requests.post(api,headers={**HEADERS,"Content-Type":"application/json"},json={"appliedFacets":{},"limit":limit,"offset":offset},timeout=TIMEOUT); r.raise_for_status(); data=r.json()
        for x in data.get('jobPostings',[]):
            loc=x.get('locationsText') or x.get('location') or ''
            url2=x.get('externalPath') or x.get('url') or ''
            if url2 and url2.startswith('/'): url2='https://'+u.netloc+url2
            out.append(normalize(company,x.get('title',''),loc,'','','',x.get('jobFamily') or '',clean_html(x.get('bulletFields') and ' '.join(x.get('bulletFields')) or x.get('description') or ''),'',str(x.get('postedOn') or '')[:10],f"Workday:{company}",url2 or url))
        if len(data.get('jobPostings',[]))<limit: break
        offset += limit
        if offset>=2000: break
    return out

def himalayas(max_pages=5):
    out=[]; cursor=None
    for _ in range(max_pages):
        params={'limit':20}
        if cursor: params['cursor']=cursor
        data=get_json('https://himalayas.app/jobs/api',params=params)
        for x in data.get('jobs',data.get('results',[])):
            loc=x.get('locationRestrictions') or x.get('location') or x.get('locationRestriction') or 'Remote'
            if isinstance(loc,list): loc=', '.join(str(a) for a in loc)
            company=(x.get('company') or {}).get('name') if isinstance(x.get('company'),dict) else x.get('companyName') or x.get('company') or ''
            out.append(normalize(company,x.get('title',''),loc,'Remote','','',';'.join(x.get('categories') or x.get('tags') or []),clean_html(x.get('description') or x.get('content') or ''),x.get('salary') or '',str(x.get('pubDate') or x.get('publishedAt') or '')[:10],'Himalayas',x.get('applicationLink') or x.get('url') or x.get('link') or ''))
        cursor=data.get('nextCursor')
        if not cursor: break
    return out

def jobicy(max_pages=2):
    out=[]; cursor=None
    for _ in range(max_pages):
        params={'count':200}
        if cursor: params['cursor']=cursor
        data=get_json('https://jobicy.com/api/v2/remote-jobs',params=params)
        for x in data.get('jobs',[]):
            out.append(normalize(x.get('companyName') or x.get('company',''),x.get('jobTitle') or x.get('title',''),x.get('jobGeo') or x.get('location') or 'Remote','Remote',x.get('jobType') or '', '', ';'.join(x.get('jobIndustry') if isinstance(x.get('jobIndustry'),list) else ([x.get('jobIndustry')] if x.get('jobIndustry') else [])),clean_html(x.get('jobDescription') or x.get('description') or ''),x.get('salary') or '',str(x.get('pubDate') or x.get('datePosted') or '')[:10],'Jobicy',x.get('url') or x.get('jobUrl') or ''))
        cursor=data.get('nextCursor')
        if not cursor: break
    return out

def yc_startup_jobs():
    # Public YC jobs directory. HTML parsing is intentionally conservative.
    r=requests.get('https://www.ycombinator.com/jobs/role/all',headers=HEADERS,timeout=TIMEOUT); r.raise_for_status()
    soup=BeautifulSoup(r.text,'html.parser'); out=[]
    for a in soup.select('a[href*="/companies/"]'):
        text=a.get_text(' ',strip=True)
        href=a.get('href','')
        if not text or not href: continue
        # Only retain anchors that look like a job detail/card, not generic company navigation.
        parent=a.parent.get_text(' ',strip=True) if a.parent else text
        if any(k in parent.lower() for k in ['software engineer','developer','data scientist','machine learning','devops','engineering','technical','security','qa','analyst']):
            out.append(normalize(text.split(' · ')[0],text,parent,'','','','',parent,'','', 'Y Combinator Jobs', 'https://www.ycombinator.com'+href if href.startswith('/') else href))
    return out


def career_page(company, url):
    r=requests.get(url,headers=HEADERS,timeout=TIMEOUT); r.raise_for_status()
    soup=BeautifulSoup(r.text,'html.parser'); out=[]
    import json as _json
    for script in soup.find_all('script',type='application/ld+json'):
        try: data=_json.loads(script.string or script.get_text())
        except Exception: continue
        nodes=data if isinstance(data,list) else data.get('@graph',[]) if isinstance(data,dict) else [data]
        if isinstance(nodes,dict): nodes=[nodes]
        for x in nodes:
            if not isinstance(x,dict) or x.get('@type') not in ('JobPosting',['JobPosting']): continue
            loc=x.get('jobLocation') or x.get('jobLocationType') or ''
            if isinstance(loc,list):
                loc='; '.join(str((a.get('address') or {}).get('addressLocality') or (a.get('address') or {}).get('addressCountry') or '') for a in loc if isinstance(a,dict))
            elif isinstance(loc,dict):
                a=loc.get('address') or {}; loc=', '.join(str(v) for v in [a.get('addressLocality'),a.get('addressRegion'),a.get('addressCountry')] if v)
            out.append(normalize(company,x.get('title',''),loc,'Remote' if x.get('jobLocationType') else '',str(x.get('experienceRequirements') or ''),'',str(x.get('skills') or ''),clean_html(x.get('description') or ''),str(x.get('baseSalary') or ''),str(x.get('datePosted') or '')[:10],'Career Page',x.get('url') or url))
    return out

def load_sources(path="config/sources.json"): return json.loads(Path(path).read_text(encoding="utf-8"))

def geo_allowed(job,policy):
    """Keep India jobs AND remote jobs even when the remote job names another country.

    A remote posting may say "Remote - US", "Remote, UK", "Remote - Germany",
    "Worldwide", etc. The search policy intentionally keeps those rather than
    throwing them away based on the country name. Country/work-authorisation
    eligibility is left visible for the candidate to verify on the employer page.
    """
    if not policy.get("enabled", True):
        return True
    location = str(job.get("location") or "").lower()
    work_mode = str(job.get("work_mode") or "").lower()
    description = str(job.get("description") or "").lower()[:5000]
    text = " ".join([location, work_mode, description])

    india = any(x in (location + " " + work_mode) for x in [
        "india", "bangalore", "bengaluru", "hyderabad", "delhi",
        "gurgaon", "gurugram", "noida", "mumbai", "pune",
        "chennai", "kolkata", "ahmedabad", "kochi", "jaipur",
        "remote - india", "india - remote"
    ])

    # Crucially, do NOT require the remote posting to mention India.
    # "Remote - US", "Remote - UK", "Remote - Germany", worldwide, etc.
    # are all retained when allow_remote is enabled.
    remote = any(x in text for x in [
        "remote", "work from home", "work-from-home", "worldwide",
        "work from anywhere", "anywhere in the world", "global remote"
    ])

    return india or (remote and policy.get("allow_remote", True))

def filter_jobs(jobs,cfg):
    from matcher import is_tech_role, fresher_eligible
    policy=cfg.get("search_policy",{})
    out=[]; tech_only=policy.get("tech_only",True)
    fresher_only=policy.get("fresher_only",True)
    max_years=int(policy.get("fresher_max_years",2))
    for job in jobs:
        if not geo_allowed(job,cfg.get("location_policy",{})): continue
        if tech_only and not is_tech_role(job.get("title",""),job.get("description","")): continue
        if fresher_only and not fresher_eligible(job,max_years=max_years): continue
        out.append(job)
    return out

def collect_all():
    cfg=load_sources(); jobs=[]; errors=[]; stats={}
    def run(name,fn):
        try:
            items=fn(); jobs.extend(items); stats[name]=len(items)
        except Exception as e:
            stats[name]=0; errors.append(f"{name}: {e}")
    feeds=cfg.get("public_feeds",{})
    if feeds.get("remoteok",{}).get("enabled"): run("Remote OK",remoteok)
    if feeds.get("arbeitnow",{}).get("enabled"): run("Arbeitnow",lambda:arbeitnow(feeds["arbeitnow"].get("max_pages",1)))
    if feeds.get("remotive",{}).get("enabled"): run("Remotive",remotive)
    for item in cfg.get("greenhouse",[]):
        if item.get("enabled",True): run(f"Greenhouse:{item['company']}",lambda i=item:greenhouse(i["company"],i["board_token"]))
    for item in cfg.get("lever",[]):
        if item.get("enabled",True): run(f"Lever:{item['company']}",lambda i=item:lever(i["company"],i["site"]))
    for item in cfg.get("ashby",[]):
        if item.get("enabled",True): run(f"Ashby:{item['company']}",lambda i=item:ashby(i["company"],i["board_name"]))
    for item in cfg.get("smartrecruiters",[]):
        if item.get("enabled",True): run(f"SmartRecruiters:{item['company']}",lambda i=item:smartrecruiters(i["company"],i["identifier"]))
    for key, fn in [("bamboohr",bamboohr),("workable",workable),("recruitee",recruitee),("breezy",breezy),("personio",personio),("teamtailor",teamtailor),("rippling",rippling)]:
        for item in cfg.get(key,[]):
            if item.get("enabled",True):
                arg=item.get("subdomain") or item.get("slug") or item.get("company_slug")
                run(f"{key.title()}:{item['company']}",lambda i=item,k=key,a=arg:globals()[k](i["company"],a))
    for item in cfg.get("workday",[]):
        if item.get("enabled",True): run(f"Workday:{item['company']}",lambda i=item:workday(i["company"],i["board_url"]))
    feeds2=cfg.get("additional_public_feeds",{})
    if feeds2.get("himalayas",{}).get("enabled"): run("Himalayas",lambda:himalayas(feeds2["himalayas"].get("max_pages",5)))
    if feeds2.get("jobicy",{}).get("enabled"): run("Jobicy",lambda:jobicy(feeds2["jobicy"].get("max_pages",2)))
    if feeds2.get("yc_jobs",{}).get("enabled"): run("Y Combinator Jobs",yc_startup_jobs)
    for item in cfg.get("career_pages",[]):
        if item.get("enabled",True): run(f"Career Page:{item['company']}",lambda i=item:career_page(i["company"],i["url"]))
    # Automatic company-career discovery: inspect official career pages, detect public ATS boards,
    # and collect JSON-LD JobPosting data without requiring the user to know ATS tokens.
    registry=cfg.get("company_registry",{}).get("companies",[]) if cfg.get("company_registry",{}).get("enabled",True) else []
    for item in registry:
        if not item.get("enabled",True): continue
        try:
            found=discover(item["company"],item["career_url"])
            if found.get("jobs"): jobs.extend(found["jobs"]); stats[f"Career Discovery:{item['company']}"]=len(found["jobs"])
            else: stats.setdefault(f"Career Discovery:{item['company']}",0)
            # Collect public ATS boards discovered on the official page.
            for a in found.get("ats",[]):
                kind=a.get("type")
                for value in a.get("values",[]):
                    try:
                        if kind=="greenhouse":
                            items=greenhouse(item["company"],value); jobs.extend(items); stats[f"Auto Greenhouse:{item['company']}:{value}"]=len(items)
                        elif kind=="lever":
                            items=lever(item["company"],value); jobs.extend(items); stats[f"Auto Lever:{item['company']}:{value}"]=len(items)
                        elif kind=="ashby":
                            items=ashby(item["company"],value); jobs.extend(items); stats[f"Auto Ashby:{item['company']}:{value}"]=len(items)
                        elif kind=="smartrecruiters":
                            items=smartrecruiters(item["company"],value); jobs.extend(items); stats[f"Auto SmartRecruiters:{item['company']}:{value}"]=len(items)
                        elif kind=="workday":
                            items=workday(item["company"],value); jobs.extend(items); stats[f"Auto Workday:{item['company']}" ]=len(items)
                        elif kind=="teamtailor":
                            items=teamtailor(item["company"],value); jobs.extend(items); stats[f"Auto Teamtailor:{item['company']}" ]=len(items)
                        elif kind=="recruitee":
                            items=recruitee(item["company"],value); jobs.extend(items); stats[f"Auto Recruitee:{item['company']}" ]=len(items)
                        elif kind=="personio":
                            items=personio(item["company"],value); jobs.extend(items); stats[f"Auto Personio:{item['company']}" ]=len(items)
                        elif kind=="bamboohr":
                            items=bamboohr(item["company"],value); jobs.extend(items); stats[f"Auto BambooHR:{item['company']}" ]=len(items)
                        elif kind=="workable":
                            items=workable(item["company"],value); jobs.extend(items); stats[f"Auto Workable:{item['company']}" ]=len(items)
                        elif kind=="breezy":
                            items=breezy(item["company"],value); jobs.extend(items); stats[f"Auto Breezy:{item['company']}" ]=len(items)
                    except Exception as e:
                        errors.append(f"Auto {kind}:{item['company']}:{value}: {e}")
            if found.get("error"): errors.append(f"Career Discovery:{item['company']}: {found['error']}")
        except Exception as e:
            errors.append(f"Career Discovery:{item['company']}: {e}")
    raw=len(jobs); filtered=filter_jobs(jobs,cfg); return filtered,errors,raw,stats
