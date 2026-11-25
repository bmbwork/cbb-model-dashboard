// Exercise the deployed SQL against a small archive with independently reported books.
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { PGlite } = require(process.env.PGLITE_MODULE || '@electric-sql/pglite');

async function main() {
  const db = new PGlite();
  try {
    await db.exec(`
      create role anon;
      create role authenticated;
      create role service_role;
      create table cbb_slates(slate_date date, board_json jsonb);
      create table cbb_slate_revisions(slate_date date, record jsonb);
      create table cbb_game_context(slate_date date);
      create table cbb_stats_team_season(season int);
      create table college_game_history(sport text, season int, start_time timestamptz, event_id text, home_team text, away_team text);
      create table college_history_refresh_runs(sport text, season int, status text, complete boolean, completed_at timestamptz);
      create table cbb_owls_best_odds_archive(id text, archive_event_key text, provider text, provider_event_id text,
        home_team text, away_team text, commence_time_utc timestamptz, captured_at_utc timestamptz,
        snapshot_role text, capture_trigger text, market_type text, book_quotes jsonb);
      create table cbb_market_snapshots(id text, slate_date date, game_id text, provider text, provider_game_id text,
        market_type text, snapshot_time_utc timestamptz, snapshot_role text, home_line numeric, away_line numeric,
        total_line numeric, home_price numeric, away_price numeric, over_price numeric, under_price numeric, source_label text);
      create table cbb_owner_betting_splits(slate_date date, game_id text, provider text, sportsbook_scope text, market_type text, snapshot_time_utc timestamptz);
      create table cbb_consensus_splits(slate_date date, game_id text, market_type text, observed_at timestamptz, side text);
      insert into cbb_slates values ('2020-11-24','[{"Game ID":"g1","Start Time UTC":"2020-11-24T20:00:00Z","Home Team":"Home","Away Team":"Away"}]');
      insert into cbb_slate_revisions values ('2020-11-24','{"board_json":[{"Game ID":"g1","Start Time UTC":"2020-11-24T20:10:00Z","Home Team":"Home","Away Team":"Away"}]}');
      insert into cbb_market_snapshots values
        ('first','2020-11-24','g1','owls_insight_odds','ev','total','2020-11-24T18:00Z','observed',null,null,155,null,null,-110,-110,'Owls Insight · DraftKings'),
        ('middle','2020-11-24','g1','owls_insight_odds','ev','total','2020-11-24T19:00Z','observed',null,null,156,null,null,-110,-110,'Owls Insight · DraftKings'),
        ('latest','2020-11-24','g1','owls_insight_odds','ev','total','2020-11-24T19:55Z','observed',null,null,157,null,null,-110,-110,'Owls Insight · DraftKings'),
        ('invalid','2020-11-24','g1','owls_insight_odds','ev','total','2020-11-24T19:57Z','observed',null,null,158,null,null,0,-110,'Owls Insight · DraftKings');
      insert into cbb_owner_betting_splits values ('2020-11-24','g1','owls_insight','DraftKings','spread','2020-11-24T19:55Z');
    `);
    for (const [id, time, quotes, phase = 'observed', trigger = 'scheduled_hourly'] of [
      ['first', '18:00', [{ book_key: 'draftkings', away_line: 4, home_line: -4 }]],
      ['middle', '19:00', [{ book_key: 'draftkings', away_line: 5, home_line: -5 }]],
      ['new-book', '19:20', [{ book_key: 'caesars', away_line: 4.5, home_line: -4.5 }]],
      ['before-tip', '19:55', [{ book_key: 'draftkings', away_line: '6.0', home_line: '-6.0' }]],
      ['invalid', '19:57', [{ book_key: 'draftkings', away_line: null, home_line: null }]],
      ['later-revision', '20:05', [{ book_key: 'draftkings', away_line: 6.5, home_line: -6.5 }]],
      ['past-tip', '20:15', [{ book_key: 'draftkings', away_line: 7, home_line: -7 }]],
      ['final-pregame', '19:55', [{ book_key: 'draftkings', away_line: 6, home_line: -6 }], 'close', 'scheduled_close_guard'],
    ]) {
      const books = quotes.map((quote) => ({ home_price: -110, away_price: -110, ...quote }));
      await db.query(
        `insert into cbb_owls_best_odds_archive values
         ($1,'archive','owls_insight','ev','Home','Away','2020-11-24T20:25Z',$2,$3,$4,'spread',$5::jsonb)`,
        [id, '2020-11-24T' + time + 'Z', phase, trigger, JSON.stringify(books)],
      );
    }
    await db.exec(readFileSync('supabase/migrations/20261125030222_compact_cbb_mobile_market_history.sql', 'utf8'));
    const { rows: [{ board }] } = await db.query("select public.mobile_research_source_v14('2020-11-24') as board");
    const marketIds = new Set(board.markets.map((row) => row.id));
    for (const id of ['first', 'new-book', 'before-tip', 'later-revision', 'final-pregame']) assert(marketIds.has(id), id);
    for (const id of ['middle', 'past-tip']) assert(!marketIds.has(id), id);
    assert.deepEqual(board.pairedMarkets.map((row) => row.id), ['first', 'latest']);
    assert.equal(board.records.length, 2);
    assert.equal(board.splits.length, 1);
    assert.equal((await db.query('select count(*)::int as n from cbb_owls_best_odds_archive')).rows[0].n, 8);
    const { rows: [roles] } = await db.query(`select
      has_function_privilege('service_role','public.mobile_research_source_v14(text,text,text)','execute') as service,
      has_function_privilege('anon','public.mobile_research_source_v14(text,text,text)','execute') as anon,
      has_function_privilege('authenticated','public.mobile_research_source_v14(text,text,text)','execute') as authenticated`);
    assert.deepEqual(roles, { service: true, anon: false, authenticated: false });
    console.log('CBB mobile SQL preserves per-book endpoints, tipoff boundaries, market roles, and access');
  } finally {
    await db.close();
  }
}
main().catch((error) => { console.error(error); process.exitCode = 1; });
