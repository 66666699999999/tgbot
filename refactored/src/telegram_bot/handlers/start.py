from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.ext import CommandHandler, ContextTypes

from telegram_bot.localization.i18n import I18n


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = context.user_data.get("lang", user_id)

    # 底部自定义菜单（ReplyKeyboard）
    reply_keyboard = [
        [I18n.t(lang, "menu.subscribe"), I18n.t(lang, "menu.account")],
        [I18n.t(lang, "menu.join_group"), I18n.t(lang, "menu.support")],
    ]
    reply_markup = ReplyKeyboardMarkup(
        reply_keyboard, resize_keyboard=True, one_time_keyboard=False
    )

    if update.message:
        await update.message.reply_text(
            text=I18n.t(lang, "general.welcome"), reply_markup=reply_markup
        )
    elif update.callback_query:
        await update.callback_query.message.reply_text(
            text=I18n.t(lang, "general.welcome"), reply_markup=reply_markup
        )


def register(app):
    app.add_handler(CommandHandler("start", start))
