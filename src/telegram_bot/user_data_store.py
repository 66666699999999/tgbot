# 可以换成真实数据库
user_language = {}


def set_language(user_id, lang):
    user_language[user_id] = lang


def get_language(user_id):
    return user_language.get(user_id, "en")  # 默认英文
