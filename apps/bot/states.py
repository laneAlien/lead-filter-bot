from aiogram.fsm.state import State, StatesGroup


class QualificationFSM(StatesGroup):
    # Phase 2: will be expanded with per-question states
    waiting_for_start_confirm = State()
    in_dialogue = State()
