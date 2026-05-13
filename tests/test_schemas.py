import pytest
from pydantic import ValidationError

from core.schemas import QualifierVerdict

VALID_VERDICT = {
    "qualified": True,
    "budget_rub_monthly": 50000,
    "service_type": "smm",
    "business_stage": "working",
    "urgency": "immediate",
    "agency_experience": "none",
    "reasoning": "Все критерии выполнены.",
    "next_step": "book_call",
}


def test_valid_verdict_parses() -> None:
    verdict = QualifierVerdict.model_validate(VALID_VERDICT)

    assert verdict.qualified is True
    assert verdict.budget_rub_monthly == 50000
    assert verdict.service_type.value == "smm"
    assert verdict.next_step.value == "book_call"


def test_null_budget_is_valid() -> None:
    data = {**VALID_VERDICT, "qualified": False, "budget_rub_monthly": None}
    verdict = QualifierVerdict.model_validate(data)

    assert verdict.budget_rub_monthly is None


def test_invalid_service_type_raises() -> None:
    data = {**VALID_VERDICT, "service_type": "banana"}

    with pytest.raises(ValidationError):
        QualifierVerdict.model_validate(data)


def test_invalid_next_step_raises() -> None:
    data = {**VALID_VERDICT, "next_step": "just_ignore"}

    with pytest.raises(ValidationError):
        QualifierVerdict.model_validate(data)


def test_missing_required_field_raises() -> None:
    data = {k: v for k, v in VALID_VERDICT.items() if k != "reasoning"}

    with pytest.raises(ValidationError):
        QualifierVerdict.model_validate(data)
