"""Stage selection independent of Streamlit; transitions never invoke a model."""


def resolve_stage(requested: str, has_plan: bool, has_completed_run: bool) -> str:
    if requested not in {'describe', 'plan', 'result'}:
        return 'describe'
    if requested in {'plan', 'result'} and not has_plan:
        return 'describe'
    if requested == 'result' and not has_completed_run:
        return 'plan'
    return requested
