const { test }=require('node:test');const assert=require('node:assert/strict');const {readFileSync}=require('node:fs');const {stripTypeScriptTypes}=require('node:module');const vm=require('node:vm');
async function health(mode='reported'){
 const now=new Date().toISOString();const day=now.slice(0,10);
 const values={cbb_slates:{slate_date:day,board_rows:30},cbb_market_snapshots:{snapshot_time_utc:now},cbb_split_refresh_runs:{completed_at:mode==='stale'?'2000-01-01T00:00:00Z':now,status:mode==='failed'?'failed':'completed',feed_state:mode==='not_reported'?'not_reported':'reported',split_games:mode==='not_reported'?0:20},cbb_consensus_refresh_runs:{completed_at:now,status:'completed',matched_events:10}};
 const db={rpc:async()=>({data:{current_slate_published:mode!=='missing_today',current_slate_rows:mode==='missing_today'?0:30,coverage_verified:mode!=='missing_today'},error:null}),from(name){const q={select(){return q},eq(){return q},order(){return q},limit(){return q},maybeSingle:async()=>({data:values[name],error:null})};return q}};
 const {withClockSkewFallback}=await import('../supabase/functions/stat-factory-health/auth-fetch.mjs');
 let handler;const src=readFileSync('supabase/functions/stat-factory-health/index.ts','utf8').replace(/^import .*;\n/gm,'');
 vm.runInNewContext(stripTypeScriptTypes(src),{createClient:()=>db,withClockSkewFallback,Deno:{env:{get:()=> 'fixture'},serve:h=>handler=h},Date,Response,console});const r=await handler({method:'GET'});assert.equal(r.status,200);return r.json();
}
test('reported fresh splits are independently monitored',async()=>{const h=await health();assert.equal(h.workflow_status,'healthy');assert.equal(h.detail.owl_splits.reported_games,20)});
test('missing provider coverage remains distinct from a failed collector',async()=>{const h=await health('not_reported');assert.equal(h.workflow_status,'healthy');assert.equal(h.detail.owl_splits.availability,'not_reported');assert.equal(h.detail.owl_splits.reported_games,0)});
test('a stale poll produces attention even when odds are fresh',async()=>{const h=await health('stale');assert.equal(h.workflow_status,'attention');assert(h.workflow_summary.includes('split collection is delayed'))});
test('collector failures produce attention even when odds are fresh',async()=>{const h=await health('failed');assert.equal(h.workflow_status,'attention');assert(h.workflow_summary.includes('split collection failed'))});
test('a future board cannot mask missing current-day publication',async()=>{const h=await health('missing_today');assert.equal(h.model_outputs_ok,false);assert.equal(h.workflow_status,'incident');assert.equal(h.detail.current_slate_published,false)});
