import time
from collections import defaultdict


class TokenBucket:
    def __init__(self, rate, capacity):
        self.rate = rate  # 每秒补充多少令牌
        self.capacity = capacity  # 桶最大容量
        self.tokens = capacity  # 当前令牌数
        self.timestamp = time.time()

    def consume(self, tokens=1):
        now = time.time()
        elapsed = now - self.timestamp
        self.timestamp = now

        # 补充令牌
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True  # 允许请求
        else:
            return False  # 拒绝请求


# 为每个用户维护一个令牌桶
USER_BUCKETS = defaultdict(lambda: TokenBucket(rate=1, capacity=5))


def rate_limit_wrapper(handler_func):
    async def wrapped(update, context):
        user_id = update.effective_user.id if update.effective_user else None

        if user_id:
            bucket = USER_BUCKETS[user_id]
            if not bucket.consume():
                if update.message:
                    await update.message.reply_text("请求太快了，请稍后再试。")
                return

        await handler_func(update, context)

    return wrapped
