import pytest
from prompt_compiler.journey import resolve_stage
from prompt_compiler.executor import extract_invoice


@pytest.mark.parametrize('requested,plan,run,expected', [
    ('describe', False, False, 'describe'), ('plan', False, False, 'describe'),
    ('result', False, True, 'describe'), ('result', True, False, 'plan'),
    ('plan', True, True, 'plan'), ('result', True, True, 'result'),
    ('describe', True, True, 'describe'), ('unknown', True, True, 'describe'),
])
def test_guided_stage_guards_and_back_navigation(requested, plan, run, expected):
    assert resolve_stage(requested, plan, run) == expected


def test_amount_due_extraction_ignores_subtotal_and_tax():
    row = {'source_file': 'new.pdf', 'text': 'Supplier: Cedar & Coast Office Systems\nCurrency: INR\nSubtotal\n61,800.00\nGST (18%)\n11,124.00\nAmount due: INR 72,924.00\n'}
    extracted = extract_invoice(row)
    assert extracted['total'] == 72924 and extracted['vendor'] == 'Cedar & Coast Office Systems'
    assert extracted['currency'] == 'INR' and extracted['extraction_status'] == 'ok'


def test_conflicting_total_and_amount_due_are_not_silently_resolved():
    row = {'source_file': 'partial.pdf', 'text': 'Vendor: Test\nCurrency: INR\nTotal: 100000\nAmount due: 50000\n'}
    extracted = extract_invoice(row)
    assert extracted['total'] is None and extracted['extraction_status'] == 'needs_review'
