/**
 * WhatsApp bridge service — connects WhatsApp (via QR login) to the AI agent.
 *
 * Flow: scan QR once (like WhatsApp Web) -> session persists in a volume ->
 * every incoming message is forwarded to the agent's /v1/chat endpoint ->
 * the agent's answer is sent back as a WhatsApp reply.
 *
 * NOTE: this uses the unofficial WhatsApp Web protocol (whatsapp-web.js).
 * For a mission-critical business number, consider the official WhatsApp
 * Business API instead.
 */
import pkg from 'whatsapp-web.js';
const { Client, LocalAuth } = pkg;
import qrcode from 'qrcode';
import qrcodeTerminal from 'qrcode-terminal';
import express from 'express';

// --- Config ---
const AGENT_URL = process.env.AGENT_URL || 'http://agent:8000';
const WHATSAPP_ENABLED = (process.env.WHATSAPP_ENABLED || 'true') === 'true';
const ROLE = process.env.WHATSAPP_ROLE || 'user'; // which API key to use
const AGENT_API_KEY = ROLE === 'admin'
  ? (process.env.ADMIN_KEY || 'dev-admin-key')
  : (process.env.USER_KEY || 'dev-user-key');
const PORT = process.env.WHATSAPP_PORT || 3001;
const PREFIX = process.env.BOT_PREFIX || ''; // e.g. "!ai " to only reply when prefixed; empty = reply to all
const IGNORE_GROUPS = process.env.IGNORE_GROUPS !== 'false';
// Comma-separated phone numbers allowed to talk to the bot (international format,
// e.g. "9677xxxxxxx,8613xxxxxxxx"). Empty = everyone is allowed.
const ALLOWED = (process.env.ALLOWED_NUMBERS || '')
  .split(',').map(n => n.trim().replace(/\D/g, '')).filter(Boolean);
// Numbers that get ADMIN powers (accounting queries etc.). The linked (self) number is always admin.
const ADMIN_NUMBERS = (process.env.ADMIN_NUMBERS || '')
  .split(',').map(n => n.trim().replace(/\D/g, '')).filter(Boolean);
// Conversation memory: last N exchanges kept per chat (0 = off).
const MEMORY_TURNS = parseInt(process.env.CHAT_MEMORY || '5', 10);
// Daily scheduled report: sends an agent-generated summary to REPORT_TO (or self-chat).
const REPORT_ENABLED = (process.env.REPORT_ENABLED || 'false') === 'true';
const REPORT_TIME = process.env.REPORT_TIME || '08:00';       // HH:MM (24h, server local time)
const REPORT_TO = (process.env.REPORT_TO || '').replace(/\D/g, ''); // digits, empty = self-chat
const REPORT_MESSAGE = process.env.REPORT_MESSAGE ||
  'Give me a concise daily report: summary of today\'s sales, count of invoices, and key notes, in short bullet points.';
// Report schedule: daily | weekly (REPORT_WEEKDAY, 0=Sun..6=Sat) | monthly (1st of month)
const REPORT_SCHEDULE = process.env.REPORT_SCHEDULE || 'daily';
const REPORT_WEEKDAY = parseInt(process.env.REPORT_WEEKDAY || '5', 10); // 5 = Friday
const WEEKLY_MESSAGE = 'Give me a concise weekly report: summary of sales this week, count of invoices, and a quick comparison with last week, in short bullet points.';
const MONTHLY_MESSAGE = 'Give me a concise monthly report: summary of sales this month, top customers, and a quick comparison with last month, in short bullet points.';
// Smart alerts: query accounting every N minutes, alert if expenses exceed ALERT_LIMIT.
const ALERTS_ENABLED = (process.env.ALERTS_ENABLED || 'false') === 'true';
const ALERT_LIMIT = parseFloat(process.env.ALERT_LIMIT || '0'); // 0 = off
const ALERT_INTERVAL_MIN = parseInt(process.env.ALERT_INTERVAL_MIN || '30', 10);
const ALERT_TO = (process.env.ALERT_TO || '').replace(/\D/g, ''); // digits, empty = self-chat
// Vision: model that can read images (e.g. gpt-4o). Empty = image messages get a polite fallback.
const VISION_MODEL = process.env.VISION_MODEL || '';

const histories = new Map(); // chat id -> [{role, content}]

// --- Tiny web UI for QR scanning + status ---
const app = express();

if (!WHATSAPP_ENABLED) {
  app.get('/', (req, res) => res.send(
    '<html><body style="font-family:sans-serif;background:#0f172a;color:#e2e8f0;display:flex;justify-content:center;align-items:center;height:100vh"><h1>WhatsApp bridge is disabled (WHATSAPP_ENABLED=false)</h1></body></html>'
  ));
  app.get('/status', (req, res) => res.json({ status: 'disabled' }));
  app.listen(PORT, () => console.log(`WhatsApp disabled — status page on :${PORT}`));
} else {

// --- State ---
let qrDataUrl = null;
let status = 'initializing'; // initializing | qr | ready | disconnected

// --- WhatsApp client (session persisted; /data in Docker, local folder otherwise) ---
const DATA_PATH = process.env.WA_DATA_PATH || './.wwebjs_auth';
const client = new Client({
  authStrategy: new LocalAuth({ dataPath: DATA_PATH }),
  puppeteer: {
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  },
});

client.on('qr', async (qr) => {
  status = 'qr';
  qrDataUrl = await qrcode.toDataURL(qr);
  console.log('\n========================================================');
  console.log('  Scan this QR with WhatsApp -> Linked devices -> Link');
  console.log('========================================================\n');
  qrcodeTerminal.generate(qr, { small: true });
  console.log('\n(QR also available at http://localhost:' + PORT + ')\n');
});

client.on('ready', () => {
  status = 'ready';
  qrDataUrl = null;
  console.log('WhatsApp client is ready');
  console.log(`Listening: prefix=${PREFIX ? JSON.stringify(PREFIX) : '(reply to all)'} · groups=${IGNORE_GROUPS ? 'ignored' : 'allowed'} · allowed=${ALLOWED.length ? ALLOWED.join(',') : 'everyone'}`);
});

client.on('disconnected', (reason) => {
  status = 'disconnected';
  console.log('Disconnected:', reason);
});

// Pick the API key by role: self-chat & ADMIN_NUMBERS -> admin key, others -> user key.
function keyForSender(senderDigits, fromMe) {
  if (fromMe || ADMIN_NUMBERS.some(n => senderDigits.endsWith(n) || n.endsWith(senderDigits))) {
    return process.env.ADMIN_KEY || 'dev-admin-key';
  }
  return process.env.USER_KEY || 'dev-user-key';
}

async function askAgent(text, apiKey, history, sessionId) {
  const res = await fetch(`${AGENT_URL}/v1/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
    body: JSON.stringify({ message: text, history, session_id: sessionId }),
  });
  if (!res.ok) return `Agent error: ${res.status}`;
  const data = await res.json();
  return data.answer || 'No answer.';
}

const HELP_TEXT = `🤖 *Bot Commands:*
• ${PREFIX}summary — Quick summary of today's sales
• ${PREFIX}invoice 123 — Invoice details by number
• ${PREFIX}customer John — Summary of customer transactions
• ${PREFIX}stock — Inventory status
• ${PREFIX}clear — Clear conversation memory
• ${PREFIX}help — Show this command list
Or type any question after ${PREFIX} and I will answer you.`;

// Built-in quick commands (matched on the text AFTER the prefix is stripped).
function runCommand(text, chatId) {
  const cmd = text.trim();
  if (cmd === 'help' || cmd === 'commands') return { reply: HELP_TEXT };
  if (cmd === 'clear') {
    histories.delete(chatId);
    return { reply: '🤖 Conversation memory cleared. Let\'s start fresh!' };
  }
  if (cmd === 'summary') {
    return { ask: 'Give me a quick summary of today\'s sales in short bullet points in English.' };
  }
  if (cmd === 'stock') {
    return { ask: 'Show a summary of current inventory status and low stock items in short bullet points in English.' };
  }
  let m = cmd.match(/^(?:invoice)\s+(.+)$/i);
  if (m) {
    return { ask: `Find invoice number "${m[1].trim()}" and display its number, date, customer name, net total, and status in English.` };
  }
  m = cmd.match(/^(?:customer)\s+(.+)$/i);
  if (m) {
    return { ask: `Show summary of transactions for customer "${m[1].trim()}": total purchases, invoice count, and last transaction, in English.` };
  }
  return null;
}

// Read an image with a vision-capable model (OpenAI-compatible chat API).
async function readImage(base64Data, mimetype, question) {
  const base = (process.env.OPENAI_BASE_URL || 'https://api.openai.com/v1').replace(/\/+$/, '');
  const res = await fetch(`${base}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${process.env.OPENAI_API_KEY || ''}`,
    },
    body: JSON.stringify({
      model: VISION_MODEL,
      messages: [{
        role: 'user',
        content: [
          { type: 'text', text: question },
          { type: 'image_url', image_url: { url: `data:${mimetype};base64,${base64Data}` } },
        ],
      }],
      max_tokens: 1000,
    }),
  });
  if (!res.ok) return null;
  const data = await res.json();
  return data.choices?.[0]?.message?.content || null;
}

client.on('message', async (msg) => {
  try {
    const chatId = msg.from;
    const sender = msg.from.replace(/\D/g, '');

    // Skip status updates (broadcasts from status@broadcast)
    if (msg.from === 'status@broadcast') return;
    // Skip group messages if configured
    if (msg.from.endsWith('@g.us') || msg.from.endsWith('@broadcast')) return;

    // ---- Image messages (invoice/receipt photos) ----
    if (msg.hasMedia) {
      const caption = (msg.body || '').trim();
      const allowedImg = msg.fromMe
        ? (!PREFIX || caption.startsWith(PREFIX) || !caption)
        : (!ALLOWED.length || ALLOWED.some(n => sender.endsWith(n) || n.endsWith(sender)));
      if (!allowedImg) return;
      console.log(`[img] from ${msg.from}`);
      if (!VISION_MODEL) {
        await msg.reply('🤖 I received your image, but image reading is not enabled yet. Please add VISION_MODEL (e.g. gpt-4o) in your .env file');
        return;
      }
      await msg.reply('⏳ Reading the image...');
      try {
        const media = await msg.downloadMedia();
        const q = caption.replace(PREFIX, '').trim() || 'Read the contents of this image in detail and extract the important data in English.';
        const desc = await readImage(media.data, media.mimetype, q);
        if (!desc) {
          await msg.reply('🤖 Could not read the image — check VISION_MODEL and OPENAI_API_KEY');
          return;
        }
        await msg.reply('🤖 ' + desc);
      } catch (e) {
        console.error('Image handling error:', e);
        await msg.reply('🤖 An error occurred while processing the image.');
      }
      return;
    }

    // Self-chat ("Message yourself"): allowed ONLY with the prefix, so the bot
    // never replies to its own answers (infinite loop protection).
    if (msg.fromMe) {
      if (!PREFIX || !(msg.body || '').trim().startsWith(PREFIX)) return;
      console.log(`[msg] self-chat command: ${(msg.body || '').slice(0, 60)}`);
    } else {
      if (IGNORE_GROUPS && msg.from.endsWith('@g.us')) {
        console.log('[msg] ignored: group message (IGNORE_GROUPS=true)');
        return;
      }

      console.log(`[msg] from ${msg.from}: ${(msg.body || '').slice(0, 60)}`);

      // whitelist check: msg.from looks like "9677xxxxxxx@c.us"
      if (ALLOWED.length && !ALLOWED.some(n => sender.endsWith(n) || n.endsWith(sender))) {
        console.log('  -> ignored: number not in ALLOWED_NUMBERS');
        return;
      }
    }

    let text = msg.body.trim();
    if (PREFIX) {
      if (!text.startsWith(PREFIX)) {
        console.log(`  -> ignored: does not start with prefix "${PREFIX}"`);
        return;
      }
      text = text.slice(PREFIX.length).trim();
      if (!text) return;
    }

    // built-in commands first
    const cmd = runCommand(text, chatId);
    if (cmd && cmd.reply) {
      await msg.reply(cmd.reply);
      return;
    }
    const question = (cmd && cmd.ask) || text;

    // role-based key + conversation memory
    const apiKey = keyForSender(sender, msg.fromMe);
    const history = MEMORY_TURNS > 0 ? (histories.get(chatId) || []) : [];

    await msg.reply('⏳ ...');
    try {
      const chat = await msg.getChat();
      await chat.sendStateTyping();
    } catch (e) {
      // typing indicator is optional — continue even if it fails
    }
    const answer = await askAgent(question, apiKey, history, chatId);
    try {
      const chat = await msg.getChat();
      await chat.clearState();
    } catch (e) {
      // typing indicator cleanup is optional
    }

    if (MEMORY_TURNS > 0 && !answer.startsWith('Agent error:')) {
      history.push({ role: 'user', content: question }, { role: 'assistant', content: answer });
      histories.set(chatId, history.slice(-2 * MEMORY_TURNS));
    }

    await msg.reply('🤖 ' + answer);
  } catch (err) {
    console.error('Message handling error:', err);
    try { await msg.reply('Sorry, something went wrong.'); } catch {}
  }
});

// --- Scheduled reports (daily / weekly / monthly) ---
let lastReportDay = '';
const REPORT_TITLES = { daily: 'Daily Report', weekly: 'Weekly Report', monthly: 'Monthly Report' };
const REPORT_MESSAGES = { daily: REPORT_MESSAGE, weekly: WEEKLY_MESSAGE, monthly: MONTHLY_MESSAGE };

function reportDueToday(now) {
  if (REPORT_SCHEDULE === 'weekly') return now.getDay() === REPORT_WEEKDAY;
  if (REPORT_SCHEDULE === 'monthly') return now.getDate() === 1;
  return true; // daily
}

setInterval(async () => {
  if (!REPORT_ENABLED || status !== 'ready') return;
  const now = new Date();
  const hhmm = String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0');
  const today = now.toISOString().slice(0, 10);
  if (hhmm !== REPORT_TIME || lastReportDay === today || !reportDueToday(now)) return;
  lastReportDay = today;
  try {
    const apiKey = process.env.ADMIN_KEY || 'dev-admin-key';
    const message = REPORT_MESSAGES[REPORT_SCHEDULE] || REPORT_MESSAGE;
    console.log(`[report] generating ${REPORT_SCHEDULE} report...`);
    const answer = await askAgent(message, apiKey, [], 'report');
    const chatId = REPORT_TO ? `${REPORT_TO}@c.us` : client.info.wid._serialized;
    await client.sendMessage(chatId, `📊 *${REPORT_TITLES[REPORT_SCHEDULE] || 'Report'}:*\n\n🤖 ` + answer);
    console.log('[report] sent to', chatId);
  } catch (e) {
    console.error('[report] failed:', e.message);
  }
}, 30000);

// --- Smart alerts: warn when today's expenses exceed ALERT_LIMIT ---
let lastAlertDay = '';
setInterval(async () => {
  if (!ALERTS_ENABLED || !ALERT_LIMIT || status !== 'ready') return;
  try {
    const now = new Date();
    const day = now.toISOString().slice(0, 10);
    const res = await fetch(`${AGENT_URL}/v1/accounting/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-API-Key': process.env.ADMIN_KEY || 'dev-admin-key' },
      body: JSON.stringify({ query: 'expenses_summary', params: { start: `${day}T00:00:00`, end: `${day}T23:59:59` } }),
    });
    if (!res.ok) return; // accounting not configured or query failed — stay quiet
    const rows = await res.json();
    const total = (Array.isArray(rows) ? rows : []).reduce(
      (sum, r) => sum + Object.values(r).reduce((s, v) => s + (typeof v === 'number' ? v : 0), 0), 0);
    if (total > ALERT_LIMIT && lastAlertDay !== day) {
      lastAlertDay = day;
      const chatId = (ALERT_TO || REPORT_TO) ? `${ALERT_TO || REPORT_TO}@c.us` : client.info.wid._serialized;
      await client.sendMessage(chatId,
        `🚨 *Expense Alert!*\n\nToday's expenses reached ${total.toLocaleString('en')} and exceeded the set limit (${ALERT_LIMIT.toLocaleString('en')}).`);
      console.log('[alert] expense alert sent:', total);
    }
  } catch (e) {
    console.error('[alert] check failed:', e.message);
  }
}, Math.max(ALERT_INTERVAL_MIN, 5) * 60000);

client.initialize();

app.get('/', (req, res) => {
  if (status === 'ready') {
    res.send(`<html><body style="font-family:sans-serif;background:#0f172a;color:#e2e8f0;display:flex;justify-content:center;align-items:center;height:100vh">
      <div style="text-align:center"><h1>✅ WhatsApp connected</h1><p>The AI agent is answering messages.</p></div></body></html>`);
  } else if (status === 'qr' && qrDataUrl) {
    res.send(`<html><head><meta http-equiv="refresh" content="5"></head>
      <body style="font-family:sans-serif;background:#0f172a;color:#e2e8f0;display:flex;justify-content:center;align-items:center;height:100vh">
      <div style="text-align:center"><h1>Scan with WhatsApp</h1>
      <p>WhatsApp → Linked devices → Link a device</p>
      <img src="${qrDataUrl}" style="width:300px;border-radius:12px"/></div></body></html>`);
  } else {
    res.send(`<html><head><meta http-equiv="refresh" content="3"></head>
      <body style="font-family:sans-serif;background:#0f172a;color:#e2e8f0;display:flex;justify-content:center;align-items:center;height:100vh">
      <div><h1>Status: ${status}</h1><p>Waiting...</p></div></body></html>`);
  }
});

app.get('/status', (req, res) => res.json({ status }));

app.listen(PORT, () => console.log(`QR web UI on http://localhost:${PORT}`));

}
