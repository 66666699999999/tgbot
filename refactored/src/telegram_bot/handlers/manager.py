from copy import deepcopy

from telegram import ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from telegram_bot.database.crud import list_admins
from telegram_bot.database.db import async_session
from telegram_bot.handlers.man.man_bot import (
    bot_man_chan,
    bot_man_set,
    bot_page,
    bot_router,
    channel_man,
    handle_manager_bot,
    list_admins_handler,
    show_db_channel,
)
from telegram_bot.handlers.man.man_handler import (
    get_common_group_stats,
    group_detail_input,
    hand_page,
)
from telegram_bot.handlers.man.man_vip import (
    check_membership_info,
    handle_man_cha_vip,
    handle_manager_vip,
    vip_page,
)

from .button import MANAGER_FIRST_MENU



async def manager_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id

    # 获取管理员列表（数据库中查）
    async with async_session() as session:
        admins = await list_admins(session)
        admin_ids = {admin["user_id"] for admin in admins}

    if user_id not in admin_ids:
        return

    # 是管理员，显示管理菜单
    markup = InlineKeyboardMarkup(deepcopy(MANAGER_FIRST_MENU))

    if update.message:
        await update.message.reply_text(text="请选择管理功能", reply_markup=markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            text="请选择管理功能", reply_markup=markup
        )


ACTION_DISPATCH = {
    "vip_check": check_membership_info,
    "vip_open": handle_man_cha_vip,
    "vip_kick": handle_man_cha_vip,
    "bot_chan_set": bot_man_chan,
    "bot_menu_jump_third": bot_man_chan,
    "bot_kickSet": bot_router,
    "bot_kickBack": bot_router,
    "bot_join_man": channel_man,
    "bot_join_db_pub": bot_router,
    "bot_join_db_pri": bot_router,
    "bot_join_db_sear": show_db_channel,
    "bot_join_delete": bot_router,
    "bot_join_add": bot_router,
    "bot_man_vip_set": bot_man_set,
    "bot_man_vip_check": list_admins_handler,
    "bot_man_vip_add": bot_router,
    "bot_man_vip_delete": bot_router,
    "bot_man_jump_third": bot_man_set,
}


async def handle_manager_actions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    action = ACTION_DISPATCH.get(data)
    if action:
        await action(query, context)
    else:
        await query.edit_message_text("⚠️ 未知操作")


def register(application):
    application.add_handler(CommandHandler("manager", manager_group))
    application.add_handler(
        CallbackQueryHandler(get_common_group_stats, pattern="^man_channel")
    )
    application.add_handler(
        CallbackQueryHandler(handle_manager_vip, pattern="^man_vip")
    )
    application.add_handler(
        CallbackQueryHandler(handle_manager_bot, pattern="^man_bot")
    )
    application.add_handler(
        CallbackQueryHandler(
            handle_manager_actions, pattern="^(sear_|vip_|bot_|manager_back)"
        )
    )
    application.add_handler(
        CallbackQueryHandler(group_detail_input, pattern="^group_detail_input$")
    )
    application.add_handler(
        CallbackQueryHandler(bot_page, pattern=r"^page_bot_.*_(prev|next)_\d+$")
    )
    application.add_handler(
        CallbackQueryHandler(vip_page, pattern=r"^page_vip_.*_(prev|next)_\d+$")
    )
    application.add_handler(
        CallbackQueryHandler(hand_page, pattern=r"^page_han_.*_(prev|next)_\d+$")
    )
    application.add_handler(
        CallbackQueryHandler(manager_group, pattern="^menu_jump_first$")
    )
    application.add_handler(
        CallbackQueryHandler(handle_manager_bot, pattern="^menu_jump_second")
    )
    application.add_handler(
        CallbackQueryHandler(handle_manager_vip, pattern="^menu_vip_man_jump_third")
    )
