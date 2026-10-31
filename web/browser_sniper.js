/**
 * Twitch In-Browser Turbo Sniper & Dashboard Bridge
 * 
 * Auto-connects to your local dashboard at http://localhost:5050
 * Executes high-speed (150-300+ names/sec) internal GraphQL validation
 * using your logged-in Twitch session.
 */

(function () {
  // Prevent duplicate instances by calling cleanup on any previous instance
  if (typeof window.__TWITCH_SNIPER_CLEANUP__ === "function") {
    try { window.__TWITCH_SNIPER_CLEANUP__(); } catch (e) {}
  }
  const existingPill = document.getElementById("twitch-sniper-status-pill");
  if (existingPill) existingPill.remove();

  console.log("%c🎯 Twitch Sniper Bridge v3.0 (Continuous Mode) Activated!", "color: #00f593; font-size: 16px; font-weight: bold;");

  // State
  let isScanning = false;
  let testedCount = 0;
  let currentSpeed = 0.0;
  let currentBatch = "";
  let startTime = null;
  let capturedHeaders = null;
  let isConnected = false;
  let syncInterval = null;

  window.__TWITCH_SNIPER_CLEANUP__ = function () {
    isScanning = false;
    if (syncInterval) clearInterval(syncInterval);
    const p = document.getElementById("twitch-sniper-status-pill");
    if (p) p.remove();
  };

  // React Input value setter that triggers React synthetic events
  function setNativeValue(el, val) {
    const setter = Object.getOwnPropertyDescriptor(el, 'value')?.set || Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), 'value')?.set;
    if (setter) setter.call(el, val); else el.value = val;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  }

  // Audio alert on available name
  function playSuccessSound() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(587.33, ctx.currentTime);
      osc.frequency.setValueAtTime(880, ctx.currentTime + 0.15);
      osc.frequency.setValueAtTime(1174.66, ctx.currentTime + 0.3);
      gain.gain.setValueAtTime(0.35, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.85);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.85);
    } catch (e) {}
  }

  // Robust username detection for logged-in user
  function getTwitchUsername() {
    // 1. Check exact cookies
    const cookieMatch = document.cookie.match(/(?:^|;\s*)(?:login|name)=([a-zA-Z0-9_]{3,25})/);
    if (cookieMatch && !cookieMatch[1].includes("-") && !cookieMatch[1].includes("T")) {
      return cookieMatch[1];
    }

    // 2. Check Slovak modal text: "používateľské meno <username> bude..."
    const bodyText = document.body.innerText || "";
    const slovakMatch = bodyText.match(/používateľské\s+meno\s+([a-zA-Z0-9_]{3,25})\s+bude/i);
    if (slovakMatch) return slovakMatch[1];

    // 3. Check English modal text: "username <username> will be..."
    const engMatch = bodyText.match(/username\s+([a-zA-Z0-9_]{3,25})\s+will/i);
    if (engMatch) return engMatch[1];

    // 4. Check display name tag in Twitch nav
    const dispEl = document.querySelector('[data-a-target="user-display-name"]');
    if (dispEl && dispEl.innerText && /^[a-zA-Z0-9_]{3,25}$/.test(dispEl.innerText.trim())) {
      return dispEl.innerText.trim();
    }

    return "yuukisvk";
  }

  // Sniff real Twitch GraphQL headers (especially Client-Integrity)
  const origFetch = window.fetch;
  window.fetch = async function (...args) {
    const [res, cfg] = args;
    if (typeof res === 'string' && res.includes('/gql') && cfg?.headers) {
      let h = cfg.headers instanceof Headers ? Object.fromEntries(cfg.headers.entries()) : { ...cfg.headers };
      if (h['Client-Integrity'] || h['client-integrity']) {
        capturedHeaders = { ...h };
      }
    }
    return origFetch.apply(this, args);
  };

  function findInput() {
    const dialog = document.querySelector('[role="dialog"]');
    if (dialog) {
      const inp = dialog.querySelector('input[type="text"]');
      if (inp) return inp;
    }
    const inputs = Array.from(document.querySelectorAll('input[type="text"]'));
    return inputs.find(i => i.maxLength === 25 || i.placeholder?.toLowerCase().includes("meno") || i.placeholder?.toLowerCase().includes("username")) || inputs.pop();
  }

  async function getHeaders() {
    if (capturedHeaders && (capturedHeaders['Client-Integrity'] || capturedHeaders['client-integrity'])) {
      return capturedHeaders;
    }
    const inp = findInput();
    if (inp) {
      // Trigger a light input event to prompt Twitch to generate/send Client-Integrity
      const cur = inp.value;
      setNativeValue(inp, cur ? cur + "x" : "test");
      await new Promise(r => setTimeout(r, 400));
      if (cur) setNativeValue(inp, cur);
    }
    if (!capturedHeaders) {
      try {
        const m = document.cookie.match(/(?:^|;\s*)auth-token=([^;]+)/);
        const t = m ? m[1] : null;
        const r = await origFetch("https://gql.twitch.tv/integrity", {
          method: "POST",
          headers: {
            "Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko",
            ...(t ? { "Authorization": `OAuth ${t}` } : {})
          }
        });
        const d = await r.json();
        if (d.token) {
          capturedHeaders = {
            "Client-Id": "kimne78kx3ncx6brgo4mv6wki5h1ko",
            "Client-Integrity": d.token,
            "Content-Type": "application/json",
            ...(t ? { "Authorization": `OAuth ${t}` } : {})
          };
        }
      } catch (e) {}
    }
    return capturedHeaders;
  }

  // Floating Status Pill UI
  const pill = document.createElement("div");
  pill.id = "twitch-sniper-status-pill";
  pill.style = `
    position: fixed;
    bottom: 24px;
    right: 24px;
    z-index: 9999999;
    background: #0e0e14;
    color: #efeff1;
    border: 1px solid #bf94ff;
    border-radius: 30px;
    padding: 10px 18px;
    font-family: Inter, Roobert, -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 13px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.7), 0 0 15px rgba(145,71,255,0.4);
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: default;
    user-select: none;
    transition: all 0.25s ease;
  `;
  document.body.appendChild(pill);

  function updatePill(html, dotColor = "#00f593") {
    pill.innerHTML = `
      <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${dotColor};box-shadow:0 0 10px ${dotColor};flex-shrink:0;"></span>
      <span>${html}</span>
    `;
    pill.style.borderColor = dotColor;
  }

  updatePill("Connecting to Dashboard...", "#ffaa00");

  // Universal Bridge Request (Tampermonkey GM_xmlhttpRequest + normal Fetch fallback)
  function bridgeRequest(endpoint, body) {
    const url = `http://127.0.0.1:5050${endpoint}`;
    return new Promise((resolve, reject) => {
      if (typeof GM_xmlhttpRequest !== "undefined") {
        GM_xmlhttpRequest({
          method: "POST",
          url: url,
          headers: { "Content-Type": "application/json" },
          data: JSON.stringify(body),
          timeout: 4000,
          onload: (res) => {
            try {
              resolve(JSON.parse(res.responseText));
            } catch (e) {
              resolve({});
            }
          },
          onerror: reject,
          ontimeout: () => reject(new Error("Timeout"))
        });
      } else {
        origFetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body)
        })
          .then((r) => r.json())
          .then(resolve)
          .catch(reject);
      }
    });
  }

  function fillUsername(name) {
    const input = findInput();
    if (input) {
      setNativeValue(input, name);
      input.style.border = "3px solid #00f593";
      input.style.boxShadow = "0 0 25px rgba(0,245,147,0.8)";
      updatePill(`🎯 Filled: <strong>${name}</strong>`, "#00f593");
    }
  }

  // Candidate Generator
  async function getCandidates(source = "pronounceable_4", pattern = "", customList = []) {
    // 1. Direct custom pasted list
    if (Array.isArray(customList) && customList.length > 0) {
      return customList.filter(x => x && x.length >= 4);
    }

    // 2. Fast in-browser generator for full exhaustive sets
    if (source === "all_4char_alphanumeric") {
      updatePill("Generating all 1,679,616 4-character names...", "#bf94ff");
      const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
      const names = [];
      for (let a of chars) {
        for (let b of chars) {
          for (let c of chars) {
            for (let d of chars) {
              names.push(a + b + c + d);
            }
          }
        }
      }
      return names;
    }

    if (source === "letters_4" || source === "all_4char_letters") {
      updatePill("Generating all 456,976 4-letter names...", "#bf94ff");
      const chars = "abcdefghijklmnopqrstuvwxyz";
      const names = [];
      for (let a of chars) {
        for (let b of chars) {
          for (let c of chars) {
            for (let d of chars) {
              names.push(a + b + c + d);
            }
          }
        }
      }
      return names;
    }

    if (source === "letters_4_a_e") {
      const first = "abcde";
      const all = "abcdefghijklmnopqrstuvwxyz";
      const names = [];
      for (let a of first) for (let b of all) for (let c of all) for (let d of all) names.push(a + b + c + d);
      return names;
    }

    if (source === "letters_4_f_j") {
      const first = "fghij";
      const all = "abcdefghijklmnopqrstuvwxyz";
      const names = [];
      for (let a of first) for (let b of all) for (let c of all) for (let d of all) names.push(a + b + c + d);
      return names;
    }

    if (source === "letters_4_k_o") {
      const first = "klmno";
      const all = "abcdefghijklmnopqrstuvwxyz";
      const names = [];
      for (let a of first) for (let b of all) for (let c of all) for (let d of all) names.push(a + b + c + d);
      return names;
    }

    if (source === "letters_4_p_t") {
      const first = "pqrst";
      const all = "abcdefghijklmnopqrstuvwxyz";
      const names = [];
      for (let a of first) for (let b of all) for (let c of all) for (let d of all) names.push(a + b + c + d);
      return names;
    }

    if (source === "letters_4_u_z") {
      const first = "uvwxyz";
      const all = "abcdefghijklmnopqrstuvwxyz";
      const names = [];
      for (let a of first) for (let b of all) for (let c of all) for (let d of all) names.push(a + b + c + d);
      return names;
    }

    if (source === "alphanumeric_digits_first") {
      const digits = "0123456789";
      const all = "abcdefghijklmnopqrstuvwxyz0123456789";
      const names = [];
      for (let a of digits) for (let b of all) for (let c of all) for (let d of all) names.push(a + b + c + d);
      return names;
    }

    // 3. Fetch from backend /api/candidates endpoint
    try {
      const res = await bridgeRequest("/api/candidates", {
        source: source,
        pattern: pattern,
        limit: 15000
      });
      if (res && res.candidates && res.candidates.length > 0) {
        return res.candidates;
      }
    } catch (e) {
      console.warn("Backend candidate API unavailable, falling back to local generator", e);
    }

    // 3. Fallback client-side generator
    const c = ["z","v","k","x","j","q","w","b","m","d","l","n","p","r","s","t"];
    const v = ["a","e","i","o","u"];
    const names = [];

    if (source === "wildcard_z" || (pattern && pattern.startsWith("z"))) {
      for (let c1 of c) for (let v1 of v) for (let c2 of c) names.push(`z${c1}${v1}${c2}`);
      return names;
    }

    if (source === "wildcard_vk" || (pattern && pattern.startsWith("vk"))) {
      for (let c1 of (c.concat(v))) for (let c2 of (c.concat(v))) names.push(`vk${c1}${c2}`);
      return names;
    }

    // Default: Pronounceable CVCV
    for (let c1 of c) {
      for (let v1 of v) {
        for (let c2 of c) {
          for (let v2 of v) {
            names.push(`${c1}${v1}${c2}${v2}`);
          }
        }
      }
    }
    return names;
  }

  // Turbo GQL Scanner
  async function startScan(opts = {}) {
    if (isScanning) return;
    const h = await getHeaders();
    if (!h) {
      alert("❌ Could not acquire Twitch session integrity token. Please click into the username box and try again.");
      return;
    }

    const candidates = await getCandidates(opts.source || "pronounceable_4", opts.pattern || "", opts.custom_list || []);
    isScanning = true;
    testedCount = 0;
    currentSpeed = 0.0;
    currentBatch = "";
    let foundHits = [];
    startTime = Date.now();
    updatePill(`⚡ Turbo Scanning (${candidates.length} names)...`, "#00f593");

    const BATCH = 15;
    for (let i = 0; i < candidates.length; i += BATCH) {
      if (!isScanning) break;
      const chunk = candidates.slice(i, i + BATCH);
      currentBatch = chunk.join(", ");

      const payload = chunk.map(name => ({
        operationName: "UsernameValidator_User",
        variables: { username: name },
        extensions: {
          persistedQuery: {
            version: 1,
            sha256Hash: "fd1085cf8350e309b725cf8ca91cd90cac03909a3edeeedbd0872ac912f3d660"
          }
        }
      }));

      try {
        const res = await origFetch("https://gql.twitch.tv/gql", {
          method: "POST",
          headers: h,
          body: JSON.stringify(payload)
        });

        if (res.ok) {
          const data = await res.json();
          const arr = Array.isArray(data) ? data : [data];
          for (let j = 0; j < arr.length; j++) {
            testedCount++;
            if (arr[j]?.data?.isUsernameAvailable === true) {
              const hit = chunk[j];
              if (!foundHits.includes(hit)) {
                foundHits.push(hit);
                try { playSuccessSound(); } catch (e) {}
                try { fillUsername(hit); } catch (e) {}

                // Inform dashboard of hit immediately
                try {
                  await bridgeRequest("/api/bridge/sync", {
                    hit: hit,
                    user: getTwitchUsername(),
                    state: isScanning ? "RUNNING" : "IDLE",
                    tested: testedCount,
                    speed: currentSpeed,
                    batch: currentBatch,
                    version: "v3.0"
                  });
                } catch (e) {}

                if (opts.stop_on_first === true) {
                  isScanning = false;
                  updatePill(`🎉 CLAIMABLE: <strong>${hit}</strong>`, "#00f593");
                  return;
                } else {
                  updatePill(`🎉 HIT (${foundHits.length}): <strong>${hit}</strong> | Searching more...`, "#00f593");
                }
              }
            }
          }
        } else if (res.status === 429) {
          updatePill("⚠️ Rate limited by Twitch, pausing 2s...", "#ffaa00");
          await new Promise(r => setTimeout(r, 2000));
        } else if (res.status === 401 || res.status === 403) {
          // Token / integrity expired - refresh
          capturedHeaders = null;
          h = await getHeaders();
        }
      } catch (e) {}

      const sec = (Date.now() - startTime) / 1000;
      currentSpeed = sec > 0 ? parseFloat((testedCount / sec).toFixed(1)) : 0.0;
      const hitPrefix = foundHits.length > 0 ? `[${foundHits.length} found] ` : "";
      updatePill(`⚡ ${hitPrefix}Scanning: ${testedCount} (${currentSpeed}/s)`, "#00f593");

      await new Promise(r => setTimeout(r, 30)); // 30ms throttle for steady 200+ req/s
    }

    isScanning = false;
    currentBatch = "";
    currentSpeed = 0.0;
    updatePill(`Scan Finished! Found <strong>${foundHits.length}</strong> available names.`, "#00f593");
    try {
      await bridgeRequest("/api/bridge/sync", {
        user: getTwitchUsername(),
        state: "IDLE",
        tested: testedCount,
        speed: 0.0,
        batch: "",
        version: "v3.0"
      });
    } catch (e) {}
  }

  function stopScan() {
    isScanning = false;
    currentSpeed = 0.0;
    currentBatch = "";
    updatePill(`Dashboard Linked: <strong>Stopped</strong>`, "#ffaa00");
  }

  // Fast Two-Way HTTP Sync Loop
  function startSyncLoop() {
    if (syncInterval) clearInterval(syncInterval);

    const syncOnce = async () => {
      try {
        const res = await bridgeRequest("/api/bridge/sync", {
          user: getTwitchUsername(),
          state: isScanning ? "RUNNING" : "IDLE",
          tested: testedCount,
          speed: currentSpeed,
          batch: currentBatch,
          version: "v3.0"
        });

        if (!isConnected) {
          isConnected = true;
          if (!isScanning) {
            updatePill(`Dashboard Linked: <strong>Active v3.0 (${getTwitchUsername()})</strong>`, "#00f593");
          }
        }

        // Process any commands received from dashboard
        if (res && res.command) {
          const cmd = res.command.command;
          const payload = res.command.payload || {};
          if (cmd === "start") {
            startScan(payload);
          } else if (cmd === "stop") {
            stopScan();
          } else if (cmd === "fill" && payload.username) {
            fillUsername(payload.username);
          }
        }
      } catch (err) {
        if (isConnected) {
          isConnected = false;
          updatePill("Dashboard Disconnected (Retrying...)", "#ffaa00");
        }
      }
    };

    // Initial immediate sync
    syncOnce();
    // Then every 400ms
    syncInterval = setInterval(syncOnce, 400);
  }

  startSyncLoop();
})();
