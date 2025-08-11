import os
import json
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from telegram_bot.config import DB_PATH
from ..config import JSON_DIR
from .models import Base
from functools import wraps
def load_db_config():
    path = os.path.join(JSON_DIR, "db.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    raise FileNotFoundError("db.json 配置文件不存在")

def build_database_url(config: dict) -> str:
    if config["db_type"] == "sqlite":
        return f"sqlite+aiosqlite:///{DB_PATH}"
    elif config["db_type"] == "postgresql":
        user = config["username"]
        password = config["password"]
        host = config["host"]
        port = config["port"]
        dbname = config["database"]
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"
    elif config["db_type"] == "mysql":
        user = config["username"]
        password = config["password"]
        host = config["host"]
        port = config["port"]
        dbname = config["database"]
        return f"mysql+aiomysql://{user}:{password}@{host}:{port}/{dbname}?charset=utf8mb4"
    else:
        raise ValueError("Unsupported DB type")

config = load_db_config()
DATABASE_URL = build_database_url(config)

engine = create_async_engine(DATABASE_URL, echo=False, future=True, poolclass=NullPool)
async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)



async def init_db():
    async with engine.begin() as conn:
        if DATABASE_URL.startswith("sqlite"):
            await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.run_sync(Base.metadata.create_all)


def async_session_decorator(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        async with async_session() as session:
            try:
                # 将 session 注入到函数参数中
                result = await func(*args, **kwargs, session=session)
                await session.commit()
                return result
            except Exception as e:
                await session.rollback()
                raise e
    return wrapper
