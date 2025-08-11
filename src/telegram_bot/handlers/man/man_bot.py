import re
from copy import deepcopy
from math import ceil

from telegram import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes
from telethon.errors import (
    ChatAdminRequiredError,
    InviteHashInvalidError,
    UserAlreadyParticipantError,
    UsernameNotOccupiedError,
)
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.tl.types import (
    Channel,
    ChannelParticipantsAdmins,
    Chat,
    PeerChannel,
    User,
)

from telegram_bot.database.crud import (
    add_admin,
    add_channel_config,
    delete_admin,
    delete_channel_config,
    get_channel_by_url,
    list_admins,
    list_channel_configs,
    set_or_get_kick_config,
)
from telegram_bot.database.db import async_session
from telegram_bot.handlers.states import ChannelInfo, ManagerState

from ..button import (
    BOT_BACK_MAN_THIRD,
    BOT_CHANNEL_CONTROL,
    BOT_DB_SELECT,
    BOT_SELECT_BUTTON,
    BOT_SELECT_CHANNEL,
    MAN_SET_BUTTON,
)

# 映射结构（按钮 data 到提示信息和状态）
bot_router_handlers = {
    "bot_join_db_pub": (
        "请输入要添加进数据库的公共群组/频道链接，格式为（支持批量导入，英文逗号分割）：\nhttps://t.me/1234567890,https://t.me/1234567890",
        ManagerState.AWAITING_JOIN_DB_PUB,
    ),
    "bot_join_db_pri": (
        "请输入要添加进数据库的VIP群组/频道链接，格式为（支持批量导入，英文逗号分割）：\nhttps://t.me/1234567890,https://t.me/1234567890",
        ManagerState.AWAITING_JOIN_DB_PRI,
    ),
    "bot_join_add": (
        "请输入要进入的群组/频道 URL，格式为（支持批量导入，英文逗号分割）：\nhttps://t.me/1234567890,https://t.me/1234567890\n不支持：\n@biadhi",
        ManagerState.AWAITING_JOIN_ADD,
    ),
    "bot_join_delete": (
        "请输入要删除的群组/频道 URL，格式如（支持批量删除，英文逗号分割）：\nhttps://t.me/1234567890,https://t.me/1234567890",
        ManagerState.AWAITING_JOIN_DELETE,
    ),
    "bot_kickSet": (
        "请输入设置的踢人频率，单位为秒",
        ManagerState.AWAITING_KICK_SET,
    ),
    "bot_kickBack": (
        "请输入设置会员被提后的返回时间，单位为秒",
        ManagerState.AWAITING_KICK_BACK,
    ),
    "bot_man_vip_add": (
        "请输入要设置为管理员的 ID，示例（支持批量操作英文逗号分割）：\n123456,15353",
        ManagerState.AWAITING_MAN_ADD,  # 你可能需要区分不同操作，这里目前只有一个 key
    ),
    "bot_man_vip_delete": (
        "请输入要删除的管理员的 ID，示例（支持批量操作英文逗号分割）：\n123456,15353",
        ManagerState.AWAITING_MAN_DELETE,  # 你可能需要区分不同操作，这里目前只有一个 key
    ),
}


async def bot_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    if page_key == "page_bot_admin_list":
        await list_admins_handler(update, context, page=page)
    elif page_key == "page_bot_db_chan":
        await show_db_channel(query, context, page=page)
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

    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton("◀️", callback_data=f"{prefix}_prev_{page - 1}")
        )
    if page * page_size < total_items:
        nav_buttons.append(
            InlineKeyboardButton("▶️", callback_data=f"{prefix}_next_{page + 1}")
        )

    return nav_buttons


async def handle_manager_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    selected_plan = query.data
    context.user_data["selected_plan"] = selected_plan

    payment_keyboard = deepcopy(BOT_SELECT_BUTTON)

    await query.edit_message_text(
        text="请选择", reply_markup=InlineKeyboardMarkup(payment_keyboard)
    )


async def bot_man_chan(query, context: ContextTypes.DEFAULT_TYPE):
    await query.answer()  # 尽快响应 Telegram

    selected_plan = query.data
    context.user_data["selected_plan"] = selected_plan

    keyboard = deepcopy(BOT_SELECT_CHANNEL)

    await query.edit_message_text(
        text="📂 请选择你要执行的操作：", reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def get_my_channels(context):
    client = context.bot_data.get("client")

    dialogs = await client.get_dialogs()

    channels = []
    for dialog in dialogs:
        entity = dialog.entity
        if isinstance(entity, Channel):
            if entity.megagroup or entity.broadcast:  # 仅超级群组或频道
                channels.append(
                    ChannelInfo(
                        id=entity.id,
                        title=entity.title,
                        url=f"https://t.me/c/{entity.id}"
                        if entity.megagroup
                        else f"https://t.me/{entity.username}"
                        if entity.username
                        else None,
                    )
                )
    return channels


async def show_db_channel(query, context, page: int = 1, page_size: int = 10):
    async with async_session() as session:
        configs = await list_channel_configs(session)

    print(configs)
    total = len(configs)
    start = (page - 1) * page_size
    end = start + page_size
    page_configs = configs[start:end]

    lines = []
    if total == 0:
        lines.append("📭 当前数据库中没有已保存的频道")
    else:
        lines.append(
            f"*📋 数据库频道列表（第 {page} 页，共 {((total - 1) // page_size) + 1} 页）：*"
        )
        lines.append("")
        for cfg in page_configs:
            url = cfg.channel_url
            line = f"- `{url}`"
            lines.append(line)

    keyboard = deepcopy(BOT_DB_SELECT)

    if total > page_size:
        print(page, page_size, total)
        pagination_buttons = build_pagination_keyboard(
            "page_bot_db_chan", page, page_size, total
        )
        keyboard.append(pagination_buttons)

    await query.edit_message_text(
        text="\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def channel_man(query, context):
    # 主操作按钮
    main_buttons = deepcopy(BOT_CHANNEL_CONTROL)

    await query.edit_message_text(
        text="请选择",
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(main_buttons),
    )


async def bot_join_delete(update: Update):
    raw_text = update.message.text.strip()

    # 支持逗号或分号分割
    entries = [x.strip() for x in raw_text.replace(";", ",").split(",") if x.strip()]

    if not entries:
        await update.message.reply_text(
            "❌ 输入格式有误，请提供频道链接（用 , 或 ; 分割）"
        )
        return ConversationHandler.END

    async with async_session() as session:
        deleted_titles = []

        for url in entries:
            channel = await get_channel_by_url(session, url)
            if channel:
                success = await delete_channel_config(session, channel_url=url)
                if success:
                    deleted_titles.append(f"🗑 删除《{channel.channel_url}》")
                else:
                    deleted_titles.append(f"⚠️ 删除失败：{url}")
            else:
                deleted_titles.append(f"⚠️ 未找到频道链接：{url}")

        await update.message.reply_text(
            "📦 删除结果：\n\n" + "\n".join(deleted_titles[:30])
        )

    return


# Bot加入群组
URL_PATTERN = re.compile(r"(https://t.me/)?([a-zA-Z0-9_]{5,})")


async def bot_join_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return await message.reply_text(
            "❌ 请直接发送频道链接（支持公开/私有链接），一行一个或用分号分隔"
        )

    raw_text = message.text.strip()
    entries = [e.strip() for e in raw_text.replace("\n", ";").split(";") if e.strip()]

    client = context.bot_data.get("client")
    if not client:
        return await message.reply_text("❌ 未配置 Telethon 客户端，请联系管理员")

    me = await client.get_me()
    await message.reply_text(
        f"当前登录用户：{me.username or me.first_name}（ID: {me.id}）"
    )

    results = []
    for entry in entries:
        try:
            if "t.me/+" in entry or "t.me/joinchat/" in entry:
                invite_hash = entry.split("/")[-1]
                re = await client(ImportChatInviteRequest(invite_hash))
                results.append(f"✅ 加入成功（私有）：{entry}")
            else:
                username = (
                    entry.replace("https://t.me/", "").replace("t.me/", "").strip("/")
                )
                await client(JoinChannelRequest(username))
                results.append(f"✅ 加入成功：{entry}")

                # 检查是否真的加入成功
                group = await client.get_entity(username)
                participants = await client.get_participants(group)
                if any(p.id == me.id for p in participants):
                    results.append("🔍 验证通过：已在群中")
                else:
                    results.append("⚠️ 加入成功但无法在群成员中找到（可能被隐形）")
        except UserAlreadyParticipantError:
            results.append(f"⚠️ 已加入：{entry}")
        except ChatAdminRequiredError:
            results.append(f"❌ 无权限加入：{entry}")
        except InviteHashInvalidError:
            results.append(f"❌ 无效邀请链接：{entry}")
        except Exception as e:
            results.append(f"❌ 加入失败：{entry} -> {e}")

    await message.reply_text("\n".join(results[:30])[:4000])


# 添加频道进数据库
async def bot_join_db(
    update: Update, context: ContextTypes.DEFAULT_TYPE, group_type=None
):
    raw_text = update.message.text.strip()
    entries = raw_text.split(",")

    client = context.bot_data.get("client")

    success = []
    failed = []

    # 自动设置频道类型（是否会员频道）
    if group_type == "pri":
        is_vip_channel = True
    elif group_type == "pub":
        is_vip_channel = False
    else:
        await update.message.reply_text("❌ 参数错误：频道类型未知")
        return

    for item in entries:
        try:
            channel_url = item.strip()
            channel_id = None

            try:
                entity = await client.get_entity(channel_url)
                if isinstance(entity, PeerChannel) or hasattr(entity, "id"):
                    channel_id = entity.id
            except UsernameNotOccupiedError:
                channel_id = None
            except Exception as e:
                logger.info(f"failed get channel id {e}")
                channel_id = None

            # 写入数据库
            async with async_session() as session:
                await add_channel_config(
                    session,
                    channel_id=channel_id,
                    channel_url=channel_url,
                    is_vip_channel=is_vip_channel,
                    bot_joined=False,
                    remark=f"{item.strip()}（{group_type}）",
                )
            success.append(f"{channel_url} ✅ 成功添加")

        except Exception as e:
            failed.append(f"{item} ❌ 错误: {e}")

    result_text = "📥 添加结果：\n\n"
    if success:
        result_text += "\n".join(success) + "\n\n"
    if failed:
        result_text += "⚠️ 以下添加失败：\n" + "\n".join(failed)

    await update.message.reply_text(result_text[:4000])


async def bot_kickSet(update: Update):
    raw_text = update.message.text

    try:
        interval = int(raw_text)
    except ValueError:
        await update.message.reply_text("❌ 无效输入，请输入一个数字（单位：秒）")
        return

    async with async_session() as session:
        config = await set_or_get_kick_config(session, kick_interval_seconds=interval)

    await update.message.reply_text(
        f"✅ 设置成功：\n\n"
        f"踢人频率：{config.kick_interval_seconds} 秒\n"
        f"返回间隔：{config.rejoin_delay_minutes} 秒"
    )


async def bot_kickBack(update: Update):
    raw_text = update.message.text

    # 校验输入
    try:
        delay = int(raw_text.strip())
        if delay <= 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("❌ 无效输入，请输入一个数字（单位：秒）")
        return

    # 更新数据库
    async with async_session() as session:
        config = await set_or_get_kick_config(session, rejoin_delay_minutes=delay)

    # 回复用户
    await update.message.reply_text(
        f"✅ 设置成功：\n\n"
        f"踢人频率：{config.kick_interval_seconds} 秒\n"
        f"返回间隔：{config.rejoin_delay_minutes} 秒"
    )


async def bot_man_set(query, context):
    await query.answer()  # 尽快响应 Telegram

    selected_plan = query.data
    context.user_data["selected_plan"] = selected_plan

    main_buttons = deepcopy(MAN_SET_BUTTON)

    await query.edit_message_text(
        text="请选择",
        reply_markup=InlineKeyboardMarkup(main_buttons),
    )


async def add_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client = context.bot_data.get("client")
    operator_id = update.effective_user.id
    text = update.message.text.strip()
    user_ids = [uid.strip() for uid in text.split(",") if uid.strip().isdigit()]

    if not user_ids:
        await update.message.reply_text("❌ 格式错误")
        return

    level = 1
    success, failed = [], []

    async with async_session() as session:
        for uid in user_ids:
            try:
                user_id = int(uid)

                try:
                    entity = await client.get_entity(user_id)
                    username = entity.username if hasattr(entity, "username") else None
                except Exception:
                    username = None

                remark = f"{user_id} 执行 添加"
                msg = await add_admin(
                    session,
                    operator_id,
                    {
                        "user_id": user_id,
                        "username": username,
                        "level": level,
                        "remark": remark,
                    },
                )
                success.append(f"{user_id} ✅\n\n{msg}")
            except Exception as e:
                failed.append(f"{uid} ❌ ({str(e)})")

    result = "📋 添加结果：\n"
    if success:
        result += "".join(success)
    if failed:
        result += "".join(failed)
    await update.message.reply_text(result)


async def del_admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    operator_id = update.effective_user.id
    text = update.message.text.strip()
    user_ids = [uid.strip() for uid in text.split(",") if uid.strip().isdigit()]

    if not user_ids:
        await update.message.reply_text("❌ 格式错误")
        return

    success, failed = [], []

    async with async_session() as session:
        for uid in user_ids:
            try:
                target_user_id = int(uid)
                msg = await delete_admin(session, operator_id, target_user_id)
                success.append(f"{uid} ✅")
            except Exception as e:
                failed.append(f"{uid} ❌ ({str(e)})")

    result = "📋 删除结果：\n"
    if success:
        result += "\n✔️ 成功：\n" + "\n".join(success)
    if failed:
        result += "\n\n❌ 失败：\n" + "\n".join(failed)
    await update.message.reply_text(result)


async def list_admins_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    page: int = 1,
    page_size: int = 5,
):
    async with async_session() as session:
        admin_list = await list_admins(session)

    if not admin_list:
        await update.message.reply_text("暂无管理员。")
        return

    total = len(admin_list)
    max_page = ceil(total / page_size)

    # 确保页码合法
    page = max(1, min(page, max_page))
    start = (page - 1) * page_size
    end = start + page_size

    current_page_list = admin_list[start:end]

    lines = [
        f"👤 {'@' + a['username'] if a['username'] else a['user_id']}"
        + f"\n🆔 `{a['user_id']}`\n"
        for a in current_page_list
    ]

    keyboard = []
    keyboard.append(
        build_pagination_keyboard("page_bot_admin_list", page, page_size, total)
    )
    keyboard.append(BOT_BACK_MAN_THIRD)

    text = f"📋 管理员列表（第 {page}/{max_page} 页）：\n\n" + "\n\n".join(lines)

    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN,
        )
    elif update.callback_query:
        await update.callback_query.message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN,
        )


async def ask_input_and_set_state(query, context, prompt: str, state):
    await query.message.reply_text(prompt)
    context.user_data["state"] = state


# 主处理函数
async def bot_router(query, context):
    await query.answer()
    data = query.data

    if data in bot_router_handlers:
        prompt, state = bot_router_handlers[data]
        await ask_input_and_set_state(query, context, prompt, state)
    else:
        await query.message.reply_text("⚠️ 无效操作")
