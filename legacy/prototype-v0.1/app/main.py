"""Visit Tigray: public cultural discovery MVP and moderated Bureau CMS.

All itinerary recommendations are illustrative; no live travel clearance/booking is asserted.
"""
from __future__ import annotations
import hmac
import json
import os
import re
import sqlite3
import urllib.request
import urllib.error
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parent.parent
DB = Path(os.getenv('DATABASE_PATH', str(ROOT / 'data' / 'tigray.sqlite3')))
DB.parent.mkdir(parents=True, exist_ok=True)
app = FastAPI(title='Visit Tigray · SERK', version='0.1.0', docs_url='/api/docs')
app.mount('/static', StaticFiles(directory=str(ROOT/'static')), name='static')

DESTINATIONS = [
  ('aksum','Aksum','Ancient civilization','Where stone monuments hold the memory of a civilization.','Aksum',14.122,38.725,'history','Ancient obelisks, archaeology and living heritage','Sacred-site photography, site access and historical claims must be reviewed by custodians.'),
  ('gheralta','Gheralta Mountains','Rock-hewn heritage','Sandstone cliffs and centuries of artistic and spiritual tradition.','Hawzen',13.98,39.39,'adventure','Rock-hewn churches, spectacular landscape and art','Access may involve difficult terrain, religious permissions and verified local arrangements.'),
  ('mekelle','Mekelle','Creative city','A living capital of food, conversation, culture and contemporary art.','Mekelle',13.4967,39.4753,'culture','Museums, cafes, craft and urban cultural experiences','Operating details and visitor services require local verification.'),
  ('wukro','Wukro','Living traditions','An encounter with exceptional rock-cut architectural traditions.','Wukro',13.793,39.6,'heritage','Architecture and community-led heritage interpretation','Church custodians control access and sensitive documentation.'),
  ('yeha','Yeha','Ancient origins','Explore the traces of one of the region’s earliest monumental centers.','Yeha',14.285,39.019,'history','Archaeological landscapes and early history','Interpretation and visitor access should be validated by heritage authorities.'),
  ('adwa','Adwa','History and memory','A landscape of enduring historical significance and collective remembrance.','Adwa',14.17,38.90,'history','Historical learning and memorial interpretation','Historical narratives should be community-reviewed.'),
]

def now(): return datetime.now(timezone.utc).isoformat()

@contextmanager
def connection():
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    try:
        yield c
        c.commit()
    finally:
        c.close()

def init_db():
    with connection() as c:
        c.execute('PRAGMA journal_mode=WAL')
        c.executescript('''
        CREATE TABLE IF NOT EXISTS destinations (
          slug TEXT PRIMARY KEY, name TEXT NOT NULL, eyebrow TEXT NOT NULL,
          description TEXT NOT NULL, area TEXT NOT NULL, lat REAL, lng REAL,
          category TEXT NOT NULL, highlights TEXT NOT NULL, advisory TEXT NOT NULL,
          published INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS memories (
          id TEXT PRIMARY KEY, display_name TEXT NOT NULL, title TEXT NOT NULL,
          story TEXT NOT NULL, destination TEXT NOT NULL,
          image_url TEXT, consent INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
          created_at TEXT NOT NULL, featured INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS contests (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL,
          prize TEXT NOT NULL, rules TEXT NOT NULL, closing_date TEXT,
          status TEXT NOT NULL DEFAULT 'draft');
        CREATE TABLE IF NOT EXISTS audit_log (
          id TEXT PRIMARY KEY, action TEXT NOT NULL, resource TEXT NOT NULL,
          resource_id TEXT, occurred_at TEXT NOT NULL);
        ''')
        for d in DESTINATIONS:
            c.execute('''INSERT OR IGNORE INTO destinations
            (slug,name,eyebrow,description,area,lat,lng,category,highlights,advisory)
            VALUES (?,?,?,?,?,?,?,?,?,?)''', d)
        c.execute('''INSERT OR IGNORE INTO contests(id,title,description,prize,rules,status)
            VALUES (?,?,?,?,?,?)''', ('memories-2026','Tigray Through Your Eyes',
            'Share an original photograph and personal memory of Tigray.',
            'Awards to be announced by the Bureau after sponsorship and rules approval.',
            'Original work only; permission and age verification required; no public voting for prizes until anti-fraud measures are in place.', 'draft'))
init_db()

class MemoryIn(BaseModel):
    display_name: str = Field(min_length=2,max_length=80)
    title: str = Field(min_length=5,max_length=120)
    story: str = Field(min_length=30,max_length=4000)
    destination: str = Field(min_length=2,max_length=100)
    image_url: str | None = Field(default=None,max_length=500)
    consent: bool
    @field_validator('image_url')
    @classmethod
    def secure_url(cls, v):
        if v and not re.fullmatch(r'https://[^\s<>"\']+',v):
            raise ValueError('Only HTTPS image links are accepted; uploads are planned for a later release.')
        return v

class PlanningIn(BaseModel):
    interests: list[Literal['history','heritage','culture','adventure']] = Field(default_factory=lambda:['history'])
    days: int = Field(default=3,ge=1,le=14)
    pace: Literal['relaxed','balanced','full']='balanced'
    question: str = Field(default='',max_length=1200)

class StatusIn(BaseModel):
    status: Literal['pending','approved','rejected']
    featured: bool = False

class DestinationEdit(BaseModel):
    description: str = Field(min_length=20,max_length=2000)
    advisory: str = Field(min_length=10,max_length=1000)
    published: bool

def admin_guard(token: str | None):
    expected=os.getenv('ADMIN_TOKEN','')
    if not expected or expected=='replace-with-a-long-random-secret':
        raise HTTPException(503,'Bureau management disabled until ADMIN_TOKEN is configured.')
    if not token or not hmac.compare_digest(token,expected):
        raise HTTPException(401,'Invalid Bureau access token')

def audit(c,action,resource,rid):
    c.execute('INSERT INTO audit_log VALUES (?,?,?,?,?)',(str(uuid4()),action,resource,rid,now()))

@app.get('/')
def index(): return FileResponse(ROOT/'static'/'index.html')

@app.get('/api/health')
def health(): return {'status':'ok','app':'Visit Tigray','stage':'public preview'}

@app.get('/api/destinations')
def destinations(category: str | None=None):
    with connection() as c:
        rows=c.execute('SELECT * FROM destinations WHERE published=1 ORDER BY name').fetchall()
    return [dict(x) for x in rows if category is None or x['category']==category]

@app.get('/api/destinations/{slug}')
def destination(slug:str):
    with connection() as c:
        x=c.execute('SELECT * FROM destinations WHERE slug=? AND published=1',(slug,)).fetchone()
    if not x: raise HTTPException(404,'Destination not found')
    return dict(x)

@app.post('/api/memories', status_code=201)
def submit_memory(item:MemoryIn):
    if not item.consent: raise HTTPException(400,'Explicit publication consent is required')
    ident=str(uuid4())
    with connection() as c:
        c.execute('''INSERT INTO memories(id,display_name,title,story,destination,image_url,consent,status,created_at)
          VALUES (?,?,?,?,?,?,?,'pending',?)''', (ident,item.display_name,item.title,item.story,item.destination,item.image_url,1,now()))
        audit(c,'create','memory',ident)
    return {'id':ident,'status':'pending','message':'Submitted for human editorial review. Nothing is published automatically.'}

@app.get('/api/memories')
def public_memories():
    with connection() as c:
        return [dict(x) for x in c.execute('''SELECT id,display_name,title,story,destination,image_url,created_at,featured
          FROM memories WHERE status='approved' ORDER BY featured DESC, created_at DESC LIMIT 100''')]

@app.get('/api/contests')
def contests():
    with connection() as c:
        return [dict(x) for x in c.execute("SELECT * FROM contests WHERE status='open'")]

def rule_plan(p:PlanningIn):
    with connection() as c:
        all_d=[dict(x) for x in c.execute('SELECT * FROM destinations WHERE published=1')]
    ranked=sorted(all_d,key=lambda d:(d['category'] not in p.interests,d['name']))
    count=min(len(ranked),p.days*(1 if p.pace=='relaxed' else 2 if p.pace=='balanced' else 3))
    selected=ranked[:count]
    days=[{'day':i+1,'stops':[{'name':d['name'],'area':d['area'],'slug':d['slug'],'reason':d['highlights'],'advisory':d['advisory']} for d in selected[i*max(1,(count+p.days-1)//p.days):(i+1)*max(1,(count+p.days-1)//p.days)]]} for i in range(p.days)]
    return {'mode':'curated-preview','title':f'{p.days}-day cultural discovery concept','days':days,
      'notice':'Not a confirmed travel route, safety assessment or booking. Do not travel based on this plan; verify current advisories, permissions, transport and site access with authorities.',
      'recommendations_source':'Editorial preview dataset; logistics and security are not live-verified.'}

@app.post('/api/plan')
def plan(p:PlanningIn):
    base=rule_plan(p)
    key=os.getenv('AI_API_KEY','')
    model=os.getenv('AI_MODEL','')
    if not key or not model:
        return base
    # AI enrichment uses only the curated context; suppress unsupported itinerary details.
    context=[{'name':s['name'],'reason':s['reason'],'advisory':s['advisory']} for day in base['days'] for s in day['stops']]
    payload={'model':model,'temperature':0.3,'max_tokens':450,'messages':[
        {'role':'system','content':"You are Visit Tigray's cultural interpretation assistant. Use ONLY the supplied editorial data. Do not invent opening times, fares, routes, access, travel safety, permits or live conditions. This is virtual/inspirational planning, not permission to travel. Respect religious custodians and cultural sensitivities. If asked safety-related questions, explain the need for official verification. Be concise."},
        {'role':'user','content':json.dumps({'question':p.question,'interests':p.interests,'destinations':context})}
    ]}
    try:
        request=urllib.request.Request(os.getenv('AI_BASE_URL','https://api.openai.com/v1').rstrip('/')+'/chat/completions',
            data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(request,timeout=8) as response:
            answer=json.load(response)['choices'][0]['message']['content']
        base['mode']='ai-assisted-curated'
        base['guide']=str(answer)[:3500]
    except (urllib.error.URLError,TimeoutError,KeyError,ValueError,IndexError):
        base['guide']='AI guide unavailable. Showing verified editorial preview instead.'
    return base

@app.get('/api/admin/overview')
def overview(x_admin_token:str|None=Header(default=None)):
    admin_guard(x_admin_token)
    with connection() as c:
        counts={t:c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ['destinations','memories','contests']}
        counts['pending_memories']=c.execute("SELECT COUNT(*) FROM memories WHERE status='pending'").fetchone()[0]
    return counts

@app.get('/api/admin/memories')
def review_memories(x_admin_token:str|None=Header(default=None)):
    admin_guard(x_admin_token)
    with connection() as c: return [dict(x) for x in c.execute('SELECT * FROM memories ORDER BY created_at DESC LIMIT 200')]

@app.patch('/api/admin/memories/{ident}')
def moderate(ident:str,item:StatusIn,x_admin_token:str|None=Header(default=None)):
    admin_guard(x_admin_token)
    with connection() as c:
        res=c.execute('UPDATE memories SET status=?,featured=? WHERE id=?',(item.status,int(item.featured and item.status=='approved'),ident))
        if not res.rowcount: raise HTTPException(404,'Memory not found')
        audit(c,'moderate-'+item.status,'memory',ident)
    return {'ok':True}

@app.patch('/api/admin/destinations/{slug}')
def edit_destination(slug:str,item:DestinationEdit,x_admin_token:str|None=Header(default=None)):
    admin_guard(x_admin_token)
    with connection() as c:
        res=c.execute('UPDATE destinations SET description=?,advisory=?,published=? WHERE slug=?',
              (item.description,item.advisory,int(item.published),slug))
        if not res.rowcount: raise HTTPException(404,'Destination not found')
        audit(c,'edit','destination',slug)
    return {'ok':True}

@app.get('/api/admin/audit')
def audits(x_admin_token:str|None=Header(default=None)):
    admin_guard(x_admin_token)
    with connection() as c: return [dict(x) for x in c.execute('SELECT * FROM audit_log ORDER BY occurred_at DESC LIMIT 100')]
