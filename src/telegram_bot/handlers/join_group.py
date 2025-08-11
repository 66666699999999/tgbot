from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from telegram_bot.database.crud import get_user_channels
from telegram_bot.database.db import async_session_decorator
from telegram_bot.localization.i18n import I18n

@async_session_decorator
async def join_group(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    user_id = update.effective_user.id
    lang = context.user_data.get("lang", user_id)


    # 获取用户关联的频道 URL 列表
    channel_urls = await get_user_channels(session, user_id)

    if len(channel_urls) == 0:
        return

    # 构建频道列表文本
    channels_text = []
    for url in channel_urls:
        channels_text.append(f"• [{url}]({url})")  # 使用 Markdown 格式加链接

    prompt = I18n.t(lang, "group.prompt")
    message_text = f"{prompt}\n\n" + "\n".join(channels_text)

    if update.message:
        await update.message.reply_text(
            message_text, parse_mode="Markdown", disable_web_page_preview=True
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            message_text, parse_mode="Markdown", disable_web_page_preview=True
        )


def register(application):
    application.add_handler(CommandHandler("join", join_group))
