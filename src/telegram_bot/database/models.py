from datetime import datetime
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class BaseModel(Base):
    __abstract__ = True
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class Subscription(BaseModel):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, index=True, nullable=False)
    uuid = Column(String(36), unique=True, nullable=False)
    amount = Column(Integer, nullable=False)
    hours = Column(Integer, nullable=False)
    status = Column(Text, nullable=False)
    chain = Column(String(20))
    address = Column(String(100))
    memberships = relationship("Membership", back_populates="subscription")

    __table_args__ = (Index("idx_user_status", "user_id", "status"),)

class Membership(BaseModel):
    __tablename__ = "memberships"
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, index=True, nullable=False, unique=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="SET NULL"))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    source = Column(String(20), nullable=False)
    is_banned = Column(Boolean, default=False, nullable=False)
    banned_at = Column(DateTime)
    remark = Column(String(255))
    version = Column(Integer, default=0, nullable=False)

    subscription = relationship("Subscription", back_populates="memberships")
    __table_args__ = (Index("idx_user_end_time", "user_id", "end_time"),)

class MembershipLog(BaseModel):
    __tablename__ = "membership_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, index=True, nullable=False)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="SET NULL"))
    operation = Column(String(10), nullable=False)
    old_end_time = Column(DateTime)
    new_end_time = Column(DateTime, nullable=False)
    remark = Column(String(255))
    subscription = relationship("Subscription")
    __table_args__ = (Index("idx_user_operation", "user_id", "operation"),)

class UserPermission(BaseModel):
    __tablename__ = "user_permissions"
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, index=True, nullable=False)
    permission_type = Column(String(30), nullable=False)
    __table_args__ = (UniqueConstraint("user_id", "permission_type", name="uq_user_permission"),)

class ChannelConfig(BaseModel):
    __tablename__ = "channel_configs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger, unique=True)
    channel_url = Column(String(255), unique=True, nullable=False)
    is_vip_channel = Column(Boolean, default=True, nullable=False)
    bot_joined = Column(Boolean, default=False, nullable=False)
    last_member_fetch_at = Column(DateTime)
    remark = Column(String(255))
    __table_args__ = (Index("idx_channel_vip", "channel_url"),)

class GroupMember(BaseModel):
    __tablename__ = "group_members"
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_id = Column(BigInteger, index=True, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    is_bot = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    cached_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("channel_id", "user_id", name="uq_channel_user"),
        Index("idx_channel_user", "channel_id", "user_id"),
    )

class KickLog(BaseModel):
    __tablename__ = "kick_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    target_user_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False)
    kicked_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class KickAfterInvite(BaseModel):
    __tablename__ = "kick_after_invite"
    id = Column(Integer, primary_key=True)
    kick_interval_seconds = Column(Integer, default=60, nullable=False)
    rejoin_delay_minutes = Column(Integer, default=300, nullable=False)
    last_executed_at = Column(DateTime)

class Admin(BaseModel):
    __tablename__ = "admins"
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(100))
    level = Column(Integer, default=1)
    remark = Column(String(255))
