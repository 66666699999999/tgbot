import sys

import pysqlite3

sys.modules["sqlite3"] = pysqlite3
import asyncio
from datetime import datetime

import aiosqlite


async def test_upsert():
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS upsert_test (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)
        await db.commit()

        # 插入新记录
        await db.execute(
            """
        INSERT INTO upsert_test (id, name, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            updated_at = excluded.updated_at
        """,
            (1, "Alice", datetime.now().isoformat()),
        )
        await db.commit()

        # 再插入相同主键，模拟冲突更新
        await db.execute(
            """
        INSERT INTO upsert_test (id, name, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            updated_at = excluded.updated_at
        """,
            (1, "Alice_Updated", datetime.now().isoformat()),
        )
        await db.commit()

        async with db.execute("SELECT * FROM upsert_test") as cursor:
            rows = await cursor.fetchall()
            print("🟢 UPSERT 测试结果：")
            for row in rows:
                print(row)


asyncio.run(test_upsert())
