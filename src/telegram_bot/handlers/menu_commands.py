from telegram import BotCommand, MenuButtonCommands


async def setup_commands(application):
    await application.bot.set_my_commands(
        [
            BotCommand("start", "开始使用 bot"),
            BotCommand("subscribe", "购买订阅"),
            BotCommand("account", "查看账户信息"),
            BotCommand("manager", "群组管理"),
            BotCommand("language", "切换语言"),
        ]
    )

    await application.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
