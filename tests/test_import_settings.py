from io import BytesIO
import pandas as pd
import pytest
from openpyxl import Workbook
from prompt_compiler.files import inventory, read_file
from prompt_compiler.executor import execute
from prompt_compiler.schema import Workflow


FILES={'data.csv':b'ID,Amount,Active,Closed\n001,20,yes,31/10/2026\n002,NA,no,\n'}
OPTIONS={'data.csv':{'column_types':{'ID':'text','Amount':'number','Active':'boolean','Closed':'date_dmy'},'missing_values':['NA']}}


def test_import_rules_are_shared_by_preview_metadata_and_execution():
    original=FILES['data.csv']
    frame=read_file('data.csv',original,OPTIONS['data.csv'])
    assert frame['ID'].tolist()==['001','002']
    assert frame['Active'].tolist()==[True,False]
    assert frame['Amount'].iloc[0]==20 and pd.isna(frame['Amount'].iloc[1])
    assert frame['Closed'].iloc[0]==pd.Timestamp('2026-10-31')
    meta=inventory(FILES,OPTIONS)['data.csv']
    assert meta['column_types']=={'ID':'text','Amount':'number','Active':'boolean','Closed':'datetime'}
    plan=Workflow.model_validate({'version':'1.0','title':'Active records','steps':[
        {'id':'read','label':'Read','operation':'read','files':['data.csv']},
        {'id':'filter','label':'Active','operation':'filter','source':'read','column':'Active','comparison':'eq','value':True},
        {'id':'report','label':'Report','operation':'export','source':'filter','filename':'report.xlsx'}]})
    run=execute(plan,FILES,OPTIONS)
    assert run.error is None and run.tables['report']['ID'].tolist()==['001']
    assert FILES['data.csv']==original


@pytest.mark.parametrize('options',[
    {'column_types':{'Unknown':'text'}}, {'column_types':{'Amount':'currency'}},
    {'column_types':{'Amount':'number'}}, {'column_types':{'Active':'date_iso'}},
    {'missing_values':[1]}, {'unknown_setting':True},
])
def test_invalid_or_incompatible_import_rules_fail_explicitly(options):
    with pytest.raises(ValueError):read_file('data.csv',FILES['data.csv'],options)


def test_literal_na_and_zeros_are_not_silently_missing():
    frame=read_file('data.csv',b'code,value\nNULL,0\nN/A,1\nNA,2\n',{'column_types':{'code':'text'}})
    assert frame['code'].tolist()==['NULL','N/A','NA']
    assert frame['value'].tolist()==[0,1,2]


def test_excel_typed_dates_and_text_identifier_are_preserved():
    book=Workbook();book.active.append(['ID','Date']);book.active.append(['0007',pd.Timestamp('2026-10-31').to_pydatetime()])
    buffer=BytesIO();book.save(buffer)
    frame=read_file('source.xlsx',buffer.getvalue(),{'column_types':{'ID':'text','Date':'date_iso'}})
    assert frame['ID'].iloc[0]=='0007' and frame['Date'].iloc[0]==pd.Timestamp('2026-10-31')


def test_import_settings_cannot_apply_to_unuploaded_files_or_documents():
    with pytest.raises(ValueError,match='not uploaded'):inventory(FILES,{'wrong.csv':{}})
    with pytest.raises(ValueError,match='CSV/XLSX'):read_file('note.txt',b'hello',{'column_types':{'text':'text'}})
