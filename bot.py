import asyncio
import json
import logging
from pathlib import Path

import aiohttp
import feedparser
from aiogram import Bot, Dispatcher, types

# --- Configuration ---
# TELEGRAM_TOKEN must be provided via environment variable in the hosting service
import os
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    raise SystemExit("Please set TELEGRAM_TOKEN environment variable")

DATA_FILE = Path("subscriptions.json")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_SEC", 30*60))  # default 30 minutes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("game_updates_bot")

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher(bot)

# --- Games config ---
games = {
    "cs2": {"type": "steam", "id": 730, "name": "Counter-Strike 2"},
    "dota": {"type": "steam", "id": 570, "name": "Dota 2"},
    "pubg": {"type": "steam", "id": 578080, "name": "PUBG"},
    "fortnite": {"type": "epic", "url": "https://www.fortnite.com/news/feed", "name": "Fortnite"},
    "lol": {"type": "riot", "url": "https://www.leagueoflegends.com/en-us/news/game-updates/feed/", "name": "League of Legends"},
    "valorant": {"type": "riot", "url": "https://playvalorant.com/en-us/news/game-updates/feed/", "name": "Valorant"}
}

# --- Persistence ---
def load_data():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.exception("Failed to read data file, starting fresh: %s", e)
            return {"subscriptions": {}, "last_updates": {}}
    return {"subscriptions": {}, "last_updates": {}}

def save_data(data):
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

data = load_data()

# --- Helpers ---
async def fetch_json(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=20) as resp:
            resp.raise_for_status()
            return await resp.json()

async def check_steam(appid):
    url = f"https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid={appid}&count=1"
    j = await fetch_json(url)
    items = j.get("appnews", {}).get("newsitems", [])
    if not items:
        return None, None
    n = items[0]
    title = n.get("title", "").strip()
    url = n.get("url", "")
    return title, url

async def check_epic(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=20) as resp:
            resp.raise_for_status()
            text = await resp.text()
    feed = feedparser.parse(text)
    if not feed.entries:
        return None, None
    entry = feed.entries[0]
    return entry.get("title", "").strip(), entry.get("link", "")

async def check_riot(url):
    feed = feedparser.parse(url)
    if not feed.entries:
        return None, None
    entry = feed.entries[0]
    return entry.get("title", "").strip(), entry.get("link", "")

async def check_game(key):
    g = games[key]
    try:
        if g["type"] == "steam":
            return await check_steam(g["id"])
        elif g["type"] == "epic":
            return await check_epic(g["url"])
        else:
            return await check_riot(g["url"])
    except Exception as e:
        logger.exception("Error checking %s: %s", key, e)
        return None, None

# --- Bot commands ---
from aiogram.filters import Command

@dp.message(Command(commands=["start"]))
async def cmd_start(message: types.Message):
    await message.answer("Привет! Я уведомляю об обновлениях игр.\nСписок команд:\n/games\n/subscribe <game_key>\n/unsubscribe <game_key>\n/mysubscriptions")

@dp.message(Command(commands=["games"]))
async def cmd_games(message: types.Message):
    lines = ["Доступные игры:"]
    for k, v in games.items():
        lines.append(f"{k} — {v['name']}")
    await message.answer("\n".join(lines))

@dp.message(Command(commands=["subscribe"]))
async def cmd_subscribe(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /subscribe cs2")
        return
    key = args[1].lower()
    if key not in games:
        await message.answer("Неизвестная игра. Список — /games")
        return
    uid = str(message.from_user.id)
    subs = data.setdefault("subscriptions", {})
    user_subs = subs.setdefault(uid, [])
    if key in user_subs:
        await message.answer("Уже подписан.")
        return
    user_subs.append(key)
    save_data(data)
    await message.answer(f"Подписка на {games[key]['name']} оформлена.")

@dp.message(Command(commands=["unsubscribe"]))
async def cmd_unsubscribe(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /unsubscribe cs2")
        return
    key = args[1].lower()
    uid = str(message.from_user.id)
    subs = data.setdefault("subscriptions", {})
    user_subs = subs.get(uid, [])
    if key in user_subs:
        user_subs.remove(key)
        save_data(data)
        await message.answer("Отписка выполнена.")
    else:
        await message.answer("Ты не был подписан на эту игру.")

@dp.message(Command(commands=["mysubscriptions"]))
async def cmd_mysubs(message: types.Message):
    uid = str(message.from_user.id)
    subs = data.get("subscriptions", {}).get(uid, [])
    if not subs:
        await message.answer("У тебя нет подписок.")
        return
    text = "Твои подписки:\n" + "\n".join([f"- {s} — {games[s]['name']}" for s in subs])
    await message.answer(text)

# --- Background task ---
async def updater_loop():
    logger.info("Updater loop started, checking every %s seconds", CHECK_INTERVAL)
    while True:
        for key in games.keys():
            title, url = await check_game(key)
            if not title:
                continue
            last = data.setdefault("last_updates", {}).get(key)
            if last != title:
                # new update
                data.setdefault("last_updates", {})[key] = title
                save_data(data)
                # notify subscribers
                for uid, subs in data.get("subscriptions", {}).items():
                    if key in subs:
                        try:
                            await bot.send_message(int(uid), f"🔔 Обновление: {games[key]['name']}\n{title}\n{url}")
                        except Exception as e:
                            logger.exception("Failed to notify %s: %s", uid, e)
        await asyncio.sleep(CHECK_INTERVAL)

# --- Startup ---
async def main():
    loop = asyncio.get_event_loop()
    loop.create_task(updater_loop())
    await dp.start_polling()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        try:
            asyncio.run(bot.session.close())
        except:
            pass
