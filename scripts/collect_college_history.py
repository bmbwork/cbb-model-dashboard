"""Verified season finals and game-time AP context. No model or market writes."""
from __future__ import annotations
import argparse
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import json
import math
import os
import re
import unicodedata
import requests

UTC=timezone.utc
SOURCES={'cfb':'https://api.collegefootballdata.com','cbb':'https://api.collegebasketballdata.com'}

def dt(value):
    if not isinstance(value,str) or not value.strip(): return None
    try: result=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError: return None
    return result.astimezone(UTC) if result.tzinfo else None

def number(value):
    if isinstance(value,bool): return None
    try: result=float(value)
    except (ValueError,TypeError): return None
    return int(result) if math.isfinite(result) and result.is_integer() and result>=0 else None

def name(value):
    return ' '.join(re.sub(r'[^a-z0-9]+',' ',''.join(c for c in unicodedata.normalize('NFKD',str(value or '')) if not unicodedata.combining(c)).lower()).split())

def request_list(session,url,token,params):
    response=session.get(url,params=params,headers={'Authorization':f'Bearer {token}'},timeout=45)
    response.raise_for_status(); data=response.json()
    if not isinstance(data,list) or any(not isinstance(x,dict) for x in data):
        raise ValueError('Provider did not return a complete list')
    return data

def polls_cfb(payload,season):
    result={}
    for p in payload:
        if p.get('season')!=season: continue
        for poll in p.get('polls',[]):
            if name(poll.get('poll'))!='ap top 25': continue
            values={name(x.get('school')):number(x.get('rank')) for x in poll.get('ranks',[])}
            values={k:v for k,v in values.items() if k and v is not None and 1<=v<=25}
            if len(values)>=25 and 1 in values.values() and 25 in values.values():
                result[(p.get('seasonType','regular'),p.get('week'))]=values
    return result

def ap_poll(value):
    return name(value) in ('ap','ap top 25','associated press','associated press top 25')

def poll_moment(value):
    # A date-only or midnight publication stamp is a calendar-day assertion,
    # not an actual release clock. The poll is safely known after that Eastern
    # calendar day ends. Keep genuine timezone-qualified publication clocks.
    if not isinstance(value,str): return None
    when=dt(value)
    try: day=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError: return None
    if when is None or (day.hour==day.minute==day.second==0):
        bound=datetime(day.year,day.month,day.day,tzinfo=ZoneInfo('America/New_York'))+timedelta(days=1)
        return bound.astimezone(UTC)
    return when

def polls_cbb(payload,season):
    batches=defaultdict(dict)
    for p in payload:
        when=poll_moment(p.get('pollDate')); rank=number(p.get('ranking'))
        if p.get('season')!=season or not ap_poll(p.get('pollType')) or when is None or rank is None or not 1<=rank<=25: continue
        batches[(p.get('seasonType'),p.get('week'),when,str(p.get('pollDate'))[:10])][name(p.get('team'))]=rank
    return sorted([(when,values if len(values)>=25 and 1 in values.values() and 25 in values.values() else None,label) for (_,_,when,label),values in batches.items()],key=lambda x:x[0])

def normalize(sport,season,games,polls,now,quarantine=None):
    """Strict finals only. Malformed eligible finals invalidate full coverage."""
    observed=now.isoformat(); out={}; covered=set(); invalid=0
    for g in games:
        if g.get('season')!=season: raise ValueError('Provider season mismatch')
        if sport=='cfb':
            for side in ('home','away'):
                if g.get(side+'Classification') in ('fbs','fcs') and g.get(side+'Team'): covered.add(g[side+'Team'])
            final=g.get('completed') is True
        else:
            if g.get('seasonType')=='preseason' or 'exhib' in str(g.get('gameType') or '').lower(): continue
            final=str(g.get('status','')).lower()=='final'
        if not final: continue
        if re.search(r'\b(cancelled|canceled|abandoned|exhibition)\b',str(g.get('notes') or g.get('gameNotes') or ''),re.I): continue
        start=dt(g.get('startDate')); h=number(g.get('homePoints')); a=number(g.get('awayPoints'))
        home=str(g.get('homeTeam') or '').strip(); away=str(g.get('awayTeam') or '').strip(); gid=number(g.get('id')); event=str(gid) if gid is not None and gid>0 else ''
        if start is None or start>=now or h is None or a is None or not home or not away or home==away or not event or h==a:
            if quarantine is not None and home and away and home!=away:
                quarantine.update((home,away))
            else: invalid+=1
            continue
        if sport=='cfb':
            ranking=polls.get((g.get('seasonType','regular'),g.get('week'))); rank_at=None
            rank_source=f'CFBD AP Top 25 {season} {g.get("seasonType")} week {g.get("week")}' if ranking else None
            periods=(g.get('homeLineScores'),g.get('awayLineScores')); regulation=4; prefix='cfbd'; home_id=g.get('homeId'); away_id=g.get('awayId')
        else:
            # Midnight/date-only releases do not establish availability earlier
            # on that same calendar day. Prefer the last prior dated full poll.
            eligible=[(t,p,label) for t,p,label in polls if t<start]
            rank_at,ranking,poll_label=eligible[-1] if eligible else (None,None,None)
            rank_source=f'CBBD AP Top 25 poll dated {poll_label}' if ranking else None
            periods=(g.get('homePeriodPoints'),g.get('awayPeriodPoints')); regulation=2; prefix='cbbd'; home_id=g.get('homeTeamId'); away_id=g.get('awayTeamId')
        overtime=None
        if all(isinstance(x,list) and len(x)>=regulation and all(number(v) is not None for v in x) for x in periods) and len(periods[0])==len(periods[1]) and sum(number(v) for v in periods[0])==h and sum(number(v) for v in periods[1])==a:
            overtime=len(periods[0])-regulation
        row={'sport':sport,'season':season,'event_id':event,'start_time':start.isoformat(),'completed_at':None,
             'home_team':home,'away_team':away,'home_team_id':f'{prefix}:{home_id}' if home_id is not None else None,'away_team_id':f'{prefix}:{away_id}' if away_id is not None else None,
             'home_score':h,'away_score':a,'home_rank':ranking.get(name(home)) if ranking else None,'away_rank':ranking.get(name(away)) if ranking else None,
             'rankings_verified':ranking is not None,'ranking_source':rank_source,'ranking_as_of':rank_at.isoformat() if rank_at else None,
             'ranking_semantics':'game_week' if sport=='cfb' else 'dated_poll','game_week':g.get('week') if sport=='cfb' else None,
             'neutral_site':g.get('neutralSite') if isinstance(g.get('neutralSite'),bool) else None,'overtimes':overtime,
             'result_source':'CFBD verified final' if sport=='cfb' else 'CBBD verified final','result_source_url':SOURCES[sport]+'/games','fetched_at':observed}
        if event in out and any(out[event][k]!=row[k] for k in ('home_team','away_team','home_score','away_score','start_time')):
            raise ValueError('Conflicting provider final')
        out[event]=row
    if invalid: raise ValueError(f'Invalid eligible finals: {invalid}')
    return list(out.values()),sorted(covered)

def fetch(sport,season,key,now,session=requests):
    url=SOURCES[sport]
    quarantined=set();metadata={}
    if sport=='cfb':
        games=[]
        for level in ('fbs','fcs'):
            part=request_list(session,url+'/games',key,{'year':season,'seasonType':'both','classification':level})
            if not part: raise ValueError('Empty season schedule')
            games.extend(part)
        raw_polls=request_list(session,url+'/rankings',key,{'year':season,'seasonType':'both'})
        polls=polls_cfb(raw_polls,season)
        rows,covered=normalize(sport,season,games,polls,datetime.now(UTC))
    else:
        games=[]
        for season_type in ('regular','postseason'):
            games.extend(request_list(session,url+'/games',key,{'season':season,'seasonType':season_type}))
        if not games: raise ValueError('Empty season schedule')
        teams=request_list(session,url+'/teams',key,{'season':season})
        if len(teams)<200: raise ValueError(f'Season team directory is incomplete: {len(teams)}')
        raw_polls=request_list(session,url+'/rankings',key,{'season':season,'pollType':'ap'})
        parsed_polls=polls_cbb(raw_polls,season)
        metadata={'ap_rows':sum(ap_poll(p.get('pollType')) for p in raw_polls),'poll_rows':len(raw_polls),'dated_ap_rows':sum(ap_poll(p.get('pollType')) and poll_moment(p.get('pollDate')) is not None for p in raw_polls),'usable_ap_batches':sum(p[1] is not None for p in parsed_polls)}
        rows,_=normalize(sport,season,games,parsed_polls,datetime.now(UTC),quarantine=quarantined)
        covered=sorted({str(t.get('school')).strip() for t in teams if t.get('school') and name(t.get('school')) not in {name(team) for team in quarantined}})
    if not covered: raise ValueError('No verified season membership')
    return rows,covered,sorted(quarantined),metadata

class Rest:
    def __init__(self,url,key): self.url=url.rstrip('/')+'/rest/v1/'; self.headers={'apikey':key,'Authorization':f'Bearer {key}','Content-Type':'application/json'}
    def get(self,table,params):
        r=requests.get(self.url+table,params=params,headers=self.headers,timeout=45);r.raise_for_status();return r.json()
    def post(self,table,rows,params=None):
        r=requests.post(self.url+table,params=params,headers={**self.headers,'Prefer':'resolution=merge-duplicates,return=minimal'},json=rows,timeout=45);r.raise_for_status()

def preserve_observation(rows,previous):
    existing={p['event_id']:p for p in previous}
    for r in rows:
        old=existing.get(r['event_id'])
        if old and all(old.get(k)==r.get(k) for k in ('home_team','away_team','home_score','away_score')) and dt(old.get('start_time'))==dt(r['start_time']) and dt(old.get('fetched_at')):
            r['fetched_at']=old['fetched_at']

def collect(sport,season,db,key,now=None,dry_run=False):
    now=now or datetime.now(UTC); run_id=None
    source='CFBD full FBS/FCS season schedule and game-week AP' if sport=='cfb' else 'CBBD full regular/postseason schedule and dated AP; coverage limited to listed verified teams'
    try:
        rows,covered,quarantined,metadata=fetch(sport,season,key,now)
        result={'sport':sport,'season':season,'complete':True,'games_count':len(rows),'ranked_games_count':sum(1 for r in rows if r['home_rank'] or r['away_rank']),'covered_team_count':len(covered),'quarantined_team_count':len(quarantined),'dry_run':dry_run,**metadata}
        if dry_run: return result
        # Read only this private history table; preserve first-seen final scores
        # on repeated polls. Corrections get a new observed-at bound.
        previous=[];offset=0
        while True:
            page=db.get('college_game_history',{'select':'event_id,start_time,home_team,away_team,home_score,away_score,fetched_at','sport':'eq.'+sport,'season':'eq.'+str(season),'order':'event_id.asc','offset':offset,'limit':500})
            previous.extend(page)
            if len(page)<500: break
            offset+=500
            if offset>=20000: raise ValueError('History exceeds safe pagination bound')
        preserve_observation(rows,previous)
        for start in range(0,len(rows),250): db.post('college_game_history',rows[start:start+250],{'on_conflict':'sport,season,event_id'})
        cutoff=datetime.now(UTC).isoformat(); begin=datetime(season if sport=='cfb' else season-1,7,1,tzinfo=UTC).isoformat()
        db.post('college_history_refresh_runs',{'sport':sport,'season':season,'status':'completed','complete':True,'completed_at':cutoff,'source':source,'games_count':len(rows),'ranked_games_count':result['ranked_games_count'],'covered_teams':covered,'complete_from':begin,'complete_through':cutoff,'error_summary':('Invalid-final team coverage withheld: '+', '.join(quarantined)) if quarantined else None})
        return result
    except Exception as exc:
        if not dry_run and db is not None:
            # Never log provider payloads, header values, credential-bearing URLs,
            # or exception messages that may include those values.
            status=getattr(getattr(exc,'response',None),'status_code',None)
            summary=type(exc).__name__+(f' HTTP {status}' if status else '')
            if isinstance(exc,ValueError) and any(str(exc).startswith(label) for label in ('Provider did not return a complete list','Provider season mismatch','Invalid eligible finals:','Conflicting provider final','Empty season schedule','Season team directory is incomplete','No verified season membership','History exceeds safe pagination bound')):
                summary+=' '+str(exc)
            try: db.post('college_history_refresh_runs',{'sport':sport,'season':season,'status':'failed','complete':False,'completed_at':datetime.now(UTC).isoformat(),'source':source,'error_summary':summary})
            except Exception: pass
        raise

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--sport',required=True,choices=['cfb','cbb']);parser.add_argument('--season',type=int);parser.add_argument('--dry-run',action='store_true');args=parser.parse_args()
    now=datetime.now(UTC);season=args.season or (now.year-(now.month<3) if args.sport=='cfb' else now.year+(now.month>=7))
    if not 2000<=season<=2100: raise SystemExit('Invalid season')
    key=str(os.environ.get('CFBD_API_KEY' if args.sport=='cfb' else 'CBBD_API_KEY') or '').strip()
    if not key or any(ord(c)<33 or ord(c)==127 for c in key): raise SystemExit('Provider credential missing or malformed')
    if not args.dry_run and os.environ.get('GITHUB_REF')!='refs/heads/main': raise SystemExit('Writes require reviewed main')
    db=None if args.dry_run else Rest(os.environ['SUPABASE_URL'],os.environ.get('SUPABASE_SECRET_KEY') or os.environ['SUPABASE_SERVICE_ROLE_KEY'])
    try: print(json.dumps(collect(args.sport,season,db,key,now,args.dry_run),sort_keys=True))
    except Exception as exc:
        status=getattr(getattr(exc,'response',None),'status_code',None)
        result={'sport':args.sport,'season':season,'status':'failed','error':type(exc).__name__,'http_status':status}
        if isinstance(exc,ValueError) and any(str(exc).startswith(label) for label in ('Provider did not return a complete list','Provider season mismatch','Invalid eligible finals:','Conflicting provider final','Empty season schedule','Season team directory is incomplete','No verified season membership','History exceeds safe pagination bound')):
            result['validation_code']=str(exc)
        print(json.dumps(result));raise SystemExit(1)
if __name__=='__main__': main()
