import re, json, time, urllib.robotparser
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

HEADERS={"User-Agent":"JobHunterCompanyDiscovery/1.0 (personal job discovery tool)"}
TIMEOUT=25
ATS_PATTERNS={
    "greenhouse": re.compile(r"https?://(?:job-boards|boards)\.greenhouse\.io/([A-Za-z0-9_-]+)",re.I),
    "lever": re.compile(r"https?://jobs\.lever\.co/([A-Za-z0-9_-]+)",re.I),
    "ashby": re.compile(r"https?://jobs\.ashbyhq\.com/([A-Za-z0-9_-]+)",re.I),
    "smartrecruiters": re.compile(r"https?://careers\.smartrecruiters\.com/([A-Za-z0-9_-]+)",re.I),
    "workday": re.compile(r"https?://[^\"'<> ]*myworkdayjobs\.com/[^\"'<> ]+",re.I),
    "teamtailor": re.compile(r"https?://([A-Za-z0-9_-]+)\.teamtailor\.com",re.I),
    "recruitee": re.compile(r"https?://([A-Za-z0-9_-]+)\.recruitee\.com",re.I),
    "personio": re.compile(r"https?://([A-Za-z0-9_-]+)\.jobs\.personio\.[a-z.]+",re.I),
    "bamboohr": re.compile(r"https?://([A-Za-z0-9_-]+)\.bamboohr\.com/careers",re.I),
    "workable": re.compile(r"https?://apply\.workable\.com/([A-Za-z0-9_-]+)",re.I),
    "breezy": re.compile(r"https?://([A-Za-z0-9_-]+)\.breezy\.hr",re.I),
}

def allowed(url):
    try:
        p=urlparse(url); robots=urljoin(f"{p.scheme}://{p.netloc}","/robots.txt")
        rp=urllib.robotparser.RobotFileParser(); rp.set_url(robots); rp.read()
        return rp.can_fetch(HEADERS["User-Agent"],url)
    except Exception:
        return True

def fetch(url):
    if not allowed(url): return None
    r=requests.get(url,headers=HEADERS,timeout=TIMEOUT,allow_redirects=True); r.raise_for_status(); return r

def extract_jsonld_jobs(company,url,soup):
    jobs=[]
    for script in soup.find_all('script',type='application/ld+json'):
        try: data=json.loads(script.string or script.get_text())
        except Exception: continue
        nodes=[]
        if isinstance(data,list): nodes=data
        elif isinstance(data,dict) and '@graph' in data: nodes=data['@graph'] if isinstance(data['@graph'],list) else [data['@graph']]
        elif isinstance(data,dict): nodes=[data]
        for x in nodes:
            if not isinstance(x,dict): continue
            typ=x.get('@type')
            if typ!='JobPosting' and not (isinstance(typ,list) and 'JobPosting' in typ): continue
            loc=x.get('jobLocation') or x.get('jobLocationType') or ''
            if isinstance(loc,list):
                vals=[]
                for a in loc:
                    if isinstance(a,dict):
                        ad=a.get('address') or {}; vals.append(', '.join(str(v) for v in [ad.get('addressLocality'),ad.get('addressRegion'),ad.get('addressCountry')] if v))
                loc='; '.join(v for v in vals if v)
            elif isinstance(loc,dict):
                ad=loc.get('address') or {}; loc=', '.join(str(v) for v in [ad.get('addressLocality'),ad.get('addressRegion'),ad.get('addressCountry')] if v)
            jobs.append({"company":company,"title":x.get('title',''),"location":loc,"work_mode":"Remote" if x.get('jobLocationType') else '',"experience":str(x.get('experienceRequirements') or ''),"education":"","skills":str(x.get('skills') or ''),"description":BeautifulSoup(str(x.get('description') or ''),'html.parser').get_text(' ',strip=True),"salary":str(x.get('baseSalary') or ''),"posted_date":str(x.get('datePosted') or '')[:10],"source":f"Career Discovery:{company}","source_url":x.get('url') or url,"official_url":x.get('url') or url})
    return jobs

def discover(company,url):
    result={"company":company,"url":url,"ats":[],"jobs":[],"error":""}
    try:
        r=fetch(url)
        if r is None: return result
        soup=BeautifulSoup(r.text,'html.parser')
        result['jobs']=extract_jsonld_jobs(company,r.url,soup)
        html=str(soup)
        links=[a.get('href','') for a in soup.find_all('a',href=True)]
        corpus=html+'\n'+'\n'.join(urljoin(r.url,x) for x in links)
        for kind,pat in ATS_PATTERNS.items():
            seen=[]
            for m in pat.finditer(corpus):
                val=m.group(1) if m.lastindex else m.group(0)
                if val not in seen: seen.append(val)
            if seen: result['ats'].append({"type":kind,"values":seen[:10]})
    except Exception as e:
        result['error']=str(e)
    return result
