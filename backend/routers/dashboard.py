from typing import Annotated
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import case
from starlette import status
from models import Task, Event, Reminder, PriorityEnum
from routers.auth import get_current_user, db_dependency
from routers.tasks import TaskResponse, generate_recurring_instances
from routers.events import EventResponse
from routers.reminders import ReminderResponse

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
)

user_dependency = Annotated[dict, Depends(get_current_user)]


class DashboardResponse(BaseModel):
    tasks_today: list[TaskResponse]
    tasks_completed_today: int
    tasks_total_today: int
    overdue_tasks: list[TaskResponse]
    no_due_date_tasks: list[TaskResponse]
    upcoming_events: list[EventResponse]
    active_reminders: list[ReminderResponse]

priority_order = case(
    (Task.priority == PriorityEnum.high, 0),
    (Task.priority == PriorityEnum.medium, 1),
    (Task.priority == PriorityEnum.low, 2),
    else_=3
)


@router.get("/", response_model=DashboardResponse, status_code=status.HTTP_200_OK)
async def get_dashboard(user: user_dependency, db: db_dependency):
    generate_recurring_instances(user['id'], db)

    today = date.today()
    week_from_now = today + timedelta(days=7)
    now = datetime.now()

    tasks_today = db.query(Task).filter(
        Task.owner_id == user['id'],
        Task.due_date == today
    ).order_by(priority_order).all()

    tasks_total_today = len(tasks_today)
    tasks_completed_today = sum(1 for t in tasks_today if t.is_completed)

    overdue_tasks = db.query(Task).filter(
        Task.owner_id == user['id'],
        Task.due_date < today,
        Task.is_completed == False
    ).order_by(priority_order).all()

    no_due_date_tasks = db.query(Task).filter(
        Task.owner_id == user['id'],
        Task.due_date.is_(None),
        Task.is_completed == False
    ).order_by(priority_order).all()

    upcoming_events = db.query(Event).filter(
        Event.owner_id == user['id'],
        Event.event_date >= today,
        Event.event_date <= week_from_now
    ).order_by(Event.event_date, Event.event_time).all()

    active_reminders = db.query(Reminder).filter(
        Reminder.owner_id == user['id'],
        Reminder.is_dismissed == False,
        Reminder.remind_at <= now
    ).order_by(Reminder.remind_at).all()

    return DashboardResponse(
        tasks_today=tasks_today,
        tasks_completed_today=tasks_completed_today,
        tasks_total_today=tasks_total_today,
        overdue_tasks=overdue_tasks,
        no_due_date_tasks=no_due_date_tasks,
        upcoming_events=upcoming_events,
        active_reminders=active_reminders
    )