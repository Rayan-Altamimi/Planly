from typing import Annotated
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, model_validator, Field
from sqlalchemy.orm import Session
from starlette import status
from models import Reminder, Task, Event
from routers.auth import get_current_user, db_dependency

router = APIRouter(
    prefix="/reminders",
    tags=["reminders"],
)

user_dependency = Annotated[dict, Depends(get_current_user)]


class CreateReminder(BaseModel):
    remind_at: datetime
    message: str | None = Field(default=None, max_length=500)
    task_id: int | None = None
    event_id: int | None = None

    @model_validator(mode="after")
    def check_exactly_one_link(self):
        if self.task_id is None and self.event_id is None:
            raise ValueError("A reminder must be linked to either a task_id or an event_id.")
        if self.task_id is not None and self.event_id is not None:
            raise ValueError("A reminder cannot be linked to both a task and an event.")
        return self


class UpdateReminder(BaseModel):
    remind_at: datetime
    message: str | None = Field(default=None, max_length=500)


class ReminderResponse(BaseModel):
    id: int
    remind_at: datetime
    message: str | None
    is_dismissed: bool
    task_id: int | None
    event_id: int | None
    owner_id: int

    class Config:
        from_attributes = True


def verify_link_ownership(task_id: int | None, event_id: int | None, user_id: int, db: Session):
    if task_id is not None:
        task = db.query(Task).filter(Task.id == task_id, Task.owner_id == user_id).first()
        if not task:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                 detail="Invalid task_id: task not found or not owned by you.")
    if event_id is not None:
        event = db.query(Event).filter(Event.id == event_id, Event.owner_id == user_id).first()
        if not event:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                 detail="Invalid event_id: event not found or not owned by you.")


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=ReminderResponse)
async def create_reminder(user: user_dependency, db: db_dependency, reminder_request: CreateReminder):
    verify_link_ownership(reminder_request.task_id, reminder_request.event_id, user['id'], db)

    new_reminder = Reminder(
        remind_at=reminder_request.remind_at,
        message=reminder_request.message,
        task_id=reminder_request.task_id,
        event_id=reminder_request.event_id,
        owner_id=user['id']
    )
    db.add(new_reminder)
    db.commit()
    db.refresh(new_reminder)
    return new_reminder


@router.get("/", response_model=list[ReminderResponse], status_code=status.HTTP_200_OK)
async def get_reminders(
    user: user_dependency,
    db: db_dependency,
    active_only: bool = Query(default=False),
):
    query = db.query(Reminder).filter(Reminder.owner_id == user['id'])

    if active_only:
        query = query.filter(
            Reminder.is_dismissed == False,
            Reminder.remind_at <= datetime.now()
        )

    return query.order_by(Reminder.remind_at).all()


@router.get("/{reminder_id}", response_model=ReminderResponse, status_code=status.HTTP_200_OK)
async def get_reminder(user: user_dependency, db: db_dependency,
                        reminder_id: Annotated[int, Path(gt=0)]):
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id)\
        .filter(Reminder.owner_id == user['id']).first()
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    return reminder


@router.put("/{reminder_id}", response_model=ReminderResponse, status_code=status.HTTP_200_OK)
async def update_reminder(user: user_dependency, db: db_dependency,
                           reminder_request: UpdateReminder,
                           reminder_id: Annotated[int, Path(gt=0)]):
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id)\
        .filter(Reminder.owner_id == user['id']).first()
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")

    reminder.remind_at = reminder_request.remind_at
    reminder.message = reminder_request.message

    db.commit()
    db.refresh(reminder)
    return reminder


@router.patch("/{reminder_id}/dismiss", response_model=ReminderResponse, status_code=status.HTTP_200_OK)
async def dismiss_reminder(user: user_dependency, db: db_dependency,
                            reminder_id: Annotated[int, Path(gt=0)]):
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id)\
        .filter(Reminder.owner_id == user['id']).first()
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    reminder.is_dismissed = True
    db.commit()
    db.refresh(reminder)
    return reminder


@router.delete("/{reminder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reminder(user: user_dependency, db: db_dependency,
                           reminder_id: Annotated[int, Path(gt=0)]):
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id)\
        .filter(Reminder.owner_id == user['id']).first()
    if not reminder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    db.delete(reminder)
    db.commit()