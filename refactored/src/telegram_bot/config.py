import os
import sys
from dataclasses import dataclass


@dataclass
class Config:
    def __init__(self):
        # 确定项目根目录
        self.BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        self.PROJECT_ROOT = os.path.abspath(os.path.join(self.BASE_DIR, "../../.."))
        
        # 配置文件路径
        self.JSON_DIR = os.path.join(self.PROJECT_ROOT, "locales")
        
        # 数据库路径
        self.DB_PATH = os.path.join(self.PROJECT_ROOT, "bot.db")
        
        # 会话文件路径
        self.SESSION_FILE = os.path.join(self.PROJECT_ROOT, "test_session.session")
        
        # 从环境变量加载密钥
        self.API_ID = os.environ.get("API_ID")
        self.API_HASH = os.environ.get("API_HASH")
        self.BOT_TOKEN = os.environ.get("BOT_TOKEN")

    def validate(self):
        """验证配置是否完整"""
        required_env_vars = ["API_ID", "API_HASH", "BOT_TOKEN"]
        missing_vars = [var for var in required_env_vars if not getattr(self, var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        return True


# 创建配置实例
config = Config()