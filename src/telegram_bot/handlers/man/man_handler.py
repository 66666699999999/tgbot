import math
from collections import defaultdict
from copy import deepcopy

from telegram import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes
from telethon.errors import UserNotParticipantError
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.functions.messages import GetFullChatRequest
from telethon.tl.types import Channel, ChannelParticipantsSearch, Chat, User

from telegram_bot.database.crud import (
    get_mem_all_chan,
    list_channel_configs,
)
from telegram_bot.database.db import async_session
from telegram_bot.handlers.states import ManagerState
from telegram_bot.utils.logger import setup_logger

from ..button import MANAGER_BACK_MENU_FIRST, MANAGER_HANDLE_USER_DETAIL_BUTTON

logger = setup_logger(__name__)


DETAIL_PAGE_SIZE = 10


async def hand_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data  # e.g. "page_bot_admin_list_2"
    parts = data.split("_")  # ['page', 'bot', 'admin', 'list', '2']

    # 提取 page
    try:
        page = int(parts[-1])
    except ValueError:
        await query.edit_message_text("⚠️ 页码格式错误。")
        return

    # 组合关键字识别页面类型
    page_key = "_".join(parts[:-2])  # e.g. "page_bot_admin_list"

    print(page_key)
    if page_key == "page_han_chan":
        await get_common_group_stats(update, context, page=page)
    elif page_key == "page_han_group_detail_":
        await show_user_group_detail(query, context, page=page)
    else:
        await query.edit_message_text("⚠️ 未知分页指令。")


def build_pagination_keyboard(prefix: str, page: int, page_size: int, total_items: int):
    """
    构造分页按钮。
    - prefix: callback_data 的前缀（如 "page_db_chan"）
    - page: 当前页码
    - page_size: 每页多少个
    - total_items: 总项目数
    """
    nav_buttons = []
    print(page, page_size, total_items)

    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton("◀️", callback_data=f"{prefix}_prev_{page - 1}")
        )
    if page * page_size < total_items:
        nav_buttons.append(
            InlineKeyboardButton("▶️", callback_data=f"{prefix}_next_{page + 1}")
        )

    return nav_buttons


def get_user_name(user):
    return user.username or f"{user.first_name or ''} {user.last_name or ''}".strip()


async def group_detail_input(update, context):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("📥 请输入用户 ID（纯数字）以查看其加入的群组明细：")
    context.user_data["state"] = ManagerState.AWAITING_DETAIL_ID


async def get_valid_group_urls():
    async with async_session() as session:
        configs = await list_channel_configs(session)
        return [c.channel_url for c in configs if c.channel_url]


async def get_common_group_stats(update: Update, context, page=1, page_size=10):
    """
    从数据库中获取所有成员的出现频道统计（分页）
    """
    query = update.callback_query
    try:
        await query.answer()

        async with async_session() as session:  # 获取 AsyncSession
            # 查询所有非 bot、非 deleted 的用户在不同频道的出现次数
            all_users = await get_mem_all_chan(session)

            total = len(all_users)
            start = (page - 1) * page_size
            end = start + page_size
            sliced_users = all_users[start:end]

            if not sliced_users:
                await query.edit_message_text("❌ 没有找到任何用户记录")
                return

            # 构造输出
            reply_lines = [f"📃 所有频道成员统计（第 {page} 页 / 共 {total} 人）："]
            for user_id, username, first_name, count in sliced_users:
                if username:
                    name = f"@{username}"
                else:
                    name = first_name or "未知用户"
                name = name.replace("_", "\\_")
                reply_lines.append(f"{name} | 加入频道数：{count} | ID: `{user_id}`")

            # 分页按钮
            buttons = deepcopy(MANAGER_HANDLE_USER_DETAIL_BUTTON)
            if total > page_size:
                pagination_buttons = build_pagination_keyboard(
                    "page_han_chan", page, page_size, total
                )
                buttons.append(pagination_buttons)
            buttons.append(deepcopy(MANAGER_BACK_MENU_FIRST))

            await query.edit_message_text(
                "\n".join(reply_lines),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(buttons),
            )

    except Exception as e:
        logger.exception("❌ 频道成员统计失败")
        await query.edit_message_text(f"❌ 统计失败：{e}")


# 再次确认用户是否仍在群中
async def is_user_in_group(client, group, user_id):
    try:
        if isinstance(group, Channel):
            # 超级群处理方式
            offset = 0
            while True:
                participants = await client(
                    GetParticipantsRequest(
                        channel=group,
                        filter=ChannelParticipantsSearch(""),
                        offset=offset,
                        limit=100,
                        hash=0,
                    )
                )
                if not participants.users:
                    break
                for user in participants.users:
                    if user.id == user_id:
                        return True
                offset += len(participants.users)
            return False
        elif isinstance(group, Chat):
            # 普通群处理方式
            full_chat = await client(GetFullChatRequest(group.id))
            for p in full_chat.full_chat.participants.participants:
                if p.user_id == user_id:
                    return True
            return False
        else:
            print(f"未知群类型: {group}")
            return False
    except Exception as e:
        print(f"确认用户 {user_id} 是否在群中失败: {e}")
        return False


# 获取用户加入的所有群组名称
async def get_user_groups(client, group_urls, user_id):
    group_names = []
    for url in group_urls:
        try:
            group = await client.get_entity(url)
            if await is_user_in_group(client, group, user_id):
                group_names.append(group.title)
        except Exception as e:
            logger.warning(f"处理群组 {url} 失败: {e}")
            continue
    return group_names


# 主函数（用于 bot 调用）
async def show_user_group_detail(update, context, page=0, page_size=10):
    message = update.message or update.callback_query.message
    query = update.callback_query

    if query:
        await query.answer()
        data = query.data  # e.g. "page_han_group_detail_123456_next_1"
        try:
            parts = data.split("_")
            target_user_id = int(parts[4])
            page = int(parts[-1])
        except Exception:
            await query.edit_message_text("❌ 分页参数错误")
            return
    else:
        text = message.text.strip()
        if not text.isdigit():
            await message.reply_text("❌ 请输入用户 ID（仅数字），仅支持一个用户")
            return
        target_user_id = int(text)

    client = context.bot_data.get("client")
    if not client:
        await message.reply_text("❌ Telethon client 未初始化")
        return

    try:
        await context.bot.get_chat(target_user_id)  # 校验用户 ID 是否有效
    except Exception:
        await message.reply_text("❌ 无效 ID")
        return

    try:
        group_urls = await get_valid_group_urls()
        if not group_urls:
            await message.reply_text("⚠️ 暂无任何已配置的频道链接")
            return

        group_names = await get_user_groups(client, group_urls, target_user_id)
        total = len(group_names)

        if total == 0:
            await message.reply_text(f"🔍 用户 {target_user_id} 未加入任何管理群组")
            return

        start = page * page_size
        end = start + page_size
        sliced = group_names[start:end]

        lines = [
            f"👤 用户 <code>{target_user_id}</code> 加入的群组（第 {page + 1} 页，共 {((total - 1) // page_size) + 1} 页）:"
        ]
        lines += [f"• {title}" for title in sliced]

        nav_buttons = []
        if total > page_size:
            nav_buttons = build_pagination_keyboard(
                prefix=f"page_han_group_detail_{target_user_id}",
                page=page,
                page_size=page_size,
                total_items=total,
            )
        markup = InlineKeyboardMarkup([nav_buttons]) if nav_buttons else None

        if query:
            await query.edit_message_text(
                "\n".join(lines),
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )
        else:
            await message.reply_text(
                "\n".join(lines),
                parse_mode=ParseMode.HTML,
                reply_markup=markup,
            )

    except Exception as e:
        logger.exception("查询用户群组详情时出错")
        await message.reply_text(f"❌ 查询失败：{e}")
