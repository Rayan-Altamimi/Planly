from typing import Annotated
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, model_validator, Field
from sqlalchemy.orm import Session
from starlette import status
from models import Task, Category, PriorityEnum, RecurrenceEnum
from routers.auth import get_current_user, db_dependency

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
)

user_dependency = Annotated[dict, Depends(get_current_user)]


class CreateTask(BaseModel):
    title: str = Field(max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    due_date: date | None = None
    priority: PriorityEnum | None = None
    is_recurring: bool = False
    recurrence_pattern: RecurrenceEnum | None = None
    recurrence_end_date: date | None = None
    category_id: int | None = None

    @model_validator(mode="after")
    def check_recurrence_pattern(self):
        if self.is_recurring and self.recurrence_pattern is None:
            raise ValueError("recurrence_pattern is required when is_recurring is True.")
        return self


class TaskResponse(BaseModel):
    id: int
    title: str
    description: str | None
    due_date: date | None
    is_completed: bool
    priority: PriorityEnum | None
    is_recurring: bool
    recurrence_pattern: RecurrenceEnum | None
    recurrence_end_date: date | None
    category_id: int | None
    owner_id: int
    parent_task_id: int | None

    class Config:
        from_attributes = True


def verify_category_ownership(category_id: int | None, user_id: int, db: Session):
    if category_id is None:
        return
    category = db.query(Category).filter(
        Category.id == category_id, Category.owner_id == user_id
    ).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                             detail="Invalid category_id: category not found or not owned by you.")


def next_due_date(current: date, pattern: RecurrenceEnum) -> date:
    if pattern == RecurrenceEnum.daily:
        return current + timedelta(days=1)
    if pattern == RecurrenceEnum.weekly:
        return current + timedelta(weeks=1)
    if pattern == RecurrenceEnum.monthly:
        month = current.month + 1
        year = current.year + (1 if month > 12 else 0)
        month = 1 if month > 12 else month
        day = min(current.day, 28)
        return date(year, month, day)
    if pattern == RecurrenceEnum.yearly:
        return date(current.year + 1, current.month, current.day)
    return current


def generate_recurring_instances(user_id: int, db: Session):
    templates = db.query(Task).filter(
        Task.owner_id == user_id,
        Task.is_recurring == True,
        Task.parent_task_id.is_(None),
        Task.due_date.isnot(None)
    ).all()

    today = date.today()

    for template in templates:
        last_instance = db.query(Task).filter(
            Task.parent_task_id == template.id
        ).order_by(Task.due_date.desc()).first()

        last_date = last_instance.due_date if last_instance else template.due_date
        next_date = next_due_date(last_date, template.recurrence_pattern)

        while next_date <= today:
            if template.recurrence_end_date and next_date > template.recurrence_end_date:
                break
            new_instance = Task(
                title=template.title,
                description=template.description,
                due_date=next_date,
                priority=template.priority,
                is_recurring=False,
                category_id=template.category_id,
                owner_id=user_id,
                parent_task_id=template.id
            )
            db.add(new_instance)
            next_date = next_due_date(next_date, template.recurrence_pattern)

        db.commit()


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=TaskResponse)
async def create_task(user: user_dependency, db: db_dependency, task_request: CreateTask):
    verify_category_ownership(task_request.category_id, user['id'], db)

    new_task = Task(
        title=task_request.title,
        description=task_request.description,
        due_date=task_request.due_date,
        priority=task_request.priority,
        is_recurring=task_request.is_recurring,
        recurrence_pattern=task_request.recurrence_pattern,
        recurrence_end_date=task_request.recurrence_end_date,
        category_id=task_request.category_id,
        owner_id=user['id']
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return new_task


@router.get("/", response_model=list[TaskResponse], status_code=status.HTTP_200_OK)
async def get_tasks(
    user: user_dependency,
    db: db_dependency,
    completed: bool | None = Query(default=None),
    due_before: date | None = Query(default=None),
    due_after: date | None = Query(default=None),
    category_id: int | None = Query(default=None),
):
    generate_recurring_instances(user['id'], db)

    query = db.query(Task).filter(Task.owner_id == user['id'])

    if completed is not None:
        query = query.filter(Task.is_completed == completed)
    if due_before is not None:
        query = query.filter(Task.due_date <= due_before)
    if due_after is not None:
        query = query.filter(Task.due_date >= due_after)
    if category_id is not None:
        query = query.filter(Task.category_id == category_id)

    return query.all()


@router.get("/{task_id}", response_model=TaskResponse, status_code=status.HTTP_200_OK)
async def get_task(user: user_dependency, db: db_dependency,
                    task_id: Annotated[int, Path(gt=0)]):
    task = db.query(Task).filter(Task.id == task_id)\
        .filter(Task.owner_id == user['id']).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.put("/{task_id}", response_model=TaskResponse, status_code=status.HTTP_200_OK)
async def update_task(user: user_dependency, db: db_dependency,
                       task_request: CreateTask,
                       task_id: Annotated[int, Path(gt=0)]):
    task = db.query(Task).filter(Task.id == task_id)\
        .filter(Task.owner_id == user['id']).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    verify_category_ownership(task_request.category_id, user['id'], db)

    task.title = task_request.title
    task.description = task_request.description
    task.due_date = task_request.due_date
    task.priority = task_request.priority
    task.is_recurring = task_request.is_recurring
    task.recurrence_pattern = task_request.recurrence_pattern
    task.recurrence_end_date = task_request.recurrence_end_date
    task.category_id = task_request.category_id

    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(user: user_dependency, db: db_dependency,
                       task_id: Annotated[int, Path(gt=0)]):
    task = db.query(Task).filter(Task.id == task_id)\
        .filter(Task.owner_id == user['id']).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    db.delete(task)
    db.commit()


@router.patch("/{task_id}/complete", response_model=TaskResponse, status_code=status.HTTP_200_OK)
async def toggle_task_complete(user: user_dependency, db: db_dependency,
                                task_id: Annotated[int, Path(gt=0)]):
    task = db.query(Task).filter(Task.id == task_id)\
        .filter(Task.owner_id == user['id']).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    task.is_completed = not task.is_completed
    db.commit()
    db.refresh(task)
    return task