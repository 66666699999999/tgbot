import uuid
from typing import List

from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from telegram_bot.database.db import async_session
from telegram_bot.handlers.man.man_bot import (
    add_admin_handler,
    bot_join_db,
    bot_join_delete,
    bot_join_group,
    bot_kickBack,
    bot_kickSet,
    del_admin_handler,
)
from telegram_bot.handlers.man.man_handler import show_user_group_detail
from telegram_bot.handlers.man.man_vip import vip_delete, vip_process
from telegram_bot.localization.i18n import I18n
from telegram_bot.utils.logger import setup_logger

from .account import account
from .join_group import join_group
from .language import language_command
from .start import start
from .states import ManagerState
from .subscription import subscribe
from .support import call_support

logger = setup_logger(__name__)


async def router(update, context):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    lang = context.user_data.get("lang", user_id)

    if text in [I18n.t(lang, "menu.subscribe"), "subscribe"]:
        await subscribe(update, context)
    elif text in [I18n.t(lang, "menu.account"), "account"]:
        await account(update, context)
    elif text in [I18n.t(lang, "menu.join_group")]:
        await join_group(update, context)
    elif text in [I18n.t(lang, "menu.support")]:
        await call_support(update, context)
    elif text in ["start"]:
        await start(update, context)
    elif text in ["manager"]:
        await manager_group(update, context)
    elif text in ["language"]:
        await language_command(update, context)
    else:
        logger.info("⚠️ 无效菜单选项")


manager_state_handlers = {
    ManagerState.AWAITING_VIP_OPEN: lambda u, c: vip_process(u),
    ManagerState.AWAITING_VIP_DELETE: lambda u, c: vip_delete(u),
    ManagerState.AWAITING_JOIN_DELETE: lambda u, c: bot_join_delete(u),
    ManagerState.AWAITING_JOIN_DB_PUB: lambda u, c: bot_join_db(u, c, "pub"),
    ManagerState.AWAITING_JOIN_DB_PRI: lambda u, c: bot_join_db(u, c, "pri"),
    ManagerState.AWAITING_JOIN_ADD: lambda u, c: bot_join_group(u, c),
    ManagerState.AWAITING_KICK_SET: lambda u, c: bot_kickSet(u),
    ManagerState.AWAITING_KICK_BACK: lambda u, c: bot_kickBack(u),
    ManagerState.AWAITING_DETAIL_ID: lambda u, c: show_user_group_detail(u, c),
    ManagerState.AWAITING_MAN_ADD: lambda u, c: add_admin_handler(u, c),
    ManagerState.AWAITING_MAN_DELETE: lambda u, c: del_admin_handler(u, c),
}


async def handle_reply_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.pop("state", None)

    if state and state in manager_state_handlers:
        handler = manager_state_handlers[state]
        await handler(update, context)
        return
    await router(update, context)


def register(application):
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reply_keyboard)
    )
