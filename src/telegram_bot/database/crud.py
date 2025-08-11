import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from telegram_bot.utils.logger import setup_logger
from sqlalchemy import and_, delete, desc, exists, func, or_, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError

from .models import (
    Admin,
    ChannelConfig,
    GroupMember,
    KickAfterInvite,
    KickLog,
    Membership,
    MembershipLog,
    Subscription,
)

logger = setup_logger(__name__)
# -----------------
# subscription.py
# -----------------
# 订阅记录
async def add_or_update_subscription(
    session: AsyncSession,
    user_id: int,
    amount: int,
    hours: int,
    invoice_id: str = None,
    chain: str = None,
    address: str = None,
    status: str = None,
):
    uuid_str = invoice_id or str(uuid.uuid4())

    # 每次都创建新的订阅记录
    sub = Subscription(
        user_id=user_id,
        amount=amount,
        hours=hours,
        uuid=uuid_str,
        chain=chain,
        address=address,
        status=status or "pending",
    )
    try:
        session.add(sub)
    except SQLAlchemyError as e:
        logger.error(e)
        return False
    except Exception as e:
        logger.error(e)
        return False
    await session.commit()
    return sub


async def can_user_resubscribe(session: AsyncSession, user_id: int) -> bool:
    # 获取会员记录
    stmt = select(Membership).where(Membership.user_id == user_id)
    try:
        result = await session.execute(stmt)

        membership = result.scalar_one_or_none()

        if not membership:
            # 用户从未订阅过，可以订阅
            return True

        if not membership.is_banned:
            # 用户未被封禁，可以订阅
            return True

        # 如果被封禁，检查 rejoin_delay_minutes 是否已到
        if not membership.banned_at:
            # 安全兜底：没有被封禁时间，认为暂不允许
            return False

        # 获取 rejoin_delay_minutes 设置
        config_stmt = select(KickAfterInvite).limit(1)
        config_result = await session.execute(config_stmt)
        config = config_result.scalar_one_or_none()

        if not config:
            # 没有配置则默认禁止重新加入
            return False

        allow_time = membership.banned_at + timedelta(minutes=config.rejoin_delay_minutes)
        return datetime.utcnow() >= allow_time
    except SQLAlchemyError as e:
        logger.error(e)
        return False
    except Exception as e:
        logger.error(e)
        return False



# -----------------
# account.py
# -----------------


# 个人账户信息
async def get_latest_membership(session: AsyncSession, user_id: int):
    try:
        result = await session.execute(
            select(Membership)
            .where(Membership.user_id == user_id)
            .order_by(desc(Membership.end_time))
            .limit(1)
        )
        return result.scalar_one_or_none()
    except SQLAlchemyError as e:
        logger.error(e)
        return False
    except Exception as e:
        logger.error(e)
        return False




# -----------------
# join_group.py
# -----------------


# 个人频道返回
async def get_user_channels(session: AsyncSession, user_id: int):
    """根据用户是否是 VIP，返回对应的频道链接列表"""
    now = datetime.utcnow()


    try:
        # 检查会员状态
        stmt = select(Membership).where(
            Membership.user_id == user_id,
            Membership.start_time <= now,
            Membership.end_time >= now,
            Membership.is_banned == False,
        )
        result = await session.execute(stmt)
        membership = result.scalar_one_or_none()

        # VIP用户可见所有，非VIP只能看到 is_vip_channel=False 的频道
        if membership:
            stmt = select(ChannelConfig.channel_url)
        else:
            stmt = select(ChannelConfig.channel_url).where(
                ChannelConfig.is_vip_channel == False
            )

        result = await session.execute(stmt)
        channel_urls = result.scalars().all()
        return channel_urls
    except SQLAlchemyError as e:
        logger.error(e)
        return []
    except Exception as e:
        logger.error(e)
        return []



# -----------------
# man_vip.py
# -----------------


async def check_vip_status(session):
    try:
        result = await session.execute(
            select(Membership)
            .order_by(Membership.end_time.desc())
            .options(selectinload(Membership.subscription))
        )
        members = result.scalars().all()
        return members
    except SQLAlchemyError as e:
        logger.error(e)
        return False
    except Exception as e:
        logger.error(e)
        return False



# 会员添加

async def process_memberships_by_uuids(
    session: AsyncSession, uuid_list: List[str]
) -> dict:
    added = 0
    renewed = 0
    now = datetime.utcnow()

    try:
        for uuid_str in uuid_list:
            uuid_str = uuid_str.strip()
            result = await session.execute(
                select(Subscription).where(Subscription.uuid == uuid_str)
            )
            sub = result.scalars().first()

            if not sub or sub.status == "failed":
                continue

            # 避免重复处理
            log_check = await session.execute(
                select(MembershipLog).where(MembershipLog.subscription_id == sub.id)
            )
            if log_check.scalar_one_or_none():
                continue

            # 查询当前会员记录
            mem_result = await session.execute(
                select(Membership)
                .where(Membership.user_id == sub.user_id)
                .order_by(Membership.end_time.desc())
                .limit(1)
            )
            membership = mem_result.scalars().first()

            sub.status = "success"

            if membership:
                # 记录当前 version
                old_version = membership.version

                # 计算新的 end_time
                new_end_time = max(membership.end_time, now) + timedelta(hours=sub.hours)

                # 乐观锁更新
                result = await session.execute(
                    update(Membership)
                    .where(
                        Membership.id == membership.id,
                        Membership.version == old_version
                    )
                    .values(
                        end_time=new_end_time,
                        version=old_version + 1
                    )
                )
                if result.rowcount == 0:
                    # 并发冲突
                    logger.warning(f"⚠️ 并发冲突跳过 UUID: {uuid_str}")
                    continue

                renewed += 1
                operation = "renew"
                remark = f"通过交易 {uuid_str} 续期 {sub.hours}小时"
                old_end_time = membership.end_time

            else:
                # 新开通会员
                new_member = Membership(
                    user_id=sub.user_id,
                    subscription_id=sub.id,
                    start_time=now,
                    end_time=now + timedelta(hours=sub.hours),
                    source="admin_manual",
                    remark="手动开通",
                    version=1,
                )
                session.add(new_member)
                membership = new_member
                old_end_time = None
                operation = "new"
                remark = f"通过交易 {uuid_str} 开通 {sub.hours}小时"
                added += 1

            log = MembershipLog(
                user_id=sub.user_id,
                subscription_id=sub.id,
                operation=operation,
                old_end_time=old_end_time,
                new_end_time=membership.end_time,
                remark=remark,
            )
            session.add(log)

        await session.commit()
        return {"added": added, "renewed": renewed}

    except SQLAlchemyError as e:
        logger.error(f"数据库错误: {e}")
        await session.rollback()
        return {}
    except Exception as e:
        logger.error(f"处理异常: {e}")
        await session.rollback()
        return {}


# 删除会员
async def delete_memberships(session: AsyncSession, user_id_list: List[int]) -> int:
    deleted_count = 0
    current_time = datetime.utcnow()

    for user_id in user_id_list:
        try:
            result = await session.execute(
                select(Membership).where(Membership.user_id == user_id)
            )
            member = result.scalars().first()

            if member:
                # 记录删除操作
                log = MembershipLog(
                    user_id=user_id,
                    subscription_id=member.subscription_id,
                    operation="delete",
                    old_end_time=member.end_time,
                    new_end_time=current_time,
                    remark="管理员手动删除会员",
                )
                session.add(log)

                # 删除会员
                await session.delete(member)
                deleted_count += 1
        except SQLAlchemyError as e:
            logger.error(e)
            return 0
        except Exception as e:
            logger.error(e)
            return 0

    await session.commit()
    return deleted_count


# -----------------
# man_bot.py   man_handler.py
# -----------------


async def get_mem_all_chan(session):
    try:
        stmt = (
            select(
                GroupMember.user_id,
                GroupMember.username,
                GroupMember.first_name,
                func.count(GroupMember.channel_id).label("channel_count"),
            )
            .where(GroupMember.is_bot == False, GroupMember.is_deleted == False)
            .group_by(GroupMember.user_id, GroupMember.username, GroupMember.first_name)
            .order_by(func.count(GroupMember.channel_id).desc())
        )
        result = await session.execute(stmt)
        return result.all()
    except SQLAlchemyError as e:
        logger.error(e)
        return False
    except Exception as e:
        logger.error(e)
        return False


# 频道信息添加
async def add_channel_config(
    session: AsyncSession,
    channel_id: int = None,
    channel_url: str = None,
    is_vip_channel: bool = True,
    bot_joined: bool = False,
    remark: str = None,
):
    try:
        new_config = ChannelConfig(
            channel_id=channel_id,
            channel_url=channel_url,
            is_vip_channel=is_vip_channel,
            bot_joined=bot_joined,
            remark=remark,
        )
        session.add(new_config)
        await session.commit()
        await session.refresh(new_config)
        return new_config
    except SQLAlchemyError as e:
        logger.error(e)
        return False
    except Exception as e:
        logger.error(e)
        return False


# 删除频道配置（按 channel_id）
async def delete_channel_config(session: AsyncSession, *, channel_url: str = None):
    if not channel_url:
        return False

    try:
        stmt = delete(ChannelConfig).where(ChannelConfig.channel_url == channel_url)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0
    except SQLAlchemyError as e:
        logger.error(e)
        return False
    except Exception as e:
        logger.error(e)
        return False


async def list_channel_configs(session: AsyncSession):
    try:
        stmt = select(ChannelConfig)
        result = await session.execute(stmt)
        return result.scalars().all()
    except SQLAlchemyError as e:
        logger.error(e)
        return False
    except Exception as e:
        logger.error(e)
        return False


async def get_channel_by_url(session: AsyncSession, url: str):
    try:
        result = await session.execute(
            select(ChannelConfig).where(ChannelConfig.channel_url == url)
        )
        return result.scalar_one_or_none()
    except SQLAlchemyError as e:
        logger.error(e)
        return False
    except Exception as e:
        logger.error(e)
        return False


# -----------------
# job.py
# -----------------


async def get_expired_memberships(session) -> List[Membership]:
    now = datetime.utcnow()
    try:
        stmt = select(Membership).where(
            Membership.end_time < now,
            Membership.is_banned == False,
            Membership.banned_at.is_(None),
        )
        result = await session.execute(stmt)
        return result.scalars().all()
    except SQLAlchemyError as e:
        logger.error(e)
        return []
    except Exception as e:
        logger.error(e)
        return []


# 检查即将过期的会员
async def get_expiring_soon_memberships(
    session: AsyncSession, within_days: int = 3
) -> List[Membership]:
    now = datetime.utcnow()
    threshold = now + timedelta(days=within_days)
    try:
        result = await session.execute(
            select(Membership).where(
                Membership.end_time > now, Membership.end_time <= threshold
            )
        )
        return result.scalars().all()
    except SQLAlchemyError as e:
        logger.error(e)
        return []
    except Exception as e:
        logger.error(e)
        return []


# -----------------
# man_bot.py
# -----------------


async def set_or_get_kick_config(
    session: AsyncSession,
    kick_interval_seconds: int = None,
    rejoin_delay_minutes: int = None,
) -> KickAfterInvite:
    """
    如果传入了值则更新，否则返回当前配置。
    """

    stmt = select(KickAfterInvite).limit(1)
    result = await session.execute(stmt)
    config = result.scalar_one_or_none()

    if not config:
        config = KickAfterInvite()
        session.add(config)

    if kick_interval_seconds is not None:
        config.kick_interval_seconds = kick_interval_seconds

    if rejoin_delay_minutes is not None:
        config.rejoin_delay_minutes = rejoin_delay_minutes

    await session.commit()
    await session.refresh(config)
    return config


async def get_vip_channels(session: AsyncSession) -> List[ChannelConfig]:
    """获取所有VIP频道配置"""
    result = await session.execute(
        select(ChannelConfig).where(ChannelConfig.is_vip_channel == True)
    )
    return result.scalars().all()


async def get_kick_setting(session: AsyncSession) -> Optional[KickAfterInvite]:
    """获取踢人设置"""
    result = await session.execute(select(KickAfterInvite).limit(1))
    return result.scalar_one_or_none()


async def record_kick(
    session: AsyncSession,
    user_id: int,
    channel_id: int,
    kicked_at: datetime = None,
) -> KickLog:
    """记录踢人操作"""
    if kicked_at is None:
        kicked_at = datetime.utcnow()

    kick_record = KickLog(
        target_user_id=user_id,
        channel_id=channel_id,
        kicked_at=kicked_at,
    )
    session.add(kick_record)
    await session.commit()
    return kick_record


async def add_admin(
    session: AsyncSession, operator_user_id: int, new_admin_data: dict
) -> str:
    """
    添加管理员，普通管理员不能添加超级管理员
    new_admin_data 示例: {
        "user_id": 123456,
        "username": "abc",
        "level": 10,
        "remark": "创始人"
    }
    """
    try:
    # 查询操作者权限
        result = await session.execute(
            select(Admin).where(Admin.user_id == operator_user_id)
        )
        operator = result.scalars().first()
        if not operator:
            return f"❌ 操作者无权限"

        if operator.level < 10 and new_admin_data.get("level", 1) == 10:
            return "❌ 权限不足，不能添加超级管理员"

        # 检查目标用户是否已存在
        result = await session.execute(
            select(Admin).where(Admin.user_id == new_admin_data["user_id"])
        )
        existing = result.scalars().first()
        if existing:
            return "⚠️ 用户已是管理员"

        new_admin = Admin(**new_admin_data)
        session.add(new_admin)
        await session.commit()

        return "✅ 添加管理员成功"
    except SQLAlchemyError as e:
        logger.error(e)
        return "❌ 管理员错误"
    except Exception as e:
        logger.error(e)
        return "❌ 管理员错误"


async def delete_admin(
    session: AsyncSession, operator_user_id: int, target_user_id: int
) -> str:
    """
    删除管理员，普通管理员不能删除超级管理员
    """
    result = await session.execute(
        select(Admin).where(Admin.user_id == operator_user_id)
    )
    operator = result.scalars().first()
    if not operator:
        return "❌ 操作者无权限"

    result = await session.execute(select(Admin).where(Admin.user_id == target_user_id))
    target = result.scalars().first()
    if not target:
        return "⚠️ 目标用户不是管理员"

    if operator.level < 10 and target.level == 10:
        return "❌ 权限不足，不能删除超级管理员"

    await session.delete(target)
    await session.commit()
    return "✅ 管理员已删除"


async def list_admins(session: AsyncSession) -> List[dict]:
    """
    获取所有管理员列表
    """
    result = await session.execute(select(Admin).order_by(Admin.level.desc()))
    admins = result.scalars().all()

    return [
        {
            "user_id": admin.user_id,
            "username": admin.username,
            "level": admin.level,
            "remark": admin.remark,
        }
        for admin in admins
    ]


# -----------------
# man_bot.py
# -----------------


async def set_ban_members(session: AsyncSession, user_ids: List[int]):
    if not user_ids:
        return

    ban_time = datetime.utcnow()

    try:
        for user_id in user_ids:
            # 获取当前记录和版本号
            result = await session.execute(
                select(Membership).where(Membership.user_id == user_id)
            )
            member = result.scalars().first()
            if not member:
                continue

            old_version = member.version

            stmt = (
                update(Membership)
                .where(
                    Membership.user_id == user_id,
                    Membership.version == old_version,
                    Membership.is_banned == False  # 避免重复操作
                )
                .values(
                    is_banned=True,
                    banned_at=ban_time,
                    version=old_version + 1
                )
            )

            await session.execute(stmt)

        await session.commit()
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(e)
        return False
    except Exception as e:
        await session.rollback()
        logger.error(e)
        return False



async def recover_ban(session: AsyncSession):
    """
    自动解除所有达到解除封禁时间的被ban用户
    """
    # 从数据库读取解除封禁时间（分钟）
    try:
        setting = await get_kick_setting(session)
        rejoin_delay_minutes = setting.rejoin_delay_minutes if setting else 300

        cutoff_time = datetime.utcnow() - timedelta(seconds=rejoin_delay_minutes)

        # 查询符合条件的被封禁会员
        stmt = select(Membership).where(
            Membership.is_banned == True,
            Membership.banned_at.is_(None),
            Membership.banned_at <= cutoff_time,
        )
        result = await session.execute(stmt)
        members = result.scalars().all()

        if not members:
            return

        user_ids = [m.user_id for m in members]

        # 批量解除封禁
        stmt_update = (
            update(Membership)
            .where(Membership.user_id.in_(user_ids))
            .values(is_banned=False)
        )
        await session.execute(stmt_update)
        await session.commit()

        return user_ids
    except SQLAlchemyError as e:
        logger.error(e)
        return False
    except Exception as e:
        logger.error(e)
        return False


async def save_chan_mem(session: AsyncSession, user, channel_id: int):
    now = datetime.utcnow()
    try:
        stmt = (
            sqlite_insert(GroupMember)
            .values(
                user_id=user.id,
                channel_id=channel_id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                is_bot=user.bot,
                is_deleted=user.deleted,
                cached_at=now,
            )
            .on_conflict_do_update(
                index_elements=["channel_id", "user_id"],
                set_={
                    "username": user.username,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "is_bot": user.bot,
                    "is_deleted": user.deleted,
                    "cached_at": now,
                },
            )
        )

        await session.execute(stmt)
        await session.commit()
    except SQLAlchemyError as e:
        logger.error(e)
        return False
    except Exception as e:
        logger.error(e)
        return False


async def fetch_config_group(session: AsyncSession, cutoff_time):
    try:
        re = await session.execute(
            select(ChannelConfig.channel_url).where(
                or_(
                    ChannelConfig.last_member_fetch_at.is_(None),
                    ChannelConfig.last_member_fetch_at < cutoff_time,
                )
            )
        )
        return re
    except SQLAlchemyError as e:
        logger.error(e)
        return False
    except Exception as e:
        logger.error(e)
        return False


async def update_config_time(session: AsyncSession, group_url):
    try:
        await session.execute(
            update(ChannelConfig)
            .where(ChannelConfig.channel_url == group_url)
            .values(last_member_fetch_at=datetime.utcnow())
        )
    except SQLAlchemyError as e:
        logger.error(e)
        return False
    except Exception as e:
        logger.error(e)
        return False
