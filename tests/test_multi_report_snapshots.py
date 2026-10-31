from prompt_compiler.schema import Workflow
from prompt_compiler.executor import execute
from prompt_compiler.workspace_tools import retain_snapshot


def test_each_export_gets_its_own_named_snapshot_and_table():
    workflow=Workflow.model_validate({'version':'1.0','title':'Two reports','steps':[
        {'id':'read','label':'Read','operation':'read','files':['data.csv']},
        {'id':'all_rows','label':'All','operation':'export','source':'read','filename':'all.csv'},
        {'id':'filter','label':'Filter','operation':'filter','source':'read','column':'Value','comparison':'gt','value':1},
        {'id':'selected','label':'Selected','operation':'export','source':'filter','filename':'selected.csv'}]})
    run=execute(workflow,{'data.csv':b'ID,Value\nA,1\nB,2\n'})
    previous,all_snapshot=retain_snapshot([],workflow,run,'now','hash',export_id='all_rows')
    kept,selected_snapshot=retain_snapshot(previous,workflow,run,'now','hash',export_id='selected')
    assert all_snapshot.report_name=='all.csv' and len(all_snapshot.frame)==2
    assert selected_snapshot.report_name=='selected.csv' and len(selected_snapshot.frame)==1
    assert len(kept)==2
    run.tables['all_rows'].loc[0,'ID']='changed'
    assert all_snapshot.frame.loc[0,'ID']=='A'
