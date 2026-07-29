#!/usr/bin/env python3
"""
Enterprise AI Agent - Web Setup Server
======================================
FastAPI-based web setup wizard.

Usage:
    uvicorn setup_web:app --host 0.0.0.0 --port 8000
"""

import os
import json
import secrets
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Enterprise AI Agent Setup", version="2.0")

BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = BASE_DIR / "templates"
TEMPLATES_DIR.mkdir(exist_ok=True)

# Create templates if they don't exist
def ensure_templates():
    """Create minimal templates if missing."""
    if not (TEMPLATES_DIR / "base.html").exists():
        # Templates will be created by setup.py
        pass

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# In-memory session storage
sessions: Dict[str, Dict[str, Any]] = {}

STEP_NAMES = {
    "en": ["Language", "LLM", "Identity", "Security", "Channels", "Accounting", "Permissions"],
    "ar": ["اللغة", "النموذج", "الهوية", "الأمان", "القنوات", "المحاسبة", "الصلاحيات"]
}

# ── Routes ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    """Redirect to setup."""
    return RedirectResponse(url="/setup?lang=en&step=0")

@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request, step: int = 0, lang: str = "en"):
    """Render setup wizard page."""
    if lang not in STEP_NAMES:
        lang = "en"

    step_names = STEP_NAMES[lang]
    step = max(0, min(step, 7))

    # Get or create session
    session_id = request.cookies.get("session_id", secrets.token_hex(16))
    if session_id not in sessions:
        sessions[session_id] = {}

    # Determine template
    if step >= 7:
        template = "done.html"
    else:
        template = f"step{step + 1}.html"

    # Build context
    context = {
        "request": request,
        "lang": lang,
        "steps": step_names,
        "current_step": step,
        "title": step_names[step] if step < len(step_names) else "Complete",
        "api_key": secrets.token_urlsafe(32),
        "jwt_secret": secrets.token_urlsafe(32),
        "preview": json.dumps(sessions.get(session_id, {}), indent=2, ensure_ascii=False)
    }

    response = templates.TemplateResponse(template, context)
    response.set_cookie("session_id", session_id, max_age=3600)
    return response

@app.post("/setup")
async def handle_setup(
    request: Request,
    step: int = 0,
    lang: str = "en"
):
    """Process setup form submission."""
    form = await request.form()
    session_id = request.cookies.get("session_id", secrets.token_hex(16))

    if session_id not in sessions:
        sessions[session_id] = {}

    # Save form data
    sessions[session_id][f"step_{step}"] = dict(form)

    next_step = step + 1
    if next_step >= 7:
        # Finalize configuration
        await save_config(session_id)
        return RedirectResponse(url=f"/setup?step=7&lang={lang}", status_code=303)

    return RedirectResponse(url=f"/setup?step={next_step}&lang={lang}", status_code=303)

@app.post("/api/test/{test_type}")
async def test_connection(test_type: str, request: Request):
    """Test connections (LLM, DB, etc.)."""
    form = await request.form()

    if test_type == "llm":
        url = form.get("llm_url", "")
        # Simple connectivity test
        import urllib.request
        try:
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "EnterpriseAI-Agent/2.0")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return JSONResponse({
                    "success": True,
                    "message": f"Connected to {url} (Status: {resp.status})"
                })
        except Exception as e:
            return JSONResponse({
                "success": False,
                "message": f"Connection failed: {str(e)}"
            })

    return JSONResponse({"success": False, "message": "Unknown test type"})

# ── Config Save ───────────────────────────────────────────────────────────

async def save_config(session_id: str):
    """Save configuration files from session data."""
    data = sessions.get(session_id, {})

    env_vars = {}
    settings = {
        "version": "2.0",
        "created_at": datetime.now().isoformat()
    }

    # Extract data from all steps
    for step_key, step_data in data.items():
        for key, value in step_data.items():
            if key.startswith("llm_"):
                if key == "llm_url":
                    env_vars["LLM_URL"] = value
                elif key == "llm_api_key":
                    env_vars["LLM_API_KEY"] = value
                elif key == "llm_model":
                    settings["llm_model"] = value
                elif key == "llm_provider":
                    settings["llm_provider"] = value
            elif key.startswith("agent_"):
                settings[key] = value
            elif key in ["api_key", "jwt_secret", "encryption_key"]:
                env_vars[key.upper()] = value
            elif key == "telegram_token":
                env_vars["TELEGRAM_BOT_TOKEN"] = value

    # Write .env
    env_file = BASE_DIR / ".env"
    with open(env_file, "w", encoding="utf-8") as f:
        f.write("# Enterprise AI Agent - Environment Variables\n")
        f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
        for k, v in sorted(env_vars.items()):
            if v:
                f.write(f'{k}="{v}"\n')

    # Write settings.json
    settings_file = BASE_DIR / "settings.json"
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)

# ── Static Files ──────────────────────────────────────────────────────────

# Serve static files if directory exists
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# ── Main ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
