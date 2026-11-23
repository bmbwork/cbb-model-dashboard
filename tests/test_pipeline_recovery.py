from copy import deepcopy
from types import SimpleNamespace
import requests
import pytest
import pandas as pd
from cbb_dashboard.recovery import retry_transport,verified_upsert,safe_error,PipelineRun,AlreadyRunning
from cbb_dashboard.final_results import grade_frozen_board
from scripts.grade_published import grade_records


def test_transient_recovery_is_bounded_and_respects_retry_after():
    calls=[];waits=[]
    def work():
        calls.append(1)
        if len(calls)<3:
            response=requests.Response();response.status_code=429;response.headers['Retry-After']='2'
            raise requests.HTTPError('private provider url',response=response)
        return 'saved'
    assert retry_transport(work,sleep=waits.append)=='saved'
    assert len(calls)==3 and waits==[2,3]


def test_permanent_auth_errors_are_not_retried_or_logged_with_secrets():
    response=requests.Response();response.status_code=401
    error=requests.HTTPError('sensitive text must stay private',response=response)
    calls=[]
    def work():calls.append(1);raise error
    with pytest.raises(requests.HTTPError):retry_transport(work,sleep=lambda _:None)
    assert len(calls)==1
    assert safe_error(error)=='HTTPError HTTP 401'


def test_three_transport_failures_stop():
    calls=[]
    def work():calls.append(1);raise requests.Timeout('provider')
    with pytest.raises(requests.Timeout):retry_transport(work,sleep=lambda _:None)
    assert len(calls)==3


class Store:
    def __init__(self,drop=False):self.rows={};self.drop=drop
    def table(self,name):self.name=name;return self
    def upsert(self,batch,**kw):self.rows.update({r['raw_snapshot_hash']:deepcopy(r) for r in batch});return self
    def select(self,*a):return self
    def in_(self,key,values):self.values=set(values);return self
    def execute(self):return SimpleNamespace(data=[] if self.drop else list(self.rows.values()))


def test_upsert_requires_actual_readback_and_replay_is_idempotent():
    store=Store();records=[{'raw_snapshot_hash':'a'},{'raw_snapshot_hash':'b'}]
    assert verified_upsert(store,'cbb_market_snapshots',records)==2
    assert verified_upsert(store,'cbb_market_snapshots',records)==2
    assert len(store.rows)==2
    with pytest.raises(RuntimeError,match='readback'):verified_upsert(Store(drop=True),'cbb_market_snapshots',records)


def board():
    return pd.DataFrame({'Game ID':[1,2],'Home Team':['H1','H2'],'Away Team':['A1','A2'],'Model Pick':['H1','A2'],'Home Win Probability':[.7,.4],'Projected Home Score':[80,70],'Projected Away Score':[70,72],'Projected Total':[150,142],'D1 Evaluation Eligible':[True,True]})


def record(day,rev,previous=None):
    return {'slate_date':day,'revision':rev,'board_sha256':str(rev),'record':{'board_json':board().to_dict('records'),'grading_json':[] if previous is None else previous.to_dict('records')}}


def test_verified_revision_finals_replay_without_another_provider_request():
    previous=grade_frozen_board(board(),{'1':(80,70),'2':(70,72)})
    records=[record('2000-01-01',1),record('2000-01-01',2,previous)]
    original=deepcopy(records)
    def no_network(day):raise AssertionError('already verified scores must not consume provider quota')
    result=grade_records(None,records,no_network)
    assert result['changed_revisions']==1 and result['provider_dates_requested']==0
    assert result['failed_revisions']==[] and result['settled_revisions_skipped']==1
    assert records==original


def test_one_failed_date_does_not_starve_other_dates_or_repeat_failed_poll():
    records=[record('2000-01-01',1),record('2000-01-01',2),record('2000-01-02',1)]
    calls=[]
    def fetch(day):
        calls.append(day)
        if day=='2000-01-01':raise requests.Timeout('secret not logged')
        return {'1':(80,70),'2':(70,72)}
    result=grade_records(None,records,fetch)
    assert calls==['2000-01-02','2000-01-01']
    assert result['changed_revisions']==1 and len(result['failed_revisions'])==2
    assert all(r['error']=='Timeout' for r in result['failed_revisions'])


def test_official_score_correction_still_requires_review():
    previous=grade_frozen_board(board(),{'1':(80,70)})
    result=grade_records(None,[record('2000-01-01',1,previous)],lambda day:{'1':(81,70),'2':(70,72)})
    assert result['changed_revisions']==0
    assert 'correction requires review' in result['failed_revisions'][0]['error']


def test_an_active_execution_lease_prevents_duplicate_work():
    class Client:
        def rpc(self,*a):return SimpleNamespace(execute=lambda:SimpleNamespace(data=None))
    with pytest.raises(AlreadyRunning):
        with PipelineRun(Client(),'odds'):raise AssertionError('must not run')
