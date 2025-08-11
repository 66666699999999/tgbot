import re
import uuid
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch

from telegram_bot.database.crud import (
    check_vip_status,
    delete_memberships,
    process_memberships_by_uuids,
)
from telegram_bot.database.db import async_session
from telegram_bot.database.models import Membership, MembershipLog
from telegram_bot.handlers.states import ManagerState

from ..button import VIP_BACK_MAN_THIRD, VIP_SELECT_BUTTON


async def vip_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    await check_membership_info(query, context, page)


def build_pagination_keyboard(prefix: str, page: int, page_size: int, total_items: int):
    """
    构造分页按钮。
    - prefix: callback_data 的前缀（如 "page_db_chan"）
    - page: 当前页码
    - page_size: 每页多少个
    - total_items: 总项目数
    """
    nav_buttons = []

    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton("◀️", callback_data=f"{prefix}_prev_{page - 1}")
        )
    if page * page_size < total_items:
        nav_buttons.append(
            InlineKeyboardButton("▶️", callback_data=f"{prefix}_next_{page + 1}")
        )

    return nav_buttons


async def handle_manager_vip(update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    selected_plan = query.data
    context.user_data["selected_plan"] = selected_plan

    payment_keyboard = deepcopy(VIP_SELECT_BUTTON)

    await query.edit_message_text(
        text="请选择", reply_markup=InlineKeyboardMarkup(payment_keyboard)
    )


async def handle_man_cha_vip(query, context):
    await query.answer()
    data = query.data

    if data == "vip_open":
        await query.message.reply_text(
            "请输入用户的交易票据，已开通或者过期会员请到续费功能操作，支持批量添加\n例如："
        )
        context.user_data["state"] = ManagerState.AWAITING_VIP_OPEN
    elif data == "vip_renew":
        await query.message.reply_text(
            "请输入用户的交易票据，还未开通的会员请到开通功能操作，支持批量添加"
        )
        context.user_data["state"] = ManagerState.AWAITING_VIP_RENEW

    elif data == "vip_kick":
        await query.message.reply_text("请输入要删除订阅的用户ID：")
        context.user_data["state"] = ManagerState.AWAITING_VIP_DELETE


def validate_uuid_list(uuid_list: List[str]) -> bool:
    for u in uuid_list:
        try:
            uuid_obj = uuid.UUID(u)
        except ValueError:
            return False
    return True


async def vip_delete(update: Update) -> None:
    text = update.message.text or ""
    user_id_list = []

    # 解析输入的用户ID
    for id_str in text.split():
        try:
            user_id = int(id_str.strip())
            user_id_list.append(user_id)
        except ValueError:
            await update.message.reply_text(f"无效的用户ID格式: {id_str}")
            return

    if not user_id_list:
        await update.message.reply_text("请输入要删除的用户ID。")
        return

    async with async_session() as session:
        deleted_count = await delete_memberships(session, user_id_list)

    await update.message.reply_text(f"🗑 已删除 {deleted_count} 个用户的会员资格。")


async def vip_process(update: Update) -> None:
    text = update.message.text or ""

    # 按中英文逗号/空格分割
    uuid_list = [x.strip() for x in re.split(r"[,，\s]+", text) if x.strip()]

    if not validate_uuid_list(uuid_list):
        await update.message.reply_text("❌ 无效的 UUID 格式，请检查输入。")
        return

    async with async_session() as session:
        result = await process_memberships_by_uuids(session, uuid_list)

        if len(result) == 0:
            added = 0
            renewed = 0
        else:
            added = result["added"]
            renewed = result["renewed"]

        await update.message.reply_text(f"✅ 新增会员 {added} 个，续费会员 {renewed} 个。")


async def check_membership_info(
    query, context: ContextTypes.DEFAULT_TYPE, page=1, page_size=1
):
    await query.answer()

    async with async_session() as session:
        members = await check_vip_status(session)

    total = len(members)
    if total == 0:
        return await query.message.edit_text("❌ 当前没有会员记录。")

    start = (page - 1) * page_size
    end = start + page_size
    sliced = members[start:end]

    lines = [
        f"📋 <b>会员列表（第 {page} 页，共 {((total - 1) // page_size) + 1} 页）</b>\n"
    ]
    for m in sliced:
        end_time = m.end_time.strftime("%Y-%m-%d %H:%M")
        start_time = m.start_time.strftime("%Y-%m-%d %H:%M")
        status = "✅ 正常" if not m.is_banned else "⛔ 封禁"
        lines.append(
            f"🆔 <code>{m.user_id}</code>\n"
            f"📦 来源：{m.source} | 状态：{status}\n"
            f"📅 {start_time} → {end_time}\n"
        )

    keyborads = []
    if total > page_size:
        ll = build_pagination_keyboard("page_vip_db_sear", page, page_size, total)
        keyborads.append(ll)
    keyborads.append(VIP_BACK_MAN_THIRD)
    reply_markup = InlineKeyboardMarkup(keyborads)

    await query.message.edit_text(
        "\n".join(lines),
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup,
    )
