from enum import StrEnum
from typing import Literal

from pydantic import BaseModel


class IntentType(StrEnum):
    question = "question"
    answer = "answer"


class IntentResult(BaseModel):
    intent: IntentType


class RagChunk(BaseModel):
    content: str
    score: float
    source: str


class ServiceType(StrEnum):
    smm = "smm"
    context = "context"
    targeting = "targeting"
    seo = "seo"
    complex = "complex"
    unclear = "unclear"


class BusinessStage(StrEnum):
    startup = "startup"
    working = "working"
    enterprise = "enterprise"
    unclear = "unclear"


class Urgency(StrEnum):
    immediate = "immediate"
    month = "month"
    future = "future"
    unclear = "unclear"


class AgencyExperience(StrEnum):
    positive = "positive"
    negative = "negative"
    none = "none"
    unclear = "unclear"


class NextStep(StrEnum):
    book_call = "book_call"
    polite_decline = "polite_decline"
    needs_clarification = "needs_clarification"


class QualifierVerdict(BaseModel):
    qualified: bool
    budget_rub_monthly: int | None
    service_type: ServiceType
    business_stage: BusinessStage
    urgency: Urgency
    agency_experience: AgencyExperience
    reasoning: str
    next_step: NextStep


class DialogueMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
