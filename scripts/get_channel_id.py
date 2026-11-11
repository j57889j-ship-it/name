"""Print the numeric chat ID of CHANNEL_USERNAME using BOT_TOKEN."""
import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot


async def main() -> None:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    username = os.getenv("CHANNEL_USERNAME", "").strip().lstrip("@")
    if not token or not username:
        raise SystemExit("BOT_TOKEN va CHANNEL_USERNAME .env faylida bo‘lishi kerak")
    bot = Bot(token)
    try:
        chat = await bot.get_chat(f"@{username}")
        print(f"CHANNEL_ID={chat.id}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
