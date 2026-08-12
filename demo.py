#!/usr/bin/env python3
"""
Demo: How the unified setup works
"""

print("""
╔══════════════════════════════════════════════════════════════════╗
║     Enterprise AI Agent - Unified Setup Wizard v2.0              ║
╚══════════════════════════════════════════════════════════════════╝

🎯 ONE COMMAND TO RULE THEM ALL:

    $ python setup.py

┌──────────────────────────────────────────────────────────────────┐
│  Choose setup mode:                                               │
│                                                                   │
│    → [1] Command Line (Terminal)                                  │
│      [2] Web Browser (Recommended)                                │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘

════════════════════════════════════════════════════════════════════
 OPTION 1: CLI Mode
════════════════════════════════════════════════════════════════════

    [1/7] Language
          → Select: English / العربية

    [2/7] LLM Configuration
          → Provider: Ollama / OpenAI / Claude / Gemini
          → Model: qwen2.5:7b / llama3.1:8b / etc.
          → URL: http://localhost:11434
          → Test Connection: ✅ OK

    [3/7] Agent Identity
          → Name: EnterpriseBot
          → Description: AI assistant

    [4/7] Security & Keys
          → Generate secure keys: ✅ Yes

    [5/7] Communication Channels
          → WhatsApp: ✅ / ❌
          → Telegram: ✅ / ❌
          → Web Dashboard: ✅ (Port 8000)

    [6/7] Accounting Integration
          → Enable: ❌ (Skip)

    [7/7] Permissions
          → Web Search: ✅
          → File Access: ❌
          → Code Execution: ❌

    ✅ Setup Complete!

    Files created:
      • .env
      • settings.json
      • backups/config_backup_20260730_120000/

════════════════════════════════════════════════════════════════════
 OPTION 2: Web Mode (RECOMMENDED)
════════════════════════════════════════════════════════════════════

    🚀 Launching web setup server...

    Open your browser and go to:
      http://localhost:8000/setup

    [Browser opens automatically]

    ┌─────────────────────────────────────────────┐
    │  🤖 Enterprise AI Agent                     │
    │  Setup Wizard v2.0                          │
    │                                             │
    │  ●───○───○───○───○───○───○                │
    │  Language  LLM  Identity  Security...       │
    │                                             │
    │  ┌─────────────────────────────────────┐   │
    │  │  🌐 Choose Language                  │   │
    │  │                                     │   │
    │  │  [English ▼]                        │   │
    │  │                                     │   │
    │  │  [        Next →        ]           │   │
    │  └─────────────────────────────────────┘   │
    │                                             │
    │  [Dark Theme 🌙]  [Language: EN/AR ▼]      │
    └─────────────────────────────────────────────┘

    Features:
      ✅ Beautiful dark UI
      ✅ Real-time connection testing
      ✅ Toggle switches for permissions
      ✅ Add multiple databases
      ✅ Live config preview
      ✅ Auto-generate secure keys
      ✅ Mobile responsive

════════════════════════════════════════════════════════════════════
 FORCE MODE (skip selector)
════════════════════════════════════════════════════════════════════

    $ python setup.py --cli      # Force CLI
    $ python setup.py --web      # Force Web
    $ python setup.py --update   # Update existing config

════════════════════════════════════════════════════════════════════
""")
