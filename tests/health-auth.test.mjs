import test from 'node:test';
import assert from 'node:assert/strict';
import {withClockSkewFallback} from '../supabase/functions/stat-factory-health/auth-fetch.mjs';
const url='https://fixture.invalid/rest/v1/rpc/cbb_current_model_health';
const initial={method:'POST',body:'{"p_date":"2026-11-23"}',headers:{apikey:'primary','authorization':'Bearer primary','content-type':'application/json'}};
test('Exact JWT clock skew retries once with existing runtime credentials and retains the read request',async()=>{
 const calls=[],fetcher=async(input,init)=>{calls.push({input,init});return calls.length===1?Response.json({message:'JWT issued at future'},{status:401}):Response.json({current_slate_published:true});};
 const response=await withClockSkewFallback('primary','runtime-service',fetcher)(url,initial);
 assert.equal(response.status,200);assert.equal(calls.length,2);assert.equal(calls[1].input,url);
 assert.equal(calls[1].init.method,'POST');assert.equal(calls[1].init.body,initial.body);
 assert.equal(calls[1].init.headers.get('apikey'),'runtime-service');assert.equal(calls[1].init.headers.get('authorization'),'Bearer runtime-service');
 assert.equal(calls[1].init.headers.get('content-type'),'application/json');
 assert.equal(initial.headers.authorization,'Bearer primary');
});
test('Other failures never switch credentials or retry',async()=>{
 for(const message of ['JWT expired','Invalid API key','Provider timeout']){
  let calls=0;const response=await withClockSkewFallback('primary','runtime-service',async()=>{calls++;return Response.json({message},{status:401});})(url,initial);
  assert.equal(response.status,401);assert.equal(calls,1);
 }
});
test('Unavailable or identical fallback credentials fail closed without repeated requests',async()=>{
 for(const fallback of [undefined,'','primary']){
  let calls=0;const response=await withClockSkewFallback('primary',fallback,async()=>{calls++;return Response.json({message:'JWT issued at future'},{status:401});})(url,initial);
  assert.equal(response.status,401);assert.equal(calls,1);
 }
});
test('A failed fallback response is returned once without a retry loop',async()=>{
 let calls=0;const response=await withClockSkewFallback('primary','runtime-service',async()=>{calls++;return Response.json({message:'JWT issued at future'},{status:401});})(url,initial);
 assert.equal(response.status,401);assert.equal(calls,2);
});
