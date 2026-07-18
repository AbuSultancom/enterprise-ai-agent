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
  'أعطني تقريرًا يوميًا مختصرًا: ملخص مبيعات اليوم وعدد الفواتير وأهم ملاحظة، في نقاط قصيرة.';

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

async function askAgent(text, apiKey, history) {
  const res = await fetch(`${AGENT_URL}/v1/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-API-Key': apiKey },
    body: JSON.stringify({ message: text, history }),
  });
  if (!res.ok) return `Agent error: ${res.status}`;
  const data = await res.json();
  return data.answer || 'No answer.';
}

const HELP_TEXT = `🤖 *أوامر البوت:*
• ${PREFIX}ملخص — ملخص سريع لمبيعات اليوم
• ${PREFIX}مسح — مسح ذاكرة المحادثة
• ${PREFIX}مساعدة — هذه القائمة
أو اكتب أي سؤال بعد ${PREFIX}وسأجيبك.`;

// Built-in quick commands (matched on the text AFTER the prefix is stripped).
function runCommand(text, chatId) {
  const cmd = text.trim();
  if (cmd === 'مساعدة' || cmd === 'help') return { reply: HELP_TEXT };
  if (cmd === 'مسح' || cmd === 'clear') {
    histories.delete(chatId);
    return { reply: '🤖 تم مسح ذاكرة محادثتنا. نبدأ من جديد!' };
  }
  if (cmd === 'ملخص' || cmd === 'summary') {
    return { ask: 'أعطني ملخصًا سريعًا لمبيعات اليوم في نقاط قصيرة بالعربية.' };
  }
  return null;
}

client.on('message', async (msg) => {
  try {
    const chatId = msg.from;
    const sender = msg.from.replace(/\D/g, '');

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
    const answer = await askAgent(question, apiKey, history);

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

// --- Daily scheduled report ---
let lastReportDay = '';
setInterval(async () => {
  if (!REPORT_ENABLED || status !== 'ready') return;
  const now = new Date();
  const hhmm = String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0');
  const today = now.toISOString().slice(0, 10);
  if (hhmm !== REPORT_TIME || lastReportDay === today) return;
  lastReportDay = today;
  try {
    const apiKey = process.env.ADMIN_KEY || 'dev-admin-key';
    console.log('[report] generating daily report...');
    const answer = await askAgent(REPORT_MESSAGE, apiKey, []);
    const chatId = REPORT_TO ? `${REPORT_TO}@c.us` : client.info.wid._serialized;
    await client.sendMessage(chatId, '📊 *التقرير اليومي:*\n\n🤖 ' + answer);
    console.log('[report] sent to', chatId);
  } catch (e) {
    console.error('[report] failed:', e.message);
  }
}, 30000);

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
