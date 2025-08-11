from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from telegram_bot.handlers.start import start
from telegram_bot.localization.i18n import I18n
from telegram_bot.user_data_store import get_language, set_language


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_language(update.effective_user.id)

    keyboard = [
        [
            InlineKeyboardButton("🇨🇳 中文", callback_data="lang_zh"),
            InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        I18n.t(lang, "general.choose_language"), reply_markup=reply_markup
    )


async def handle_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if query.data.startswith("lang_"):
        lang_code = query.data.split("_")[1]
        set_language(user_id, lang_code)
        context.user_data["lang"] = lang_code

        await query.edit_message_text(I18n.t(lang_code, "general.language_set"))
        await start(update, context)


def register(app):
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CallbackQueryHandler(handle_language_callback, pattern="^lang_"))
