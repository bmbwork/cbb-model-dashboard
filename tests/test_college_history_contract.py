"""Synthetic API contract tests, never production or demo game records."""
import importlib.util
from pathlib import Path
from datetime import datetime,timezone
import unittest
from unittest.mock import patch
p=Path(__file__).resolve().parents[1]/'scripts/collect_college_history.py';spec=importlib.util.spec_from_file_location('college_collector',p);C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)
NOW=datetime(2026,11,21,15,tzinfo=timezone.utc)
def cfb(**kw):
 g=dict(id=1,season=2026,week=4,seasonType='regular',startDate='2026-09-20T16:00:00Z',completed=True,neutralSite=False,homeId=10,awayId=20,homeTeam='Home',awayTeam='Away',homeClassification='fbs',awayClassification='fcs',homePoints=24,awayPoints=17,homeLineScores=[7,7,3,7],awayLineScores=[7,3,0,7]);g.update(kw);return g
def cbb(**kw):
 g=dict(id=2,season=2027,seasonType='regular',startDate='2026-11-18T19:00:00Z',status='final',neutralSite=True,homeTeamId=10,awayTeamId=20,homeTeam='Home',awayTeam='Away',homePoints=80,awayPoints=79,homePeriodPoints=[40,40],awayPeriodPoints=[39,40]);g.update(kw);return g
def poll(when='2026-11-16T17:00:00Z',week=2,count=25):
 return [dict(season=2027,week=week,seasonType='regular',pollDate=when,pollType='ap',team='Away' if i==0 else 'Poll '+str(i),ranking=i+1) for i in range(count)]
class Contracts(unittest.TestCase):
 def test_paired_cfb_and_game_week_ap(self):
  r,covered=C.normalize('cfb',2026,[cfb()],{('regular',4):{'away':5}},NOW)
  self.assertEqual(covered,['Away','Home']);self.assertEqual(r[0]['away_rank'],5);self.assertTrue(r[0]['rankings_verified']);self.assertEqual(r[0]['home_team_id'],'cfbd:10');self.assertEqual(r[0]['overtimes'],0);self.assertIsNone(r[0]['completed_at'])
 def test_no_current_poll_retroactive(self):
  rankings=C.polls_cbb(poll()+poll('2026-11-23T17:00:00Z',3),2027)
  r,_=C.normalize('cbb',2027,[cbb()],rankings,NOW)
  self.assertEqual(r[0]['away_rank'],1);self.assertEqual(r[0]['ranking_as_of'],'2026-11-16T17:00:00+00:00')
 def test_incomplete_new_poll_does_not_reuse_obsolete_poll(self):
  rankings=C.polls_cbb(poll('2026-11-09T17:00:00Z',1)+poll(count=24),2027)
  r,_=C.normalize('cbb',2027,[cbb()],rankings,NOW);self.assertFalse(r[0]['rankings_verified']);self.assertIsNone(r[0]['away_rank'])
 def test_same_day_midnight_is_not_precise_release_time(self):
  rankings=C.polls_cbb(poll('2026-11-18T00:00:00Z'),2027)
  r,_=C.normalize('cbb',2027,[cbb()],rankings,NOW);self.assertFalse(r[0]['rankings_verified'])
 def test_nonfinal_and_exhibition_not_counted(self):
  games=[cbb(status='in_progress'),cbb(id=3,gameType='Exhibition'),cbb(id=4,seasonType='preseason')]
  self.assertEqual(C.normalize('cbb',2027,games,[],NOW)[0],[])
 def test_unknown_rank_is_not_unranked(self):
  r,_=C.normalize('cfb',2026,[cfb()],{},NOW);self.assertFalse(r[0]['rankings_verified']);self.assertIsNone(r[0]['home_rank'])
 def test_invalid_final_fails_full_coverage(self):
  for patch in [{'homePoints':None},{'homePoints':True},{'homePoints':-1},{'awayPoints':2.5},{'startDate':'invalid'},{'startDate':'2027-01-01T00:00:00Z'}]:
   with self.subTest(patch=patch),self.assertRaises(ValueError):C.normalize('cfb',2026,[cfb(**patch)],{},NOW)
 def test_cbb_tie_invalid_cfb_zero_score_valid(self):
  with self.assertRaises(ValueError):C.normalize('cbb',2027,[cbb(homePoints=79)],[],NOW)
  with self.assertRaises(ValueError):C.normalize('cfb',2026,[cfb(homePoints=17)],{},NOW)
  self.assertEqual(C.normalize('cfb',2026,[cfb(homePoints=0,awayPoints=3)],{},NOW)[0][0]['home_score'],0)
 def test_dedup_conflicting_score_fails(self):
  self.assertEqual(len(C.normalize('cfb',2026,[cfb(),cfb()],{},NOW)[0]),1)
  with self.assertRaises(ValueError):C.normalize('cfb',2026,[cfb(),cfb(homePoints=25)],{},NOW)
 def test_non_d1_incidental_team_not_covered(self):
  _,covered=C.normalize('cfb',2026,[cfb(awayClassification='ii')],{},NOW);self.assertEqual(covered,['Home'])
 def test_ot_only_from_matching_reported_periods(self):
  r,_=C.normalize('cbb',2027,[cbb(homePoints=90,awayPoints=88,homePeriodPoints=[40,40,10],awayPeriodPoints=[39,40,9])],[],NOW);self.assertEqual(r[0]['overtimes'],1)
  r,_=C.normalize('cbb',2027,[cbb(homePeriodPoints=None)],[],NOW);self.assertIsNone(r[0]['overtimes'])
 def test_first_observation_preserved_but_correction_new(self):
  r,_=C.normalize('cfb',2026,[cfb()],{},NOW);old={**r[0],'fetched_at':'2026-09-21T00:00:00Z'}
  C.preserve_observation(r,[old]);self.assertEqual(r[0]['fetched_at'],old['fetched_at'])
  r,_=C.normalize('cfb',2026,[cfb(homePoints=25)],{},NOW);C.preserve_observation(r,[old]);self.assertEqual(r[0]['fetched_at'],NOW.isoformat())
 def test_dry_run_does_not_write(self):
  class Refuse:
   def __getattr__(self,_):raise AssertionError('DB touched')
  with patch.object(C,'fetch',return_value=([],['Home'],[],{})):
   self.assertTrue(C.collect('cfb',2026,Refuse(),'TEST',NOW,True)['dry_run'])
 def test_quarantine_blocks_both_teams_but_keeps_verified_other_game(self):
  excluded=set()
  games=[cbb(homePoints=79),cbb(id=3,homeTeam='Other Home',awayTeam='Other Away')]
  rows,_=C.normalize('cbb',2027,games,[],NOW,quarantine=excluded)
  self.assertEqual(excluded,{'Home','Away'});self.assertEqual(len(rows),1);self.assertEqual(rows[0]['event_id'],'3')
 def test_quarantine_cannot_hide_unknown_identity(self):
  with self.assertRaises(ValueError):C.normalize('cbb',2027,[cbb(homeTeam='')],[],NOW,quarantine=set())
 def test_date_only_ap_alias_is_safe_next_day(self):
  payload=poll('2026-11-16')
  for p in payload:p['pollType']='AP Top 25'
  parsed=C.polls_cbb(payload,2027)
  rows,_=C.normalize('cbb',2027,[cbb()],parsed,NOW)
  self.assertEqual(rows[0]['away_rank'],1)
  self.assertEqual(rows[0]['ranking_as_of'],'2026-11-17T05:00:00+00:00')
  self.assertIn('2026-11-16',rows[0]['ranking_source'])
 def test_undated_and_coaches_do_not_become_ap(self):
  payload=poll(None)
  self.assertEqual(C.polls_cbb(payload,2027),[])
  for p in payload:p['pollDate']='2026-11-16';p['pollType']='Coaches'
  self.assertEqual(C.polls_cbb(payload,2027),[])
 def test_uncertain_release_day_never_reuses_obsolete_rank(self):
  payload=poll('2026-11-09T17:00:00Z',1)+poll('2026-11-16')
  rows,_=C.normalize('cbb',2027,[cbb(startDate='2026-11-16T19:00:00Z')],C.polls_cbb(payload,2027),NOW)
  self.assertFalse(rows[0]['rankings_verified'])
 def test_ap_filtered_response_can_omit_redundant_type(self):
  payload=poll('2026-11-16')
  for p in payload:del p['pollType']
  self.assertEqual(C.polls_cbb(payload,2027),[])
  self.assertEqual(len(C.polls_cbb(payload,2027,requested_ap=True)),1)
 def test_cfb_full_poll_required(self):
  ranks=[dict(school='Team'+str(i),rank=i+1) for i in range(25)]
  base=dict(season=2026,seasonType='regular',week=2,polls=[dict(poll='AP Top 25',ranks=ranks)])
  self.assertEqual(len(C.polls_cfb([base],2026)[('regular',2)]),25)
  base['polls'][0]['ranks']=ranks[:-1];self.assertEqual(C.polls_cfb([base],2026),{})
if __name__=='__main__':unittest.main()
