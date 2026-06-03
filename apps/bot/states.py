from aiogram.fsm.state import State, StatesGroup


class QualificationFSM(StatesGroup):
    waiting_for_start_confirm = State()
    waiting_for_budget = State()
    waiting_for_service_type = State()
    waiting_for_business_stage = State()
    waiting_for_urgency = State()
    waiting_for_agency_experience = State()
    generating_verdict = State()
