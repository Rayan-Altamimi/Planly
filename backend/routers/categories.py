from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette import status
from models import Category
from routers.auth import get_current_user, db_dependency

router = APIRouter(
    prefix="/categories",
    tags=["categories"],
)

user_dependency = Annotated[dict, Depends(get_current_user)]


class CreateCategory(BaseModel):
    name: str = Field(max_length=100)
    color: str | None = Field(default=None, max_length=20)

class CategoryResponse(BaseModel):
    id: int
    name: str
    color: str | None
    owner_id: int

    class Config:
        from_attributes = True


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=CategoryResponse)
async def create_category(user: user_dependency, db: db_dependency, create_category_request: CreateCategory):
    existing_category = db.query(Category).filter(
        Category.name == create_category_request.name,
        Category.owner_id == user['id']
    ).first()
    if existing_category:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                             detail="You already have a category with this name.")

    new_category = Category(
        name=create_category_request.name,
        color=create_category_request.color,
        owner_id=user['id']
    )
    db.add(new_category)
    db.commit()
    db.refresh(new_category)
    return new_category


@router.get("/", response_model=list[CategoryResponse], status_code=status.HTTP_200_OK)
async def get_categories(user: user_dependency, db: db_dependency):
    return db.query(Category).filter(Category.owner_id == user['id']).all()


@router.get("/{category_id}", response_model=CategoryResponse, status_code=status.HTTP_200_OK)
async def get_category(user: user_dependency, db: db_dependency,
                        category_id: Annotated[int, Path(gt=0)]):
    category = db.query(Category).filter(Category.id == category_id)\
        .filter(Category.owner_id == user['id']).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


@router.put("/{category_id}", response_model=CategoryResponse, status_code=status.HTTP_200_OK)
async def update_category(user: user_dependency, db: db_dependency,
                           category_request: CreateCategory,
                           category_id: Annotated[int, Path(gt=0)]):
    category = db.query(Category).filter(Category.id == category_id)\
        .filter(Category.owner_id == user['id']).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    category.name = category_request.name
    category.color = category_request.color
    db.commit()
    db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(user: user_dependency, db: db_dependency,
                           category_id: Annotated[int, Path(gt=0)]):
    category = db.query(Category).filter(Category.id == category_id)\
        .filter(Category.owner_id == user['id']).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    db.delete(category)
    db.commit()