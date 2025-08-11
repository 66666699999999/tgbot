from abc import ABC, abstractmethod
from sqlalchemy import select
from .database import db_manager
from .database.models import UserPermission


class UserDataStore(ABC):
    @abstractmethod
    async def set_language(self, user_id, lang):
        pass

    @abstractmethod
    async def get_language(self, user_id):
        pass


class InMemoryUserDataStore(UserDataStore):
    def __init__(self):
        self.user_language = {}

    async def set_language(self, user_id, lang):
        self.user_language[user_id] = lang

    async def get_language(self, user_id):
        return self.user_language.get(user_id, "en")  # 默认英文


class DatabaseUserDataStore(UserDataStore):
    async def set_language(self, user_id, lang):
        async with db_manager.get_session()() as session:
            # 这里假设我们有一个 User 模型来存储用户语言
            # 为了简化，我们可以使用 UserPermission 表来存储语言偏好
            # 实际应用中应该创建一个单独的 User 表
            result = await session.execute(
                select(UserPermission).where(
                    UserPermission.user_id == user_id,
                    UserPermission.permission_type == "language"
                )
            )
            permission = result.scalar_one_or_none()

            if permission:
                permission.permission_type = f"language:{lang}"
            else:
                # 在实际应用中，这里应该创建一个新的 User 记录
                # 为了简化，我们使用 UserPermission 表
                pass

            await session.commit()

    async def get_language(self, user_id):
        async with db_manager.get_session()() as session:
            result = await session.execute(
                select(UserPermission).where(
                    UserPermission.user_id == user_id,
                    UserPermission.permission_type.like("language:%")
                )
            )
            permission = result.scalar_one_or_none()

            if permission:
                return permission.permission_type.split(":")[1]
            return "en"  # 默认英文


# 创建用户数据存储实例
# 可以根据配置选择使用内存存储或数据库存储
data_store = InMemoryUserDataStore()