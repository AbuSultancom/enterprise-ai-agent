"""
Admin Settings Tools - Agent can modify its own configuration.
==============================================================
The agent can change models, language, persona, tools, channels,
add providers, schedule tasks, and restart itself.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = os.path.join(ROOT, ".env")
SETTINGS_FILE = os.path.join(ROOT, "config", "settings.json")


def _read_env() -> dict:
    env = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


def _write_env(env: dict) -> None:
    with open(ENV_FILE, "w", encoding="utf-8") as f:
        for k, v in env.items():
            f.write(f"{k}={v}\n")


def _read_settings() -> dict:
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _write_settings(data: dict) -> None:
    os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


async def change_model(provider: str, model: str) -> str:
    try:
        env = _read_env()
        env["DEFAULT_MODEL"] = f"{provider}:{model}"
        _write_env(env)
        return f"✅ تم تغيير الموديل إلى: {provider}:{model} (يحتاج إعادة تشغيل)"
    except Exception as e:
        return f"❌ خطأ: {e}"


async def change_language(language: str) -> str:
    try:
        if language not in ("ar", "en", "auto"):
            return "❌ اللغة يجب أن تكون: ar, en, أو auto"
        settings = _read_settings()
        settings.setdefault("agent", {})["language"] = language
        _write_settings(settings)
        names = {"ar": "العربية", "en": "English", "auto": "تلقائي"}
        return f"✅ تم تغيير لغة الوكيل إلى: {names.get(language, language)}"
    except Exception as e:
        return f"❌ خطأ: {e}"


async def change_personality(personality: str) -> str:
    try:
        settings = _read_settings()
        settings.setdefault("agent", {})["personality"] = personality
        _write_settings(settings)
        return f"✅ تم تغيير شخصية الوكيل إلى: {personality}"
    except Exception as e:
        return f"❌ خطأ: {e}"


async def toggle_tool(tool_name: str, enabled: bool = True) -> str:
    try:
        settings = _read_settings()
        settings.setdefault("permissions", {})[tool_name] = enabled
        _write_settings(settings)
        action = "تفعيل" if enabled else "تعطيل"
        return f"✅ تم {action} أداة: {tool_name}"
    except Exception as e:
        return f"❌ خطأ: {e}"


async def change_whatsapp_prefix(prefix: str) -> str:
    try:
        env = _read_env()
        env["BOT_PREFIX"] = prefix
        _write_env(env)
        if prefix:
            return f"✅ تم تغيير بادئة واتساب إلى: '{prefix}'"
        else:
            return "✅ تم إلغاء البادئة - الوكيل يرد على كل الرسائل"
    except Exception as e:
        return f"❌ خطأ: {e}"


async def add_api_key(name: str, key: str) -> str:
    try:
        env = _read_env()
        env_name = f"{name.upper()}_API_KEY"
        env[env_name] = key
        _write_env(env)
        return f"✅ تم حفظ مفتاح API: {env_name}"
    except Exception as e:
        return f"❌ خطأ: {e}"


async def toggle_channel(channel: str, enabled: bool = True) -> str:
    try:
        env = _read_env()
        key = f"{channel.upper()}_ENABLED"
        env[key] = "true" if enabled else "false"
        _write_env(env)
        action = "تفعيل" if enabled else "تعطيل"
        return f"✅ تم {action} قناة: {channel}"
    except Exception as e:
        return f"❌ خطأ: {e}"


async def add_provider(name: str, base_url: str, api_key: str,
                       models: str = "") -> str:
    try:
        env = _read_env()
        pkey = f"PROVIDER_{name.upper()}_BASE_URL"
        akey = f"PROVIDER_{name.upper()}_API_KEY"
        mkey = f"PROVIDER_{name.upper()}_MODELS"
        env[pkey] = base_url
        env[akey] = api_key
        if models:
            env[mkey] = models
        _write_env(env)

        settings = _read_settings()
        settings.setdefault("providers", {})[name] = {
            "base_url": base_url,
            "has_key": bool(api_key),
            "models": models.split(",") if models else [],
        }
        _write_settings(settings)

        lines = [f"✅ تمت إضافة مزود: {name}", f"   الرابط: {base_url}"]
        if models:
            lines.append(f"   الموديلات: {models}")
        lines.append("   استخدم: python start.py لإعادة التشغيل")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ خطأ: {e}"


async def restart_agent() -> str:
    try:
        restart_marker = os.path.join(ROOT, "data", ".restart")
        Path(restart_marker).touch()
        return "🔄 جاري إعادة تشغيل الوكيل..."
    except Exception as e:
        return f"❌ خطأ: {e}"


async def show_current_config() -> str:
    try:
        env = _read_env()
        settings = _read_settings()

        lines = ["⚙️ الإعدادات الحالية / Current Configuration\n"]
        lines.append(f"📡 الموديل: {env.get('DEFAULT_MODEL', 'غير محدد')}")
        lines.append(f"🌐 اللغة: {settings.get('agent', {}).get('language', 'auto')}")
        lines.append(f"👤 الشخصية: {settings.get('agent', {}).get('personality', 'افتراضي')}")
        lines.append(f"📱 واتساب: {'✅' if env.get('WHATSAPP_ENABLED')=='true' else '❌'}")
        lines.append(f"💬 تلغرام: {'✅' if env.get('TELEGRAM_ENABLED')=='true' else '❌'}")
        lines.append(f"🏷️ البادئة: '{env.get('BOT_PREFIX', '(بدون)')}'")

        perms = settings.get("permissions", {})
        if perms:
            lines.append(f"\n🛠️ الأدوات: {sum(1 for v in perms.values() if v)}/{len(perms)} مفعلة")

        acc_file = os.path.join(ROOT, "config", "accounting_schema.json")
        if os.path.exists(acc_file):
            with open(acc_file, encoding="utf-8") as f:
                acc = json.load(f)
            dbs = acc.get("databases", {})
            lines.append(f"🏦 قواعد البيانات: {len(dbs)}")
            for key, val in dbs.items():
                lines.append(f"   • {val.get('name', key)}")

        lines.append(f"\n🔑 مفاتيح API:")
        for k, v in env.items():
            if "API_KEY" in k and v:
                masked = v[:4] + "..." if len(v) > 8 else "***"
                lines.append(f"   {k}: {masked}")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ خطأ: {e}"
