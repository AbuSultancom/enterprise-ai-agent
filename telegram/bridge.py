#!/usr/bin/env python3
"""
Telegram channel bridge — connects a Telegram bot to the AI agent.

Long-polling (no public URL needed). Create a bot with @BotFather to get a token.
Config via environment variables:
  TELEGRAM_BOT_TOKEN   — from @BotFather (required)
  TELEGRAM_ALLOWED     — comma-separated numeric user IDs or @usernames (empty = everyone)
  BOT_PREFIX           — optional prefix filter, e.g. "!ai " (empty = reply to all)
  AGENT_URL            — agent API base URL (default http://localhost:8000)
  USER_KEY / ADMIN_KEY + WHATSAPP_ROLE — which API key to use (default: user)
"""
from __future__ import annotations

import asyncio
import os
import re
import sys

import httpx

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
AGENT_URL = os.getenv("AGENT_URL", "http://localhost:8000").rstrip("/")
ROLE = os.getenv("TELEGRAM_ROLE", os.getenv("WHATSAPP_ROLE", "user"))
API_KEY = os.getenv("ADMIN_KEY" if ROLE == "admin" else "USER_KEY", "dev-user-key")
PREFIX = os.getenv("BOT_PREFIX", "")
ALLOWED = {x.strip().lower() for x in os.getenv("TELEGRAM_ALLOWED", "").split(",") if x.strip()}

API = f"https://api.telegram.org/bot{TOKEN}"


def allowed(msg: dict) -> bool:
    if not ALLOWED:
        return True
    user = msg.get("from", {})
    uid = str(user.get("id", "")).lower()
    uname = ("@" + user.get("username", "")).lower()
    return uid in ALLOWED or uname in ALLOWED


async def reply(client: httpx.AsyncClient, chat_id: int, text: str) -> None:
    # Telegram message limit is 4096 chars
    for i in range(0, len(text), 4000):
        await client.post(f"{API}/sendMessage",
                          json={"chat_id": chat_id, "text": text[i:i + 4000]})


async def ask_agent(client: httpx.AsyncClient, text: str) -> str:
    r = await client.post(f"{AGENT_URL}/v1/chat",
                          headers={"X-API-Key": API_KEY},
                          json={"message": text}, timeout=180)
    if r.status_code != 200:
        return f"Agent error: {r.status_code}"
    return r.json().get("answer", "No answer.")


async def main() -> None:
    if not TOKEN:
        print("TELEGRAM_BOT_TOKEN is not set — exiting.")
        sys.exit(1)

    print("Telegram bridge started. Polling for messages...")
    offset = 0
    async with httpx.AsyncClient(timeout=60) as client:
        me = await client.get(f"{API}/getMe")
        if me.status_code == 200:
            print(f"Connected as @{me.json()['result']['username']}")
        else:
            print(f"WARNING: getMe failed ({me.status_code}) — check the token.")

        while True:
            try:
                r = await client.get(f"{API}/getUpdates",
                                     params={"offset": offset, "timeout": 30})
                for upd in r.json().get("result", []):
                    offset = upd["update_id"] + 1
                    msg = upd.get("message") or {}
                    text = (msg.get("text") or "").strip()
                    chat_id = msg.get("chat", {}).get("id")
                    if not text or not chat_id:
                        continue
                    if not allowed(msg):
                        print(f"Ignored message from non-allowed user: {msg.get('from', {})}")
                        continue
                    if PREFIX:
                        if not text.startswith(PREFIX):
                            continue
                        text = text[len(PREFIX):].strip()
                        if not text:
                            continue
                    print(f"[{msg.get('from', {}).get('username', '?')}] {text[:80]}")
                    await client.post(f"{API}/sendChatAction",
                                      json={"chat_id": chat_id, "action": "typing"})
                    try:
                        answer = await ask_agent(client, text)
                    except Exception as e:
                        answer = f"Sorry, something went wrong: {e}"
                    await reply(client, chat_id, answer)
            except httpx.HTTPError as e:
                print(f"Polling error: {e} — retrying in 5s")
                await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
