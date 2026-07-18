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

client.on('message', async (msg) => {
  try {
    if (msg.fromMe) return;
    if (IGNORE_GROUPS && msg.from.endsWith('@g.us')) return;

    console.log(`[msg] from ${msg.from}: ${(msg.body || '').slice(0, 60)}`);

    // whitelist check: msg.from looks like "9677xxxxxxx@c.us"
    const sender = msg.from.replace(/\D/g, '');
    if (ALLOWED.length && !ALLOWED.some(n => sender.endsWith(n) || n.endsWith(sender))) {
      console.log('  -> ignored: number not in ALLOWED_NUMBERS');
      return;
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

    await msg.reply('⏳ ...');
    const res = await fetch(`${AGENT_URL}/v1/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': AGENT_API_KEY,
      },
      body: JSON.stringify({ message: text }),
    });

    if (!res.ok) {
      await msg.reply(`Agent error: ${res.status}`);
      return;
    }
    const data = await res.json();
    await msg.reply(data.answer || 'No answer.');
  } catch (err) {
    console.error('Message handling error:', err);
    try { await msg.reply('Sorry, something went wrong.'); } catch {}
  }
});

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
