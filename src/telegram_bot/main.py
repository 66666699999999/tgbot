import asyncio
import inspect
import logging
import os
import sys
import traceback

import pysqlite3

sys.modules["sqlite3"] = pysqlite3
from telegram.ext import ApplicationBuilder
from telethon import TelegramClient

from telegram_bot.config import SESSION_FILE
from telegram_bot.database.db import init_db
from telegram_bot.handlers import (
    account,
    join_group,
    language,
    manager,
    menu_commands,
    menu_router,
    start,
    subscription,
    support,
)
from telegram_bot.localization.i18n import I18n
from telegram_bot.scheduler.jobs import setup_scheduler
from telegram_bot.utils.logger import setup_logger
from telegram_bot.utils.speed import rate_limit_wrapper
#asyncio.get_event_loop().set_debug(True)
# logger = setup_logger(__name__)
#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(level=logging.INFO)
I18n.load_locales()
API_ID = os.environ.get("API_ID")
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELETHON_SESSION = SESSION_FILE
client = TelegramClient(TELETHON_SESSION, API_ID, API_HASH)


def wrap_all_han(application):
    for handler in application.handlers[0]:
        o_call = handler.callback
        if inspect.iscoroutinefunction(o_call):
            handler.callback = rate_limit_wrapper(o_call)


async def on_startup(application):
    await init_db()
    await menu_commands.setup_commands(application)
    await client.start()
    application.bot_data["client"] = client
    # logger.info("Telethon 客户端已启动")
    await setup_scheduler(application)


async def on_shutdown(application):
    await client.disconnect()
    # logger.info("Telethon 客户端已断开")


def main():
    try:
        application = (
            ApplicationBuilder()
            .token(BOT_TOKEN)
            .post_init(on_startup)
            .post_shutdown(on_shutdown)
            .build()
        )

        # 注册模块
        modules = [
            start,
            subscription,
            language,
            join_group,
            account,
            menu_router,
            support,
            manager,
        ]
        for module in modules:
            module.register(application)

        wrap_all_han(application)

        # logger.info("🤖 Bot 启动中...")
        application.run_polling()
        # logger.info("✅ Bot 已正常退出")

    except Exception as e:
        print(e)
        # logger.error("启动时出错:\n%s\n%s", e, traceback.format_exc())
        # logger.error(e)


if __name__ == "__main__":
    main()
