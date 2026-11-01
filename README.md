# Twitch Short Username Checker & HyperTurbo Sniper 🚀

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Speed](https://img.shields.io/badge/Speed-2%2C500--4%2C000%2B%20req%2Fsec-brightgreen.svg)]()
[![Twitch GQL](https://img.shields.io/badge/Twitch-Internal%20GraphQL-9146FF.svg)](https://twitch.tv)

A high-performance, real-time Twitch short handle validator and in-browser turbo sniper. Designed to discover, test, and snipe rare 4-letter and 5-letter usernames, dictionary words, and aesthetic handles at **up to 2,500–4,000+ names per second with 50 concurrent workers (verified zero flags)** with **100% verification accuracy**.

---

## 🌟 Why This Sniper is Different

Most external Twitch checkers only query the public `user(login)` endpoint, which produces **false positives**:
- ❌ Many names appear "free" on public endpoints but are actually **locked, banned, or held in a 6-month recycling cooldown**.
- ❌ Public endpoints get IP-banned or rate-limited after just a few dozen checks.

### The In-Browser Apex Sniper Solution (v4.0)
This tool bridges directly to your logged-in **Twitch Profile Settings** tab (`twitch.tv/settings/profile`):
- ✅ Uses Twitch's official **internal `UsernameValidator_User` GraphQL query** with your active session integrity token (`Client-Integrity`).
- ✅ **100% True Availability:** If the sniper says a name is available, it is **guaranteed claimable right that second**.
- ✅ **Apex 50 Concurrent Workers:** Launches up to 50 parallel async workers with batch sizes up to 35, checking **2,500–4,000+ names every second** over HTTP/2 multiplexing with smooth 4ms network staggering.
- ✅ **Instant Auto-Fill:** When an available handle is found, click **Auto-Fill** to instantly inject it into the Twitch username input box.

---

## ✨ Features

- **Continuous Scan Mode:**
  - Toggle **Continuous Scan (Find all)** to keep scanning through massive lists without stopping on the first hit.
  - Discovered usernames stream live into a responsive grid with copy and auto-fill buttons.
  - Multi-tone audio chimes notify you whenever a free handle is found.
- **Exhaustive 4-Character Combinations:**
  - 🌐 **All 4-Character Alphanumeric:** `a-z`, `0-9` (1,679,616 combinations).
  - 🔡 **All 4-Letter Combinations:** `aaaa` → `zzzz` (456,976 combinations).
  - 🔤 **Partitioned Brackets:** A–E, F–J, K–O, P–T, U–Z (~87,800 to 105,400 each).
  - 🔢 **Digits First:** `0-9***` (466,560 combinations).
- **Curated & Aesthetic Presets:**
  - ✨ **4-Letter & 5-Letter Pronounceable:** High-value CVCV/CVCVC handles (e.g., `kuro`, `vibe`, `zemo`, `valek`).
  - 💎 **Aesthetic Patterns:** Repetitive and palindromic patterns (`AAAA`, `AABB`, `ABAB`, `ABBA`).
  - 📖 **Dictionary Dictionaries:** Clean English words (4,030 4-letter words, 8,938 5-letter words).
  - 👑 **Gamertag Suffixes:** `**og`, `**gg`, `**tv`, `**77`, `**99`.
- **Custom Pattern Engine & Pasting:**
  - Wildcard pattern matching: `*god`, `z***`, `??99`, `x#@#` (`*`/`?` = alphanumeric, `@` = letter, `#` = digit).
  - Direct paste box: paste thousands of custom usernames to test them at turbo speed.
- **Interactive Dark Dashboard:**
  - Live speedometer (checks/second), total tested counter, live current batch preview, and real-time status pill.
- **Headless CLI Mode:**
  - Complete command-line interface for offline checks, database querying, and file exports.

---

## 🚀 Quick Start

### 1. Installation

Clone this repository and install dependencies:

```bash
git clone https://github.com/ludzof/twitch-name-checker.git
cd twitch-name-checker
pip install -r requirements.txt
```

### 2. Launch the Dashboard

Run the server (or double-click `start.bat` on Windows):

```bash
python server.py
```

Open your browser at **[http://localhost:5050](http://localhost:5050)**.

### 3. Link Your Twitch Tab

1. Open your Twitch settings page in Chrome/Firefox:  
   👉 **[https://www.twitch.tv/settings/profile](https://www.twitch.tv/settings/profile)**
2. Click the edit pencil icon next to **Username** so the change dialog is active.
3. Link the tab using **either** of these methods:
   - **Method A (Tampermonkey - Recommended):**  
     Install the Userscript loader from `http://localhost:5050/twitch_sniper.user.js`. It auto-updates and keeps the bridge linked permanently.
   - **Method B (1-Line Console):**  
     Press <kbd>F12</kbd> on the Twitch tab $\rightarrow$ go to **Console** $\rightarrow$ paste:
     ```javascript
     fetch("http://localhost:5050/static/browser_sniper.js?v=" + Date.now()).then(r=>r.text()).then(eval);
     ```
4. Look at the bottom-right of your Twitch page: you will see a green floating pill:  
   `🟢 Dashboard Linked: Active v3.0 (<your_username>)`

### 4. Start Scanning!

Go back to **[http://localhost:5050](http://localhost:5050)**:
- Select your candidate category (e.g., *All 4 Characters*, *4-Letter Pronounceable*, or *Custom Wildcard*).
- Check **Continuous Scan (Find all)** to collect all available handles.
- Click **START TURBO SCAN**!

---

## 💻 Headless CLI Usage

You can also run scans directly from your terminal:

```bash
# Instant check for a single username
python cli.py check ninja
python cli.py check zw7v

# Scan 3-character letter combinations
python cli.py scan --mode 3char_letters

# Scan 4-letter English dictionary words and save to file
python cli.py scan --mode 4char_words --out free_4letter_words.txt

# Scan custom wildcard pattern
python cli.py scan --mode pattern --pattern "z***"

# Scan custom text file (one username per line)
python cli.py scan --mode file --file my_names.txt

# View SQLite database statistics
python cli.py stats

# Export available names from database
python cli.py export --status available --out available_names.txt
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────┐          HTTP Sync / WS          ┌──────────────────────────────────┐
│   Twitch Browser Tab            │◄────────────────────────────────►│   Local Dashboard (Web UI)       │
│   (twitch.tv/settings/profile)  │                                  │   http://localhost:5050          │
│                                 │                                  │                                  │
│  - Internal GraphQL Validator   │                                  │  - Real-time speedometer         │
│  - Session Integrity Token      │                                  │  - Candidate preset generator    │
│  - Local 1.68M combinatorics    │                                  │  - Live verified hits grid       │
│  - Auto-fill handle injector    │                                  │  - Start / Stop remote control   │
└────────────────┬────────────────┘                                  └─────────────────┬────────────────┘
                 │                                                                     │
                 │ Batched GQL (15/req)                                                │ SQLite Cache
                 ▼                                                                     ▼
┌─────────────────────────────────┐                                  ┌──────────────────────────────────┐
│   Twitch GraphQL Engine         │                                  │   SQLite Database (results.db)   │
│   (https://gql.twitch.tv/gql)   │                                  │   Caches all checked usernames   │
└─────────────────────────────────┘                                  └──────────────────────────────────┘
```

---

## 📋 Twitch Username Rules

- **Length:** 4 to 25 characters (some grandfathered accounts are 2 or 3 characters).
- **Allowed Characters:** Letters `a-z`, numbers `0-9`, and underscores `_`.
- **Leading Underscores:** Usernames **cannot** begin with an underscore `_`.
- **Recycling Period:** Released or renamed accounts are held in a **6-month lock** before public re-release.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
