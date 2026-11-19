from datetime import datetime, timezone
from types import SimpleNamespace
import copy
import pandas as pd
import pytest
from cbb_dashboard.market import normalize_market_import, snapshots_frame, attach_market_to_board
from cbb_dashboard.premium_ui_patch import premium_betting_splits_html, _money_card
from cbb_dashboard.public_consensus import attach_aggregated_consensus, aggregate_public_books_html
from cbb_dashboard.owlsinsight_provider import OwlsInsightConfig, OwlsInsightSplitsProvider
from cbb_dashboard.owlsinsight_odds_provider import OwlsInsightOddsConfig, OwlsInsightOddsProvider
from cbb_dashboard.split_collection import collect_owls_splits

NOW=datetime(2026,11,19,15,tzinfo=timezone.utc)
STAMP='2026-11-19T14:50:00Z'
TIP='2026-11-19T23:00:00Z'

def board():
    return pd.DataFrame([{'Game ID':'1','Home Team':'Duke','Away Team':'North Carolina','Start Time UTC':TIP,'_start_dt':pd.Timestamp(TIP),'Target Date':'2026-11-19','slate_date':'2026-11-19','Model Pick':'Duke'}])

def split_payload():
    return {'meta':{'as_of':STAMP},'data':[{'event_id':'owl1','home_team':'Duke','away_team':'North Carolina','commence_time':TIP,'splits':[{'book':'circa','title':'Circa','spread':{'home_money_pct':1,'away_money_pct':99,'home_bets_pct':20,'away_bets_pct':80},'moneyline':{'home_money_pct':60,'away_money_pct':40,'home_bets_pct':45,'away_bets_pct':55},'total':{'over_money_pct':55,'under_money_pct':45,'over_bets_pct':40,'under_bets_pct':60}}]}]}

@pytest.mark.parametrize('pair,expected', [((1,99),(1,99)),((.01,.99),(1,99)),((0,100),(0,100)),((1,0),(100,0)),((0,0),(0,0))])
def test_percent_pair_normalization_is_idempotent(pair,expected):
    f=pd.DataFrame([{'Slate Date':'2026-11-19','Game ID':'1','Provider':'owls','Market Type':'spread','Snapshot Time UTC':STAMP,'Home Money %':pair[0],'Away Money %':pair[1]}])
    first=normalize_market_import(f);second=normalize_market_import(first)
    assert tuple(first.iloc[0][['Home Money %','Away Money %']])==expected
    assert tuple(second.iloc[0][['Home Money %','Away Money %']])==expected

def test_latest_odds_do_not_erase_paired_split_sides():
    provider=OwlsInsightSplitsProvider(OwlsInsightConfig('fixture'))
    splits,_=provider.parse(split_payload(),board())
    odds=pd.DataFrame([{'Slate Date':'2026-11-19','Game ID':'1','Provider':'odds','Market Type':kind,'Snapshot Time UTC':'2026-11-19T14:59:00Z','Home Line':-4,'Away Line':4} for kind in ('spread','moneyline','total')])
    out=attach_market_to_board(board(),pd.concat([splits,normalize_market_import(odds)],ignore_index=True))
    html=premium_betting_splits_html(out.iloc[0])
    assert html.count('sf-money-bar')==3
    assert '1%' in html and '99%' in html and '60%' in html
    assert 'Circa' in html
    assert 'Duke -4.0' not in html  # odds are not this split source's line
    assert '14:50' in str(out.iloc[0]['_market_ml_split_time'])

def test_source_home_away_reversal_is_preserved():
    payload=split_payload();event=payload['data'][0];event['home_team'],event['away_team']=event['away_team'],event['home_team']
    f,_=OwlsInsightSplitsProvider(OwlsInsightConfig('fixture')).parse(payload,board())
    spread=f[f['Market Type']=='spread'].iloc[0]
    assert spread['Home Money %']==99 and spread['Away Money %']==1
    assert pd.Timestamp(spread['Snapshot Time UTC'])==pd.Timestamp(STAMP)
    assert pd.Timestamp(spread['Snapshot Time UTC'])!=pd.Timestamp(TIP)

class Client:
    def __init__(self,consensus=None):self.consensus=consensus or [];self.writes=[]
    def table(self,name):self.table_name=name;return self
    def select(self,*a,**k):return self
    def eq(self,*a):return self
    def order(self,*a,**k):return self
    def limit(self,*a):return self
    def insert(self,values):self.writes.append((self.table_name,'insert',copy.deepcopy(values)));return self
    def update(self,values):self.writes.append((self.table_name,'update',copy.deepcopy(values)));return self
    def upsert(self,values,**k):self.writes.append((self.table_name,'upsert',copy.deepcopy(values)));return self
    def execute(self):return SimpleNamespace(data=self.consensus)

def consensus_rows(money=(65,35)):
    return [dict(refresh_run_id='r1',slate_date='2026-11-19',game_id='1',market_type='spread',side=side,line=line,tickets_pct=tickets,handle_pct=handle,observed_at=STAMP) for side,line,tickets,handle in [('spread_away',4,55,money[0]),('spread_home',-4,45,money[1])]]

def test_consensus_money_bars_are_visible_and_separate():
    row=attach_aggregated_consensus(Client(consensus_rows()),board(),'2026-11-19',now=NOW).iloc[0]
    html=aggregate_public_books_html(row)
    assert 'AGGREGATED PUBLIC BOOKS' in html and 'sf-money-bar' in html and '<details' not in html
    assert '65%' in html and 'Tickets:' in html
    assert 'not reported; reported public consensus' in premium_betting_splits_html(row)

def test_invalid_consensus_money_never_becomes_a_money_bar():
    row=attach_aggregated_consensus(Client(consensus_rows((0,0))),board(),'2026-11-19',now=NOW).iloc[0]
    html=aggregate_public_books_html(row)
    assert 'Money not reported' in html and 'sf-money-bar' not in html
    assert _money_card('SPREAD','A',-5,30,'B',105,70)==''

@pytest.mark.parametrize('dry_run',[False,True])
def test_collector_archives_reported_splits_and_does_not_write_forecasts(monkeypatch,dry_run):
    monkeypatch.setattr('cbb_dashboard.split_collection._active_board',lambda *_:board().drop(columns='_start_dt'))
    provider=OwlsInsightSplitsProvider(OwlsInsightConfig('fixture'));monkeypatch.setattr(provider,'live_splits',split_payload)
    client=Client();out=collect_owls_splits(client,provider,now=NOW,dry_run=dry_run)
    assert out['feed_state']=='reported' and out['split_games']==1
    if dry_run:assert not client.writes
    else:
        assert {table for table,_,_ in client.writes}=={'cbb_split_refresh_runs','cbb_owner_betting_splits'}
        raw=[values for table,method,values in client.writes if table=='cbb_owner_betting_splits' and method=='upsert'][0]
        assert len(raw)==3 and raw[0]['snapshot_role']=='observed'
        assert raw[0]['home_money_pct']==1

def test_provider_failure_records_a_safe_error(monkeypatch):
    monkeypatch.setattr('cbb_dashboard.split_collection._active_board',lambda *_:board())
    provider=OwlsInsightSplitsProvider(OwlsInsightConfig('fixture'))
    def failure():raise RuntimeError('provider API secret HIDDEN HTTP 403')
    monkeypatch.setattr(provider,'live_splits',failure)
    client=Client()
    with pytest.raises(RuntimeError,match='HTTP 403'):collect_owls_splits(client,provider,now=NOW)
    assert 'HIDDEN' not in str(client.writes)
    assert client.writes[-1][2]['status']=='failed'

def test_odds_fallback_is_selected_per_market():
    provider=OwlsInsightOddsProvider(OwlsInsightOddsConfig('fixture'))
    event={'id':'q','home_team':'Duke','away_team':'North Carolina','commence_time':TIP,'bookmakers':[
        {'key':'draftkings','title':'DraftKings','markets':[{'key':'h2h','outcomes':[{'name':'Duke','price':-150},{'name':'North Carolina','price':130}]}]},
        {'key':'fanduel','title':'FanDuel','markets':[{'key':'spreads','outcomes':[{'name':'Duke','point':-3.5,'price':-110},{'name':'North Carolina','point':3.5,'price':-110}]},{'key':'totals','outcomes':[{'name':'Over','point':150.5,'price':-110},{'name':'Under','point':150.5,'price':-110}]}]}]}
    rows,fallback=provider.parse_event(event,board().iloc[0],response_timestamp=STAMP)
    assert set(rows['Market Type'])=={'spread','moneyline','total'}
    assert 'DraftKings' in rows[rows['Market Type']=='moneyline'].iloc[0]['Source Label']
    assert 'FanDuel' in rows[rows['Market Type']=='total'].iloc[0]['Source Label']
    assert fallback

def test_market_readers_fetch_beyond_the_api_row_cap():
    from cbb_dashboard.storage import SupabaseSlateStore
    store=SupabaseSlateStore.__new__(SupabaseSlateStore)
    calls=[];data=[{'id':str(i)} for i in range(1251)]
    class Query:
        def range(self,start,end):self.start,self.end=start,end;calls.append((start,end));return self
        def execute(self):return SimpleNamespace(data=data[self.start:self.end+1])
    result=store._paged_rows(Query,20000)
    assert len(result)==1251 and result[-1]['id']=='1250'
    assert calls==[(0,499),(500,999),(1000,1499)]

def test_owl_ticket_only_report_is_not_labelled_as_money():
    row=board().iloc[0].copy()
    row['_market_home_ticket_pct']=30;row['_market_away_ticket_pct']=70
    html=premium_betting_splits_html(row)
    assert 'Tickets:' in html and 'Money not reported' in html and 'sf-money-bar' not in html


def test_stale_and_future_consensus_snapshots_are_distinguished():
    rows=consensus_rows();rows[0]['observed_at']=rows[1]['observed_at']='2026-11-19T10:00:00Z'
    row=attach_aggregated_consensus(Client(rows),board(),'2026-11-19',now=NOW).iloc[0]
    assert row['_aggregate_public_available']
    from cbb_dashboard.public_consensus import split_snapshot_label
    assert 'Stale snapshot' in split_snapshot_label(row['_aggregate_public_last_seen'],row,now=NOW)
    for r in rows:r['observed_at']='2026-11-19T16:00:00Z'
    row=attach_aggregated_consensus(Client(rows),board(),'2026-11-19',now=NOW).iloc[0]
    assert not row['_aggregate_public_available']
