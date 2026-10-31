import pytest
from prompt_compiler.schema import Workflow
from prompt_compiler.task_coverage import validate_requested_actions


def plan(select=False):
    steps=[{'id':'read','label':'Read','operation':'read','files':['data.csv']},
        {'id':'part','label':'Subexpression','operation':'flag_rows','source':'read','match':'any',
         'conditions':[{'column':'Area','comparison':'eq','value':'east'},{'column':'Points','comparison':'gte','value':8}], 'output_column':'internal_any'},
        {'id':'final','label':'Final result','operation':'flag_rows','source':'part','match':'all',
         'conditions':[{'column':'internal_any','comparison':'eq','value':True},{'column':'State','comparison':'eq','value':'ready'}], 'output_column':'Match'}]
    source='final'
    if select:
        steps.append({'id':'clean','label':'Final columns','operation':'select','source':'final','columns':['Area','Points','State','Match']})
        source='clean'
    steps.append({'id':'report','label':'Report','operation':'export','source':source,'filename':'report.csv'})
    return Workflow.model_validate({'version':'1.0','title':'Nested expression','steps':steps})


def test_internal_predicate_column_cannot_be_approved_as_an_extra_export():
    with pytest.raises(ValueError,match='Internal helper flags'):
        validate_requested_actions(plan(),'Flag the nested condition as Match. Preserve original columns and add only Match.')


def test_final_selection_removes_the_internal_column():
    validate_requested_actions(plan(True),'Flag the nested condition as Match, preserving original columns and adding only Match.')


def test_explicitly_requested_helper_columns_remain_allowed():
    validate_requested_actions(plan(),'Flag the nested condition as Match. Show intermediate flags.')


def test_negative_helper_request_does_not_disable_the_guard():
    with pytest.raises(ValueError,match='Internal helper flags'):
        validate_requested_actions(plan(),'Flag the nested condition as Match. Do not include helper flags.')
