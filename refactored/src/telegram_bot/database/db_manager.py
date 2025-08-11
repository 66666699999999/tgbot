import os
import json
from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from ..config import JSON_DIR
from .models import Base


class DatabaseManager(ABC):
    @abstractmethod
    async def init_db(self):
        pass

    @abstractmethod
    def get_session(self):
        pass


class SQLiteManager(DatabaseManager):
    def __init__(self, db_path):
        self.database_url = f"sqlite+aiosqlite:///{db_path}"
        self.engine = create_async_engine(
            self.database_url, echo=False, future=True, poolclass=NullPool
        )
        self.async_session = sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.run_sync(Base.metadata.create_all)

    def get_session(self):
        return self.async_session


class PostgreSQLManager(DatabaseManager):
    def __init__(self, username, password, host, port, database):
        self.database_url = f"postgresql+asyncpg://{username}:{password}@{host}:{port}/{database}"
        self.engine = create_async_engine(
            self.database_url, echo=False, future=True, poolclass=NullPool
        )
        self.async_session = sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    def get_session(self):
        return self.async_session


class MySQLManager(DatabaseManager):
    def __init__(self, username, password, host, port, database):
        self.database_url = f"mysql+aiomysql://{username}:{password}@{host}:{port}/{database}?charset=utf8mb4"
        self.engine = create_async_engine(
            self.database_url, echo=False, future=True, poolclass=NullPool
        )
        self.async_session = sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    def get_session(self):
        return self.async_session


class DatabaseManagerFactory:
    @staticmethod
    def create_manager(config):
        db_type = config["db_type"]

        if db_type == "sqlite":
            from ..config import DB_PATH
            return SQLiteManager(DB_PATH)
        elif db_type == "postgresql":
            return PostgreSQLManager(
                config["username"],
                config["password"],
                config["host"],
                config["port"],
                config["database"],
            )
        elif db_type == "mysql":
            return MySQLManager(
                config["username"],
                config["password"],
                config["host"],
                config["port"],
                config["database"],
            )
        else:
            raise ValueError(f"Unsupported database type: {db_type}")


def load_db_config():
    path = os.path.join(JSON_DIR, "db.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    raise FileNotFoundError("db.json 配置文件不存在")


# 创建数据库管理器实例
config = load_db_config()
db_manager = DatabaseManagerFactory.create_manager(config)