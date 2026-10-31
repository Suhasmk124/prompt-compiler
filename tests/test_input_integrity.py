from io import BytesIO
import pytest
from openpyxl import Workbook
from prompt_compiler.files import read_file
from prompt_compiler.schema import Workflow

@pytest.mark.parametrize('headers,message', [(['Name','Name'],'unique'), (['Name',''],'non-empty'), (['Name','   '],'non-empty')])
@pytest.mark.parametrize('extension',['csv','xlsx'])
def test_original_headers_are_checked_before_parser_renaming(headers,message,extension):
    if extension=='csv':
        content=(','.join(headers)+'\nA,B\n').encode()
    else:
        book=Workbook(); book.active.append(headers); book.active.append(['A','B'])
        buf=BytesIO();book.save(buf);content=buf.getvalue()
    with pytest.raises(ValueError,match=message):read_file('input.'+extension,content)


def test_literal_quoted_headers_remain_intact():
    frame=read_file('input.csv',b'"Last, First",NA\n"Smith, Ada",4\n')
    assert list(frame)==['Last, First','NA']
    assert frame.iloc[0,0]=='Smith, Ada'


def test_exports_cannot_collide_on_case_insensitive_filesystems():
    with pytest.raises(ValueError,match='ignoring letter case'):
        Workflow.model_validate({'version':'1.0','title':'Collision','steps':[
            {'operation':'read','id':'input','label':'Input','files':['data.csv']},
            {'operation':'export','id':'one','label':'One','source':'input','filename':'Report.csv'},
            {'operation':'export','id':'two','label':'Two','source':'input','filename':'report.csv'}]})

@pytest.mark.parametrize('extension',['csv','xlsx'])
def test_literal_na_markers_survive_but_empty_cells_are_missing(extension):
    import pandas as pd
    rows=[['Region','Note'],['NA','N/A'],['EU','NULL'],['APAC','']]
    if extension=='csv':
        content=('\n'.join(','.join(row) for row in rows)+'\n').encode()
    else:
        book=Workbook()
        for row in rows:book.active.append(row)
        buf=BytesIO();book.save(buf);content=buf.getvalue()
    frame=read_file('input.'+extension,content)
    assert frame['Region'].tolist()==['NA','EU','APAC']
    assert frame['Note'].iloc[:2].tolist()==['N/A','NULL']
    assert pd.isna(frame['Note'].iloc[2])
