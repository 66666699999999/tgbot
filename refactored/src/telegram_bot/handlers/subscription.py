# src/telegram_bot/handlers/subscription.py
import json
import os
import uuid
from copy import deepcopy
from functools import lru_cache

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from telegram_bot.database.crud import add_or_update_subscription, can_user_resubscribe
from telegram_bot.database.db import async_session_decorator
from telegram_bot.localization.i18n import I18n

from ..config import JSON_DIR
from .button import PAYMENT_KEYBOARD, get_subscription_buttons
from .start import start


@lru_cache()
def load_plan_info():
    path = os.path.join(JSON_DIR, "subscription_plans.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


PAYMENT_METHOD_NAMES = {
    "pay_trc20": {"name": "USDT", "network": "TRC20"},
    "pay_ton": {"name": "USDT", "network": "TON"},
}

ADDRESS = {
    "TRC20": os.environ.get("ADDRESS_TRC20"),
    "TON": os.environ.get("ADDRESS_TON"),
}


def clear_subscription_context(context):
    keys_to_pop = [
        "invoice_id",
        "selected_plan",
        "network",
        "amount",
        "payment_address",
    ]
    for key in keys_to_pop:
        context.user_data.pop(key, None)


async def handle_payment_method_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang") or "zh"
    selected_plan = context.user_data.get("selected_plan")

    plans = load_plan_info()
    if not selected_plan or selected_plan not in plans:
        await query.edit_message_text(I18n.t(lang, "subscribe.error.no_plan"))
        return

    plan_info = plans.get(selected_plan)
    payment = PAYMENT_METHOD_NAMES.get(query.data)
    if not payment:
        await query.edit_message_text("无效的支付方式")
        return

    network = payment["network"]
    address = ADDRESS.get(network)

    # 更新上下文信息
    context.user_data.update(
        {
            "payment_address": address,
            "network": network,
            "invoice_id": str(uuid.uuid4()),
            "amount": plan_info["amount"],
        }
    )

    text = I18n.t(
        lang,
        "subscribe.payment_detail",
        amount=plan_info["amount"],
        network=network,
        uuid=context.user_data["invoice_id"],
        address=address,
    )

    confirm_button = [
        [
            InlineKeyboardButton(
                I18n.t(lang, "subscribe.payment_info"), callback_data="confirm_pay"
            )
        ]
    ]
    await query.edit_message_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(confirm_button),
        parse_mode=ParseMode.MARKDOWN,
    )


async def handle_subscription_choice(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query
    await query.answer()
    lang = context.user_data.get("lang") or "zh"

    selected_plan = query.data
    plans = load_plan_info()
    if selected_plan not in plans:
        await query.edit_message_text(I18n.t(lang, "subscribe.error.no_plan"))
        return

    context.user_data["selected_plan"] = selected_plan
    await query.edit_message_text(
        text=I18n.t(lang, "subscribe.payment_method"),
        reply_markup=InlineKeyboardMarkup(deepcopy(PAYMENT_KEYBOARD)),
    )

@async_session_decorator
async def confirm_payment_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    query = update.callback_query
    await query.answer("✅ 支付信息已确认")
    user_id = query.from_user.id

    required_fields = ["selected_plan", "invoice_id", "payment_address", "network"]
    if not all(field in context.user_data for field in required_fields):
        await query.edit_message_text("支付信息不完整，请重新订阅。")
        return

    plans = load_plan_info()
    plan_info = plans.get(context.user_data["selected_plan"])
    if not plan_info:
        await query.edit_message_text("无效的订阅计划")
        return


    await add_or_update_subscription(
        session,
        user_id,
        plan_info["amount"],
        plan_info["duration_days"] * 24,
        context.user_data["invoice_id"],
        context.user_data["network"],
        context.user_data["payment_address"],
        "pending",
    )

    clear_subscription_context(context)
    await start(update, context)

@async_session_decorator
async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """触发订阅菜单：命令或文本"""
    user_id = update.effective_user.id
    lang = context.user_data.get("lang") or "zh"

    markup = InlineKeyboardMarkup(get_subscription_buttons())  # ✅ 提前定义

    res = await can_user_resubscribe(session, user_id)
    if res is not True:
        if update.message:
            await update.message.reply_text("您已被 Ban ，请稍后再来")
        elif update.callback_query:
            await update.callback_query.edit_message_text("您已被 Ban ，请稍后再来")
        return

    if "selected_plan" in context.user_data:
        clear_subscription_context(context)

    text = I18n.t(lang, "subscribe.choose_plan")

    if update.message:
        await update.message.reply_text(text, reply_markup=markup)
    elif update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=markup)


def register(application):
    application.add_handler(CommandHandler("subscribe", subscribe))
    application.add_handler(
        CallbackQueryHandler(handle_subscription_choice, pattern="^sub_")
    )
    application.add_handler(
        CallbackQueryHandler(handle_payment_method_choice, pattern="^pay_")
    )
    application.add_handler(
        CallbackQueryHandler(confirm_payment_handler, pattern="^confirm_")
    )
