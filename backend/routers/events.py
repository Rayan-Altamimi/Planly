from typing import Annotated
from datetime import date, time
from enum import Enum
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette import status
from models import Event, Category
from routers.auth import get_current_user, db_dependency
from routers.tasks import verify_category_ownership

router = APIRouter(
    prefix="/events",
    tags=["events"],
)

user_dependency = Annotated[dict, Depends(get_current_user)]


class EventStatus(str, Enum):
    upcoming = "upcoming"
    past = "past"
    all = "all"


class CreateEvent(BaseModel):
    title: str
    description: str | None = None
    event_date: date
    event_time: time | None = None
    location: str | None = None
    category_id: int | None = None


class EventResponse(BaseModel):
    id: int
    title: str
    description: str | None
    event_date: date
    event_time: time | None
    location: str | None
    category_id: int | None
    owner_id: int

    class Config:
        from_attributes = True


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=EventResponse)
async def create_event(user: user_dependency, db: db_dependency, event_request: CreateEvent):
    verify_category_ownership(event_request.category_id, user['id'], db)

    new_event = Event(
        title=event_request.title,
        description=event_request.description,
        event_date=event_request.event_date,
        event_time=event_request.event_time,
        location=event_request.location,
        category_id=event_request.category_id,
        owner_id=user['id']
    )
    db.add(new_event)
    db.commit()
    db.refresh(new_event)
    return new_event


@router.get("/", response_model=list[EventResponse], status_code=status.HTTP_200_OK)
async def get_events(
    user: user_dependency,
    db: db_dependency,
    event_status: EventStatus = Query(default=EventStatus.all),
    category_id: int | None = Query(default=None),
):
    query = db.query(Event).filter(Event.owner_id == user['id'])

    today = date.today()
    if event_status == EventStatus.upcoming:
        query = query.filter(Event.event_date >= today)
    elif event_status == EventStatus.past:
        query = query.filter(Event.event_date < today)

    if category_id is not None:
        query = query.filter(Event.category_id == category_id)

    return query.order_by(Event.event_date, Event.event_time).all()


@router.get("/{event_id}", response_model=EventResponse, status_code=status.HTTP_200_OK)
async def get_event(user: user_dependency, db: db_dependency,
                     event_id: Annotated[int, Path(gt=0)]):
    event = db.query(Event).filter(Event.id == event_id)\
        .filter(Event.owner_id == user['id']).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


@router.put("/{event_id}", response_model=EventResponse, status_code=status.HTTP_200_OK)
async def update_event(user: user_dependency, db: db_dependency,
                        event_request: CreateEvent,
                        event_id: Annotated[int, Path(gt=0)]):
    event = db.query(Event).filter(Event.id == event_id)\
        .filter(Event.owner_id == user['id']).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    verify_category_ownership(event_request.category_id, user['id'], db)

    event.title = event_request.title
    event.description = event_request.description
    event.event_date = event_request.event_date
    event.event_time = event_request.event_time
    event.location = event_request.location
    event.category_id = event_request.category_id

    db.commit()
    db.refresh(event)
    return event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(user: user_dependency, db: db_dependency,
                        event_id: Annotated[int, Path(gt=0)]):
    event = db.query(Event).filter(Event.id == event_id)\
        .filter(Event.owner_id == user['id']).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    db.delete(event)
    db.commit()