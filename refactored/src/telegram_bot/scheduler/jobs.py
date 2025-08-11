from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.error import Forbidden
from telethon.errors import (
    ChannelPrivateError,
    UserAdminInvalidError,
    UserIsBlockedError,
    UserNotParticipantError,
)
from telethon.tl.functions.channels import EditBannedRequest, GetParticipantsRequest
from telethon.tl.functions.messages import DeleteChatUserRequest, GetFullChatRequest
from telethon.tl.types import Channel, ChannelParticipantsSearch, Chat, ChatBannedRights

from telegram_bot.database.crud import (
    fetch_config_group,
    get_expired_memberships,
    get_expiring_soon_memberships,
    get_kick_setting,
    get_vip_channels,
    record_kick,
    recover_ban,
    save_chan_mem,
    set_ban_members,
    update_config_time,
)
from telegram_bot.database.db import async_session
from telegram_bot.utils.logger import setup_logger

logger = setup_logger(__name__)


async def kick_user_from_group(client, channel_id: int, user_id: int):
    """
    自动判断群类型并踢人，兼容频道/超级群/普通群
    """
    try:
        entity = await client.get_entity(channel_id)

        if isinstance(entity, Channel) and entity.megagroup:
            # 超级群 / 频道
            participant = await client.get_input_entity(user_id)
            await client(
                EditBannedRequest(
                    channel=entity,
                    participant=participant,
                    banned_rights=ChatBannedRights(until_date=None, view_messages=True),
                )
            )
            logger.info(f"✅ 已踢出用户 {user_id} 从超级群 {channel_id}")

        elif isinstance(entity, Chat):
            # 普通群
            user = await client.get_input_entity(user_id)
            await client(
                DeleteChatUserRequest(
                    chat_id=entity.id, user_id=user, revoke_history=True
                )
            )
            logger.info(f"✅ 已踢出用户 {user_id} 从普通群 {channel_id}")

        else:
            logger.error(f"❌ 未知群类型: {type(entity)}")

    except UserNotParticipantError:
        logger.warning(f"⚠️ 用户 {user_id} 不在群组 {channel_id}")
    except UserAdminInvalidError:
        logger.error(f"❌ 没有权限踢出用户 {user_id}（需要管理权限）")
    except Exception as e:
        logger.error(f"❌ 踢出用户失败: {e}")


async def kick_expired_members(client):
    """
    自动踢出过期会员的任务
    """
    async with async_session() as session:
        # 获取过期会员
        expired_members = await get_expired_memberships(session)
        if not expired_members:
            return

        # 获取VIP频道
        vip_channels = await get_vip_channels(session)
        if not vip_channels:
            logger.info("❌ 未找到VIP频道配置")
            return

        now = datetime.utcnow()

        for member in expired_members:
            for channel in vip_channels:
                try:
                    # 踢出用户
                    await kick_user_from_group(
                        client, channel.channel_id, member.user_id
                    )

                    # 记录踢出操作
                    await record_kick(
                        session,
                        user_id=member.user_id,
                        channel_id=channel.channel_id,
                        kicked_at=now,
                    )

                    logger.info(
                        f"✅ 已踢出过期会员 {member.user_id} 从频道 {channel.channel_id}"
                    )

                except UserNotParticipantError:
                    logger.warning(
                        f"⚠️ 用户 {member.user_id} 已不在频道 {channel.channel_id} 中"
                    )
                    continue
                except ChannelPrivateError:
                    logger.error(f"❌ 无法访问频道 {channel.channel_id}")
                    continue
                except Exception as e:
                    logger.error(f"❌ 踢人失败: {str(e)}")
                    continue

        # 删除过期会员记录
        if expired_members:
            await set_ban_members(session, [m.user_id for m in expired_members])
            logger.info(f"✅ 已删除 {len(expired_members)} 个过期会员记录")

        logger.info(f"🔄 自动踢人任务完成")


# ⏰ 提醒会员即将过期任务
async def remind_membership_expiring(bot):
    """
    提醒即将过期会员的任务
    """
    async with async_session() as session:
        members = await get_expiring_soon_memberships(session, within_days=7)
        if not members:
            return

        for member in members:
            try:
                await bot.send_message(
                    member.user_id,
                    "⚠️ 您的会员将在 7 天后到期，请及时续费以避免被踢出频道。",
                )
                logger.info(f"✅ 已发送过期提醒给用户 {member.user_id}")
            except Forbidden:
                logger.warning(f"🚫 用户 {member.user_id} 未开启或屏蔽了 bot")
            except Exception as e:
                logger.error(f"❌ 无法发送提醒给 {member.user_id}: {str(e)}")


async def recover_ban_members(client):
    async with async_session() as session:
        user_ids = await recover_ban(session)  # 返回已解除封禁状态的 user_id 列表

        if not user_ids:
            return

        vip_channels = await get_vip_channels(session)
        if not vip_channels:
            logger.info("❌ 未找到VIP频道配置")
            return

        success_count = 0
        fail_count = 0

        for user_id in user_ids:
            for channel in vip_channels:
                try:
                    entity = await client.get_entity(channel.channel_id)

                    if isinstance(entity, Channel) and entity.megagroup:
                        participant = await client.get_input_entity(user_id)
                        await client(
                            EditBannedRequest(
                                channel=entity,
                                participant=participant,
                                banned_rights=ChatBannedRights(
                                    until_date=None, view_messages=False
                                ),
                            )
                        )
                        logger.info(
                            f"✅ 已解禁用户 {user_id} 于超级群 {channel.channel_id}"
                        )
                        success_count += 1
                    else:
                        logger.info(f"⚠️ 频道 {channel.channel_id} 不是超级群")
                except Exception as e:
                    logger.info(
                        f"❌ 解禁用户 {user_id} 于 {channel.channel_id} 失败: {e}"
                    )
                    fail_count += 1

        logger.info(f"🔁 解禁完成，成功: {success_count} 次，失败: {fail_count} 次")


async def fetch_group_participants(client, group):
    users = []

    try:
        if isinstance(group, Channel):
            offset = 0
            limit = 100
            while True:
                try:
                    participants = await client(
                        GetParticipantsRequest(
                            channel=group,
                            filter=ChannelParticipantsSearch(""),
                            offset=offset,
                            limit=limit,
                            hash=0,
                        )
                    )
                    if not participants.users:
                        break
                    users.extend(participants.users)
                    offset += len(participants.users)
                except Exception as e:
                    logger.warning(f"⚠️ 获取超级群成员失败: {group.id} - {e}")
                    break

        elif isinstance(group, Chat):
            try:
                full_chat = await client(GetFullChatRequest(group.id))
                for p in full_chat.full_chat.participants.participants:
                    try:
                        user = await client.get_entity(p.user_id)
                        users.append(user)
                    except Exception as e:
                        logger.warning(f"获取用户信息失败 user_id={p.user_id}: {e}")
            except Exception as e:
                logger.warning(f"获取普通群成员失败: {group.id} - {e}")

    except Exception as e:
        logger.warning(f"⚠️ 获取群成员失败: {group.id} - {e}")

    return users


async def update_all_group_members(client):
    """
    遍历数据库中所有群组链接，抓取成员并存入 group_members 表（限制抓取频率）
    """
    async with async_session() as session:
        cutoff_time = datetime.utcnow() - timedelta(minutes=60)

        # 仅获取从未抓取过或抓取时间已过期的群组
        result = await fetch_config_group(session, cutoff_time)
        group_urls = [row[0] for row in result.fetchall()]

        for group_url in group_urls:
            try:
                entity = await client.get_entity(group_url)
            except Exception as e:
                logger.warning(f"⚠️ 获取实体失败: {group_url} - {e}")
                continue

            try:
                participants = await fetch_group_participants(client, entity)
            except Exception as e:
                logger.warning(f"⚠️ 获取成员失败: {group_url} - {e}")
                continue

            for user in participants:
                if user.bot or user.deleted:
                    continue
                await save_chan_mem(session, user, entity.id)

            # 更新该群组的 last_member_fetch_at
            await update_config_time(session, group_url)

        await session.commit()

    logger.info("✅ 群组成员信息更新完毕")


async def setup_scheduler(application):
    """
    设置定时任务
    """
    bot = application.bot
    scheduler = AsyncIOScheduler()
    client = application.bot_data.get("client")

    async with async_session() as session:
        setting = await get_kick_setting(session)
        seconds = setting.kick_interval_seconds if setting else 60
        back_time = setting.rejoin_delay_minutes if setting else 60

    # 频率执行踢人任务
    scheduler.add_job(kick_expired_members, "interval", seconds=seconds, args=[client])

    scheduler.add_job(recover_ban_members, "interval", seconds=back_time, args=[client])

    # 每天凌晨 3 点更新所有群组成员（UTC 时间）
    scheduler.add_job(
        update_all_group_members,
        "cron",
        hour=3,
        minute=0,
        args=[client],  # 注意这里传入的是 session 工厂
    )

    # 每天凌晨2点执行提醒任务，使用的是 UTC + 0 时间
    scheduler.add_job(
        remind_membership_expiring,
        "cron",
        hour=17,
        minute=2,
        args=[bot],
    )

    scheduler.start()
    application.bot_data["scheduler"] = scheduler
    logger.info("✅ 定时任务已启动")
