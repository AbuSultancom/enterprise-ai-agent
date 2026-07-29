"""Communication & Alerting tools (Email SMTP & Webhooks)."""
from __future__ import annotations

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import httpx

from tools.registry import registry, Tool


@registry.register(
    name="send_email_notification",
    description="Send an email notification or alert to an employee or client.",
    parameters={
        "type": "object",
        "properties": {
            "to_email": {"type": "string", "description": "Recipient email address"},
            "subject": {"type": "string", "description": "Email subject"},
            "body": {"type": "string", "description": "Email body content"},
        },
        "required": ["to_email", "subject", "body"],
    },
)
async def send_email_notification(to_email: str, subject: str, body: str) -> str:
    smtp_server = os.getenv("SMTP_SERVER", "localhost")
    smtp_port = int(os.getenv("SMTP_PORT", "1025")) # Default to local test SMTP or Mailpit
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")

    msg = MIMEMultipart()
    msg["From"] = os.getenv("SMTP_FROM", "ai-agent@company.com")
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        if smtp_user and smtp_pass:
            with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10) as server:
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_server, smtp_port, timeout=5) as server:
                server.send_message(msg)
        return f"Email successfully sent to {to_email} with subject '{subject}'."
    except Exception as e:
        return f"Simulated email send to {to_email} (SMTP server not reachable: {e}). Subject: '{subject}'."


@registry.register(
    name="send_webhook_alert",
    description="Trigger an external HTTP Webhook alert (e.g. Teams, Slack, Zapier).",
    parameters={
        "type": "object",
        "properties": {
            "webhook_url": {"type": "string", "description": "Target webhook URL"},
            "message": {"type": "string", "description": "Alert message string"},
        },
        "required": ["webhook_url", "message"],
    },
)
async def send_webhook_alert(webhook_url: str, message: str) -> str:
    payload = {"text": message, "content": message}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(webhook_url, json=payload)
            res.raise_for_status()
            return f"Webhook alert triggered successfully (HTTP {res.status_code})."
    except Exception as e:
        return f"Webhook alert failed to execute: {e}"
