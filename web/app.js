/**
 * Simplified Twitch Name Sniper Dashboard Logic
 * Direct two-way bridge with Twitch Browser Tab
 */

// DOM Elements
const bridgePill = document.getElementById("bridge-pill");
const bridgeText = document.getElementById("bridge-text");
const controlStateBadge = document.getElementById("control-state-badge");
const btnDashboardStart = document.getElementById("btn-dashboard-start");
const btnDashboardStop = document.getElementById("btn-dashboard-stop");
const selectCandidateSource = document.getElementById("select-candidate-source");
const liveSpeed = document.getElementById("live-speed");
const liveTested = document.getElementById("live-tested");
const liveBatch = document.getElementById("live-batch");
const liveHitsGrid = document.getElementById("live-hits-grid");
const btnClearHits = document.getElementById("btn-clear-hits");
const btnCopyOneliner = document.getElementById("btn-copy-oneliner");

// Custom Pattern and Paste Elements
const customPatternBox = document.getElementById("custom-pattern-box");
const inputCustomPattern = document.getElementById("input-custom-pattern");
const patternCountBadge = document.getElementById("pattern-count-badge");
const customPasteBox = document.getElementById("custom-paste-box");
const textareaCustomNames = document.getElementById("textarea-custom-names");
const pasteCountBadge = document.getElementById("paste-count-badge");

// Quick check elements
const quickCheckForm = document.getElementById("quick-check-form");
const quickInput = document.getElementById("quick-input");
const quickResult = document.getElementById("quick-result");
const qrName = document.getElementById("qr-name");
const qrBadge = document.getElementById("qr-badge");
const qrDesc = document.getElementById("qr-desc");
const btnQuickSubmit = document.getElementById("btn-quick-submit");

const seenHits = new Set();
let isBridgeConnected = false;
let isScanning = false;
let ws = null;

// ----------------- WebSocket Connection -----------------

function initWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    fetchBridgeStatus();
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === "bridge_update" && msg.bridge) {
        updateBridgeUI(msg.bridge);
      }
    } catch (e) {}
  };

  ws.onclose = () => {
    setTimeout(initWebSocket, 2000);
  };
}

// ----------------- Bridge UI Update -----------------

function updateBridgeUI(bridge) {
  if (!bridge) return;

  isBridgeConnected = bridge.connected;
  isScanning = (bridge.state === "RUNNING");

  // Connection Pill
  if (bridge.connected) {
    bridgePill.className = "status-pill online";
    const ver = bridge.bridge_version || "v2.0";
    if (ver === "v3.0") {
      bridgeText.innerHTML = `Twitch Tab: <strong>Linked (${bridge.twitch_user || "Active"} · v3.0 Continuous)</strong>`;
      document.getElementById("bridge-connect-banner").style.borderColor = "rgba(0, 245, 147, 0.4)";
    } else {
      bridgeText.innerHTML = `Twitch Tab: <strong>Linked (${bridge.twitch_user || "Active"})</strong> · <span style="color:#ffaa00;font-weight:700;">Old Script (Please refresh Twitch tab)</span>`;
      document.getElementById("bridge-connect-banner").style.borderColor = "rgba(255, 170, 0, 0.6)";
    }
  } else {
    bridgePill.className = "status-pill offline";
    bridgeText.textContent = "Twitch Tab: Waiting for connection";
  }

  // Scanner state badge & buttons
  if (isScanning) {
    controlStateBadge.className = "scanner-state-tag running";
    controlStateBadge.textContent = "TURBO SCANNING";
    btnDashboardStart.disabled = true;
    btnDashboardStop.disabled = false;
  } else {
    controlStateBadge.className = "scanner-state-tag";
    controlStateBadge.textContent = "IDLE";
    btnDashboardStart.disabled = false;
    btnDashboardStop.disabled = true;
  }

  // Live Stats
  liveSpeed.textContent = bridge.speed ? bridge.speed.toFixed(1) : "0.0";
  liveTested.textContent = bridge.tested ? bridge.tested.toLocaleString() : "0";
  liveBatch.textContent = bridge.current_batch || "-";

  // Hits
  if (bridge.available && bridge.available.length > 0) {
    const emptyMsg = document.getElementById("empty-hits-msg");
    if (emptyMsg) emptyMsg.remove();

    bridge.available.forEach((name) => {
      if (!seenHits.has(name)) {
        seenHits.add(name);
        renderHitCard(name);
      }
    });
  }
}

function renderHitCard(name) {
  const card = document.createElement("div");
  card.className = "hit-card";
  card.innerHTML = `
    <div class="hit-top">
      <span class="hit-name">${name}</span>
      <span class="hit-badge">${name.length} chars</span>
    </div>
    <div class="hit-actions">
      <button class="btn-fill-twitch" data-name="${name}">⚡ Auto-Fill in Tab</button>
      <button class="btn-copy-hit" data-name="${name}">Copy</button>
    </div>
  `;

  // Auto-fill button sends command to Twitch tab
  card.querySelector(".btn-fill-twitch").addEventListener("click", async (e) => {
    const targetName = e.target.dataset.name;
    await sendBridgeCommand("fill", { username: targetName });
    e.target.textContent = "✓ Sent to Tab!";
    setTimeout(() => { e.target.textContent = "⚡ Auto-Fill in Tab"; }, 1500);
  });

  // Copy button
  card.querySelector(".btn-copy-hit").addEventListener("click", (e) => {
    navigator.clipboard.writeText(e.target.dataset.name);
    e.target.textContent = "Copied!";
    setTimeout(() => { e.target.textContent = "Copy"; }, 1500);
  });

  liveHitsGrid.prepend(card);
}

// ----------------- Dashboard Commands to Twitch Tab -----------------

async function sendBridgeCommand(command, payload = {}) {
  try {
    await fetch("/api/bridge/command", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ command, payload })
    });
  } catch (e) {
    console.error("Command error:", e);
  }
}

// ----------------- Candidate Source & Custom Input Handlers -----------------

let patternDebounce = null;
async function updatePatternCount() {
  const pattern = (inputCustomPattern.value || "").trim().toLowerCase();
  if (!pattern || pattern.length < 3) {
    patternCountBadge.textContent = "Enter pattern (min 3 chars)";
    return;
  }
  patternCountBadge.textContent = "Calculating...";
  try {
    const res = await fetch(`/api/candidates?source=custom_pattern&pattern=${encodeURIComponent(pattern)}&limit=10000`);
    if (res.ok) {
      const data = await res.json();
      patternCountBadge.textContent = `${(data.count || 0).toLocaleString()} combinations`;
    }
  } catch (e) {
    patternCountBadge.textContent = "Pattern valid";
  }
}

function updatePasteCount() {
  const raw = textareaCustomNames.value || "";
  const names = raw.split(/[\r\n,]+/).map(s => s.trim().toLowerCase()).filter(s => s.length >= 4);
  pasteCountBadge.textContent = `${names.length.toLocaleString()} valid handles loaded`;
}

if (selectCandidateSource) {
  selectCandidateSource.addEventListener("change", () => {
    const val = selectCandidateSource.value;
    if (val === "custom_pattern") {
      customPatternBox.classList.remove("hidden");
      customPasteBox.classList.add("hidden");
      updatePatternCount();
    } else if (val === "custom_paste") {
      customPasteBox.classList.remove("hidden");
      customPatternBox.classList.add("hidden");
      updatePasteCount();
    } else {
      customPatternBox.classList.add("hidden");
      customPasteBox.classList.add("hidden");
    }
  });
}

if (inputCustomPattern) {
  inputCustomPattern.addEventListener("input", () => {
    clearTimeout(patternDebounce);
    patternDebounce = setTimeout(updatePatternCount, 300);
  });
}

if (textareaCustomNames) {
  textareaCustomNames.addEventListener("input", updatePasteCount);
}

btnDashboardStart.addEventListener("click", async () => {
  if (!isBridgeConnected) {
    const confirmRun = confirm(
      "Notice: Your Twitch tab doesn't report as connected yet.\n\n" +
      "Make sure you have twitch.tv/settings/profile open and pasted the 1-line script or clicked the bookmarklet.\n\n" +
      "Do you want to send the Start command anyway?"
    );
    if (!confirmRun) return;
  }

  const selectedSource = selectCandidateSource.value;
  let customPattern = "";
  let customList = [];

  if (selectedSource === "custom_pattern") {
    customPattern = (inputCustomPattern.value || "").trim().toLowerCase();
    if (!customPattern || customPattern.length < 4) {
      alert("Please enter a wildcard pattern of at least 4 characters (e.g. *god, ??99, z***).");
      return;
    }
  } else if (selectedSource === "custom_paste") {
    const raw = textareaCustomNames.value || "";
    customList = raw.split(/[\r\n,]+/).map(s => s.trim().toLowerCase()).filter(s => s.length >= 4);
    if (!customList.length) {
      alert("Please paste at least one 4+ character username into the text box.");
      return;
    }
  }

  const chkContinuous = document.getElementById("chk-continuous-scan");
  const isContinuous = chkContinuous ? chkContinuous.checked : true;

  await sendBridgeCommand("start", {
    source: selectedSource,
    pattern: customPattern,
    custom_list: customList,
    stop_on_first: !isContinuous
  });
  fetchBridgeStatus();
});

btnDashboardStop.addEventListener("click", async () => {
  await sendBridgeCommand("stop");
  fetchBridgeStatus();
});

btnClearHits.addEventListener("click", () => {
  liveHitsGrid.innerHTML = `
    <div class="empty-hits" id="empty-hits-msg">
      <span>⚡ Available names will appear here as soon as verified.</span>
    </div>
  `;
  seenHits.clear();
});

// ----------------- Quick Copy 1-Liner -----------------

if (btnCopyOneliner) {
  btnCopyOneliner.addEventListener("click", () => {
    const code = 'fetch("http://localhost:5050/static/browser_sniper.js?v=" + Date.now()).then(r=>r.text()).then(eval);';
    navigator.clipboard.writeText(code);
    btnCopyOneliner.textContent = "Copied!";
    setTimeout(() => { btnCopyOneliner.textContent = "Copy"; }, 1500);
  });
}

// ----------------- Quick Single Lookup -----------------

quickCheckForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const username = quickInput.value.trim().toLowerCase();
  if (!username) return;

  btnQuickSubmit.disabled = true;
  btnQuickSubmit.textContent = "Checking...";

  try {
    const resp = await fetch("/api/check-single", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username })
    });
    const res = await resp.json();

    quickResult.classList.remove("hidden");
    qrName.textContent = res.username;
    qrBadge.className = `table-badge ${res.status}`;
    qrBadge.textContent = res.status.toUpperCase();

    if (res.status === "available") {
      qrDesc.innerHTML = `🟢 <strong>${res.username}</strong> has no active user or channel record!`;
    } else if (res.status === "taken") {
      qrDesc.innerHTML = `🔴 <strong>${res.username}</strong> is actively owned by <em>${res.display_name || res.username}</em>.`;
    } else if (res.status === "locked") {
      qrDesc.innerHTML = `🟡 <strong>${res.username}</strong> is held or reserved by Twitch (deactivated or suspended).`;
    } else {
      qrDesc.innerHTML = `⚠️ ${res.reason || "Invalid username syntax."}`;
    }
  } catch (err) {
    alert("Error: " + err.message);
  } finally {
    btnQuickSubmit.disabled = false;
    btnQuickSubmit.textContent = "Check";
  }
});

// ----------------- Periodic Status Polling -----------------

async function fetchBridgeStatus() {
  try {
    const resp = await fetch("/api/bridge/status");
    if (resp.ok) {
      const data = await resp.json();
      updateBridgeUI(data);
    }
  } catch (e) {}
}

// Start polling & WebSocket
initWebSocket();
fetchBridgeStatus();
setInterval(fetchBridgeStatus, 1500);
