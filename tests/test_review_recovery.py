import pytest
from pydantic import ValidationError
from prompt_compiler.semantic_review import SemanticReview
from test_automatic import Stub, PLAN, APPROVED, FILES
from prompt_compiler.compiler import compile_workflow
from prompt_compiler.files import inventory


def test_missing_cosmetic_summary_does_not_erase_a_valid_review_verdict():
    assert SemanticReview.model_validate({'approved': True, 'issues': []}).approved
    review = SemanticReview.model_validate({'approved': False, 'issues': ['Wrong sort order']})
    assert not review.approved and review.issues == ['Wrong sort order']


@pytest.mark.parametrize('payload', [
    {'approved': True, 'issues': ['Mismatch']},
    {'approved': False, 'issues': []},
    {'issues': []},
    {'approved': True},
])
def test_missing_summary_never_relaxes_the_actual_review_contract(payload):
    with pytest.raises(ValidationError):
        SemanticReview.model_validate(payload)


def test_correction_receives_the_actual_rejected_proposal_and_issues():
    provider = Stub([PLAN, {'approved': False, 'issues': ['Use the requested threshold']}, PLAN, APPROVED])
    result = compile_workflow('Filter Score above 3 and export CSV', inventory(FILES), provider, 'automatic', 1)
    assert result.workflow is not None and result.api_calls == 4
    feedback = provider.calls[2][0][-1]['content']
    assert 'Use the requested threshold' in feedback and 'Latest proposal' in feedback
    assert '"comparison": "gt"' in feedback
