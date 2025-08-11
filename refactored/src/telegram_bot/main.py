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

from .config import config
from .database import db_manager
from .handlers import (
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
from .localization.i18n import I18n
from .scheduler.jobs import setup_scheduler
from .utils.logger import setup_logger
from .utils.speed import rate_limit_wrapper

# 初始化日志
# logger = setup_logger(__name__)
logging.basicConfig(level=logging.INFO)

# 加载本地化
I18n.load_locales()

# 从配置中获取环境变量
API_ID = config.API_ID
API_HASH = config.API_HASH
BOT_TOKEN = config.BOT_TOKEN
TELETHON_SESSION = config.SESSION_FILE

# 创建 Telethon 客户端
client = TelegramClient(TELETHON_SESSION, API_ID, API_HASH)


def wrap_all_han(application):
    for handler in application.handlers[0]:
        o_call = handler.callback
        if inspect.iscoroutinefunction(o_call):
            handler.callback = rate_limit_wrapper(o_call)


async def on_startup(application):
    # 初始化数据库
    await db_manager.init_db()
    
    # 设置菜单命令
    await menu_commands.setup_commands(application)
    
    # 启动 Telethon 客户端
    await client.start()
    application.bot_data["client"] = client
    
    # 设置调度器
    await setup_scheduler(application)


async def on_shutdown(application):
    # 断开 Telethon 客户端
    await client.disconnect()


class BotApplication:
    def __init__(self):
        self.application = None

    def initialize(self):
        try:
            # 验证配置
            config.validate()
            
            # 创建应用
            self.application = (
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
                module.register(self.application)

            # 包装所有处理器
            wrap_all_han(self.application)

            return True
        except Exception as e:
            print(e)
            traceback.print_exc()
            return False

    def run(self):
        if not self.application:
            if not self.initialize():
                print("应用初始化失败")
                return

        # 启动机器人
        print("🤖 Bot 启动中...")
        self.application.run_polling()
        print("✅ Bot 已正常退出")


if __name__ == "__main__":
    bot_app = BotApplication()
    bot_app.run()