"""Finite-state definitions for user and admin conversations."""
from aiogram.fsm.state import State, StatesGroup


class SupportStates(StatesGroup):
    waiting_message = State()


class AdminStates(StatesGroup):
    waiting_prompt_task = State()
    waiting_prompt_title = State()
    waiting_prompt_search = State()
    waiting_prompt_rename = State()
    waiting_post_topic = State()
    waiting_post_edit = State()
    waiting_schedule_time = State()
    waiting_ticket_reply = State()
    waiting_broadcast_text = State()
    waiting_user_search = State()
    waiting_ai_research = State()
    waiting_ai_limit = State()
    waiting_note = State()
