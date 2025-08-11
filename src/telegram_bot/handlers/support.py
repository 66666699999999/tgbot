from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from telegram_bot.localization.i18n import I18n


async def call_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    lang = context.user_data.get("lang", user_id)

    prompt = I18n.t(lang, "support.contact")
    if update.message:
        await update.message.reply_text(prompt)
    elif update.callback_query:
        await update.callback_query.edit_message_text(prompt)


def register(application):
    application.add_handler(CommandHandler("support", call_support))
