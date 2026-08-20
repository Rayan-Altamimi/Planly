from fastapi import FastAPI
from database import engine, Base
from routers import auth, categories, tasks

app = FastAPI()

#Base.metadata.create_all(bind=engine)

app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(tasks.router)