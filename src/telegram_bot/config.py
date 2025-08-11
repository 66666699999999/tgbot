import os
import sys

"""
# 打包环境路径获取
def get_resource_path(relative_path):
    base_path = getattr(sys, '_MEIPASS', os.path.abspath("."))
    return os.path.join(base_path, relative_path)

# 其他路径基于 BASE_DIR 构建
JSON_DIR = get_resource_path("locales")
DB_PATH = get_resource_path("bot.db")
SESSION_FILE = get_resource_path("test_session.session")
"""
# 测试环境

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, "../../"))
JSON_DIR = os.path.join(PROJECT_ROOT, "locales")
DB_PATH = os.path.join(PROJECT_ROOT, "bot.db")
SESSION_FILE = os.path.join(PROJECT_ROOT, "test_session.session")
