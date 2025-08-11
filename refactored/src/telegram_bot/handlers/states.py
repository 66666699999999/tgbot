# telegram_bot/handlers/states.py

# 订阅流程相关状态
CHOOSE_PLAN, CHOOSE_PAYMENT, CONFIRM_PAYMENT = range(3)


# 管理面板相关状态
class ManagerState:
    AWAITING_USER_ID = "awaiting_user_id"
    AWAITING_VIP_OPEN = "awaiting_vip_open"
    AWAITING_VIP_RENEW = "awaiting_vip_renew"
    AWAITING_VIP_DELETE = "awaiting_vip_delete"
    AWAITING_SEAR_SINGLE = "awaiting_sear_single"
    AWAITING_JOIN_DB_PUB = "awaiting_join_db_pub"
    AWAITING_JOIN_DB_PRI = "awaiting_join_db_pri"
    AWAITING_JOIN_ADD = "awaiting_join_add"
    AWAITING_JOIN_DELETE = "awaiting_join_delete"
    AWAITING_KICK_SET = "awaiting_kick_set"
    AWAITING_KICK_BACK = "awaiting_kick_back"
    AWAITING_DETAIL_ID = "awaiting_detail_id"
    AWAITING_MAN_ADD = "awaiting_man_add"
    AWAITING_MAN_DELETE = "awaiting_man_delete"


class ChannelInfo:
    def __init__(self, id, title, url):
        self.id = id
        self.title = title
        self.channel_url = url
