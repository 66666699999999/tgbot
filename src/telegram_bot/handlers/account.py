from datetime import datetime, timedelta

import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from telegram_bot.database.crud import get_latest_membership
from telegram_bot.database.db import async_session
from telegram_bot.localization.i18n import I18n


async def account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = context.user_data.get("lang", user_id)

    async with async_session() as session:
        menbership = await get_latest_membership(session, user_id)

    if menbership:
        # 获取时区
        utc_tz = pytz.UTC
        beijing_tz = pytz.timezone("Asia/Shanghai")

        # 确保时间有时区信息
        start_time_utc = utc_tz.localize(menbership.start_time)
        end_time_utc = utc_tz.localize(menbership.end_time)

        # 转换为北京时间
        start_time_beijing = start_time_utc.astimezone(beijing_tz)
        end_time_beijing = end_time_utc.astimezone(beijing_tz)

        # 格式化显示
        signup_date_local = start_time_beijing.strftime("%Y-%m-%d %H:%M:%S %Z")
        sub_end_date_local = end_time_beijing.strftime("%Y-%m-%d %H:%M:%S %Z")

        text = I18n.t(
            lang,
            "account.status",
            user_id=user_id,
            signup_date=f"{signup_date_local}",
            sub_end_date=f"{sub_end_date_local}",
        )
    else:
        text = I18n.t(lang, "account.no_subscription")

    if update.message:
        await update.message.reply_text(text=text)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text=text)


def register(application):
    application.add_handler(CommandHandler("account", account))
