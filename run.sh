#!/bin/bash

ENV_FILE=".env"

# 加载 .env 文件中的环境变量
export $(grep -v '^#' "$ENV_FILE" | tr -d '\r' | xargs)

# 后台启动脚本
echo "正在后台启动 Telegram Bot..."
uv run src/telegram_bot/main.py
#uv run main.py
