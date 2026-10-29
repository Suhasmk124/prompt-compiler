from pathlib import Path
from prompt_compiler.files import read_file
from prompt_compiler.executor import extract_invoice


def test_real_pdf_fixture_extracts_tax_inclusive_amount_due():
    source = Path(__file__).resolve().parents[1] / 'examples/pdf/cedar_coast_invoice.pdf'
    frame = read_file(source.name, source.read_bytes())
    row = extract_invoice(frame.iloc[0])
    assert row == {'source_file': source.name, 'vendor': 'Cedar & Coast Office Systems',
                   'total': 72924.0, 'currency': 'INR', 'extraction_status': 'ok'}
