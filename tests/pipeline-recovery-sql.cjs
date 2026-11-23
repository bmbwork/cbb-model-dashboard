const {PGlite}=require(process.env.PGLITE_MODULE||'@electric-sql/pglite');
const assert=require('node:assert/strict'),fs=require('node:fs');
async function main(){
 const db=new PGlite();
 try{
  await db.exec('create role anon;create role authenticated;create role service_role bypassrls;create table cbb_slates(slate_date date,revision integer,model_version text,board_rows integer,board_json jsonb,published_at timestamptz);grant select on cbb_slates to service_role;');
  const migration=fs.readdirSync('supabase/migrations').find(x=>x.endsWith('_cbb_pipeline_recovery_ledger.sql'));
  await db.exec(fs.readFileSync('supabase/migrations/'+migration,'utf8'));
  await db.exec('set role service_role');
  const id=(await db.query("select cbb_begin_pipeline_run('odds') id")).rows[0].id;
  assert.ok(id);
  assert.equal((await db.query("select cbb_begin_pipeline_run('odds') id")).rows[0].id,null);
  await db.query("update cbb_pipeline_runs set lease_until=now()-interval '1 minute' where id=$1",[id]);
  const next=(await db.query("select cbb_begin_pipeline_run('odds') id")).rows[0].id;
  assert.notEqual(id,next);
  assert.equal((await db.query("select status from cbb_pipeline_runs where id=$1",[id])).rows[0].status,'abandoned');
  assert.equal((await db.query("select cbb_finish_pipeline_run($1,'completed',2,'{}',null) done",[next])).rows[0].done,true);
  assert.equal((await db.query("select cbb_finish_pipeline_run($1,'completed',2,'{}',null) done",[next])).rows[0].done,false);
  await db.exec('reset role');
  await db.query("insert into cbb_slates values('2026-11-23',1,'1.1.3B',2,$1,now()),('2026-11-24',1,'1.1.3B',2,$2,now())",[JSON.stringify([{'Game ID':1},{'Game ID':2}]),JSON.stringify([{'Game ID':1},{'Game ID':1}])]);
  assert.equal((await db.query("select cbb_current_model_health('2026-11-23') health")).rows[0].health.coverage_verified,true);
  assert.equal((await db.query("select cbb_current_model_health('2026-11-24') health")).rows[0].health.coverage_verified,false);
  assert.equal((await db.query("select cbb_current_model_health('2026-11-25') health")).rows[0].health.current_slate_published,false);
  await db.exec('set role anon');
  await assert.rejects(db.query("select cbb_begin_pipeline_run('grading')"));
  await assert.rejects(db.query("select cbb_current_model_health('2026-11-23')"));
  await assert.rejects(db.query('select * from cbb_pipeline_runs'));
  console.log('CBB PostgreSQL recovery leases, expired-job replay, forecast coverage and private access passed.');
 }finally{await db.close();}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
