import json
import os
from functools import lru_cache

from telegram import InlineKeyboardButton

from telegram_bot.localization.i18n import I18n

from ..config import JSON_DIR


@lru_cache()
def load_plan_info():
    path = os.path.join(JSON_DIR, "subscription_plans.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# 缓存订阅计划按钮
@lru_cache(maxsize=4)
def get_subscription_buttons():
    plans = load_plan_info()
    buttons = []
    for key, val in plans.items():
        title = val["title"]
        buttons.append([InlineKeyboardButton(title, callback_data=key)])
    return buttons


# 缓存支付方式按钮
PAYMENT_KEYBOARD = [
    [
        InlineKeyboardButton("USDT (TRC20)", callback_data="pay_trc20"),
        InlineKeyboardButton("USDT (TON)", callback_data="pay_ton"),
    ]
]


MANAGER_FIRST_MENU = [
    [InlineKeyboardButton("会员进频道状况", callback_data="man_channel")],
    [InlineKeyboardButton("会员管理", callback_data="man_vip")],
    [InlineKeyboardButton("机器人管理", callback_data="man_bot")],
]

MANAGER_HANDLE_USER_DETAIL_BUTTON = [
    [
        InlineKeyboardButton(
            "📂 输入用户 ID 查看明细", callback_data="group_detail_input"
        )
    ]
]


MANAGER_BACK_MENU_FIRST = [
    InlineKeyboardButton("🔙 返回上一级", callback_data="menu_jump_first")
]
BOT_BACK_MENU_SECOND = [
    InlineKeyboardButton("🔙 返回上一级", callback_data="menu_jump_second")
]
BOT_BACK_MENU_THIRD = [
    InlineKeyboardButton("🔙 返回上一级", callback_data="bot_menu_jump_third")
]
BOT_BACK_MAN_THIRD = [
    InlineKeyboardButton("🔙 返回上一级", callback_data="bot_man_jump_third")
]
VIP_BACK_MAN_THIRD = [
    InlineKeyboardButton("🔙 返回上一级", callback_data="menu_vip_man_jump_third")
]


VIP_SELECT_BUTTON = [
    [
        InlineKeyboardButton("查看数据库的会员", callback_data="vip_check"),
    ],
    [
        InlineKeyboardButton("开通会员", callback_data="vip_open"),
    ],
    [
        InlineKeyboardButton("取消会员", callback_data="vip_kick"),
    ],
    MANAGER_BACK_MENU_FIRST,
]

BOT_SELECT_BUTTON = [
    [InlineKeyboardButton("频道配置", callback_data="bot_chan_set")],
    [InlineKeyboardButton("管理员配置", callback_data="bot_man_vip_set")],
    [InlineKeyboardButton("设置踢人频率", callback_data="bot_kickSet")],
    [InlineKeyboardButton("设置踢后返回间隔", callback_data="bot_kickBack")],
    MANAGER_BACK_MENU_FIRST,
]


BOT_SELECT_CHANNEL = [
    [InlineKeyboardButton("频道添加", callback_data="bot_join_man")],
    [InlineKeyboardButton("查看数据库的频道", callback_data="bot_join_db_sear")],
    BOT_BACK_MENU_SECOND,
]


BOT_DB_SELECT = [
    [InlineKeyboardButton("➖ 删除频道", callback_data="bot_join_delete")],
    BOT_BACK_MENU_THIRD,
]


BOT_CHANNEL_CONTROL = [
    [InlineKeyboardButton("📥 添加公共频道进数据库", callback_data="bot_join_db_pub")],
    [InlineKeyboardButton("📥 添加VIP频道进数据库", callback_data="bot_join_db_pri")],
    BOT_BACK_MENU_THIRD,
]


MAN_SET_BUTTON = [
    [
        InlineKeyboardButton("添加管理", callback_data="bot_man_vip_add"),
    ],
    [
        InlineKeyboardButton("删除管理", callback_data="bot_man_vip_delete"),
    ],
    [
        InlineKeyboardButton("查看管理", callback_data="bot_man_vip_check"),
    ],
    BOT_BACK_MENU_SECOND,
]
