from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
from io import BytesIO
import json
from threading import Event
from urllib.error import HTTPError
import pytest

from prompt_compiler.jobs import BackgroundJob
from prompt_compiler.provider import Provider, RateLimitedError, RequestCancelled, retry_after_seconds
from prompt_compiler.compiler import compile_workflow
from prompt_compiler.files import inventory


def test_background_job_reports_progress_and_returns_without_ui_state():
    def worker(cancel,progress):
        progress({'stage':'generation','message':'Working','api_calls':1})
        return 'done'
    job=BackgroundJob(worker,'fingerprint').start()
    assert job.done.wait(2)
    assert job.result=='done' and job.snapshot()['api_calls']==1


def test_job_cancellation_is_cooperative_and_does_not_start_more_work():
    entered=Event()
    def worker(cancel,progress):
        entered.set()
        cancel.wait(2)
        return 'cancelled' if cancel.is_set() else 'unexpected'
    job=BackgroundJob(worker,'abc').start()
    assert entered.wait(1)
    job.cancel()
    assert job.done.wait(1) and job.result=='cancelled'
    assert job.snapshot()['cancelling']


def test_result_completed_before_cancel_is_still_discarded():
    job=BackgroundJob(lambda event,progress:'result','abc').start()
    assert job.done.wait(1)
    assert job.accepts_result('abc') and not job.accepts_result('changed')
    job.cancel()
    assert not job.accepts_result('abc')


@pytest.mark.parametrize('value,expected',[('2',2),('0',0),('-1',0),('invalid',None),('NaN',None),('inf',None)])
def test_retry_after_numbers_are_bounded_and_parsed(value,expected):
    assert retry_after_seconds(value)==expected


def test_retry_after_http_date_is_understood():
    value=format_datetime(datetime.now(timezone.utc)+timedelta(seconds=30),usegmt=True)
    assert 28<=retry_after_seconds(value)<=31


def test_rate_limit_retry_respects_header_and_counts_physical_calls(monkeypatch):
    requests=[];progress=[]
    class Opener:
        def open(self,request,**kwargs):
            requests.append(request)
            if len(requests)==1:
                raise HTTPError('https://example.invalid',429,'Busy',{'Retry-After':'0'},BytesIO(b'{"error":{}}'))
            return BytesIO(b'{"choices":[{"message":{"content":"{}"}}]}')
    monkeypatch.setattr('urllib.request.build_opener',lambda *args:Opener())
    provider=Provider('https://example.invalid/v1','test',max_rate_retries=1,on_progress=progress.append)
    assert provider.complete([]).text=='{}' and provider.request_count==2
    assert progress[0]['stage']=='retry_wait' and progress[0]['retry_after']==0


def test_long_rate_wait_is_not_silently_ignored(monkeypatch):
    class Opener:
        def open(self,*args,**kwargs):
            raise HTTPError('https://example.invalid',429,'Busy',{'Retry-After':'999'},BytesIO(b'{"error":{}}'))
    monkeypatch.setattr('urllib.request.build_opener',lambda *args:Opener())
    provider=Provider('https://example.invalid/v1','test',max_rate_retries=2,max_retry_wait=30)
    with pytest.raises(RateLimitedError):provider.complete([])
    assert provider.request_count==1


def test_cancel_during_retry_stops_without_another_request(monkeypatch):
    event=Event()
    class Opener:
        def open(self,*args,**kwargs):
            raise HTTPError('https://example.invalid',429,'Busy',{'Retry-After':'30'},BytesIO(b'{"error":{}}'))
    monkeypatch.setattr('urllib.request.build_opener',lambda *args:Opener())
    provider=Provider('https://example.invalid/v1','test',max_rate_retries=1,cancel_event=event,on_progress=lambda _:event.set())
    with pytest.raises(RequestCancelled):provider.complete([])
    assert provider.request_count==1


def test_compiler_counts_rate_retry_attempts_and_retains_success(monkeypatch):
    calls=[]
    plan={'title':'Copy input','steps':[
        {'id':'read','label':'Read','operation':'read','files':['data.csv']},
        {'id':'report','label':'Export','operation':'export','source':'read','filename':'report.csv'}],'clarification':None}
    class Opener:
        def open(self,request,**kwargs):
            calls.append(request)
            if len(calls)==1:
                raise HTTPError('https://example.invalid',429,'Busy',{'Retry-After':'0'},BytesIO(b'{"error":{}}'))
            return BytesIO(json.dumps({'choices':[{'message':{'content':json.dumps(plan)}}]}).encode())
    monkeypatch.setattr('urllib.request.build_opener',lambda *args:Opener())
    provider=Provider('https://example.invalid/v1','test',max_rate_retries=1)
    result=compile_workflow('Copy all rows to CSV',inventory({'data.csv':b'ID\nA\n'}),provider,'one_shot',0,verify_semantics=False)
    assert result.workflow is not None and result.api_calls==2


def test_cancelled_compilation_never_calls_provider():
    event=Event();event.set()
    provider=Provider('https://example.invalid/v1','test')
    result=compile_workflow('Copy input',inventory({'data.csv':b'ID\nA\n'}),provider,'one_shot',0,cancel_event=event)
    assert result.error_kind=='cancelled' and result.api_calls==0 and provider.request_count==0
