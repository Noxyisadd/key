const express = require('express');
const fs = require('fs');
const path = require('path');
const app = express();
app.use(express.json());

const DATA_FILE = path.join(__dirname, 'keys.json');

let users = new Map();

function loadKeys() {
  if (fs.existsSync(DATA_FILE)) {
    const raw = fs.readFileSync(DATA_FILE, 'utf-8');
    try {
      const obj = JSON.parse(raw);
      users = new Map(Object.entries(obj));

      for (const [key, data] of users) {
        if (data.expiresAt) data.expiresAt = Number(data.expiresAt);
      }
    } catch (e) {
      console.error('Failed to parse keys.json, starting fresh.', e);
      users = new Map();
    }
  }
}

function saveKeys() {

  const obj = Object.fromEntries(users);
  fs.writeFileSync(DATA_FILE, JSON.stringify(obj, null, 2));
}

function parseDuration(timeStr) {
  const units = {
    min: 60,
    h: 3600,
    d: 86400,
    m: 2592000,
    y: 31536000
  };

  const regex = /^(\d+)(min|[dhmy])$/i;
  const match = timeStr.match(regex);
  if (!match) return null;

  const value = parseInt(match[1], 10);
  const unit = match[2].toLowerCase();

  return value * units[unit];
}

loadKeys();

app.post('/register', (req, res) => {
  const { username, time } = req.body;

  if (!username || !time) {
    return res.status(400).json({ error: 'Username and time are required' });
  }

  let expiresAt = null;
  if (time.toLowerCase() !== 'lifetime') {
    const seconds = parseDuration(time);
    if (!seconds) return res.status(400).json({ error: 'Invalid time format (e.g., 1d, 1m, 1y, 1min)' });
    expiresAt = Date.now() + seconds * 1000;
  }

  const apiKey = Math.random().toString(36).slice(2, 18);
  users.set(apiKey, { username, hwid: null, expiresAt });

  saveKeys();

  res.json({ apiKey, expiresAt });
});

app.post('/login', (req, res) => {
  const { apiKey, hwid } = req.body;

  const user = users.get(apiKey);
  if (!user) return res.status(401).json({ error: 'Invalid key' });

  if (user.expiresAt && Date.now() > user.expiresAt) {
    return res.status(401).json({ error: 'Key expired' });
  }

  if (user.hwid && user.hwid !== hwid) {
    return res.status(401).json({ error: 'HWID mismatch' });
  }

  if (!user.hwid) {
    user.hwid = hwid;
    saveKeys();
  }

  res.json({ success: true, expiresAt: user.expiresAt || 0 });
});

app.get('/list', (req, res) => {
  const list = [];
  for (const [key, data] of users) {
    list.push({
      key,
      username: data.username,
      hwid: data.hwid,
      expiresAt: data.expiresAt || null
    });
  }
  res.json(list);
});

app.post('/hwid-reset', (req, res) => {
  const { apiKey } = req.body;
  const user = users.get(apiKey);
  if (!user) return res.status(404).json({ error: 'Key not found' });

  user.hwid = null;
  saveKeys();

  res.json({ success: true });
});

app.delete('/key', (req, res) => {
  const { apiKey } = req.body;
  if (!users.has(apiKey)) return res.status(404).json({ error: 'Key not found' });

  users.delete(apiKey);
  saveKeys();

  res.json({ success: true });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`✅ API running on port ${PORT}`));