import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./planly.db")

if not SECRET_KEY:
    raise ValueError("SECRET_KEY is not set. Add it to your .env file.")