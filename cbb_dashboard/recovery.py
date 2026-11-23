"""Bounded transport recovery and verified writes; no model or access changes."""
from __future__ import annotations
import json
import time
import requests
import httpx


def safe_error(exc):
    response = getattr(exc, 'response', None)
    status = getattr(response, 'status_code', None) or getattr(exc, 'status_code', None)
    text = str(exc)
    known = next((hint for hint in ('CBBD_API_KEY is required','CBBD_API_KEY contains an invalid embedded character','publication readback did not match','correction requires review','Conflicting final scores','Archived CBB revision changed during grading') if hint in text),None)
    return type(exc).__name__ + (f' HTTP {status}' if status else '') + (': '+known if known else '')


def retry_transport(work, *, sleep=time.sleep):
    for attempt in range(3):
        try:
            return work()
        except Exception as exc:
            response = getattr(exc, 'response', None)
            status = getattr(response, 'status_code', None) or getattr(exc, 'status_code', None)
            transient = isinstance(exc, (requests.Timeout, requests.ConnectionError, httpx.TransportError)) or status in (408,429,500,502,503,504) or str(getattr(exc, 'code', '')) in ('57014','53300','57P01')
            if not transient or attempt == 2:
                raise
            wait = (1,3)[attempt]
            try:
                value = float((getattr(response, 'headers', None) or {}).get('Retry-After', wait))
                wait = min(30,max(wait,value))
            except (ValueError,TypeError):
                pass
            sleep(wait)


def verified_upsert(client, table, records, *, batch_size=20):
    """Stable raw hashes make a response-lost retry safe; read back each batch."""
    count = 0
    for start in range(0,len(records),batch_size):
        batch = records[start:start+batch_size]
        hashes = {r['raw_snapshot_hash'] for r in batch}
        retry_transport(lambda: client.table(table).upsert(batch,on_conflict='raw_snapshot_hash').execute())
        saved = retry_transport(lambda: client.table(table).select('raw_snapshot_hash').in_('raw_snapshot_hash',list(hashes)).execute()).data or []
        if {r['raw_snapshot_hash'] for r in saved} != hashes:
            raise RuntimeError('CBB '+table+' publication readback did not match')
        count += len(hashes)
    return count


def transport_get(session,url,**kwargs):
    def pull():
        response=session.get(url,**kwargs)
        if response.status_code in (408,429,500,502,503,504):
            response.raise_for_status()
        return response
    return retry_transport(pull)


class AlreadyRunning(RuntimeError):
    pass


class PipelineRun:
    def __init__(self,client,stage):
        self.client,self.stage = client,stage
        self.rows,self.details,self.status = 0,{},'completed'
    def __enter__(self):
        self.id = self.client.rpc('cbb_begin_pipeline_run',{'p_stage':self.stage}).execute().data
        if not self.id:
            raise AlreadyRunning('A CBB '+self.stage+' execution lease is already active')
        return self
    def __exit__(self,kind,exc,tb):
        error = safe_error(exc) if exc else None
        result = self.client.rpc('cbb_finish_pipeline_run',{'p_id':self.id,'p_status':'failed' if exc else self.status,'p_rows':self.rows,'p_details':self.details,'p_error':error}).execute()
        print(json.dumps({'stage':self.stage,'status':'failed' if exc else self.status,'rows_verified':self.rows,'error':error,**self.details}),flush=True)
        if not result.data and not exc:
            raise RuntimeError('CBB execution lease expired before verified completion')
        return False
