// ETDS Batch Uploader — Bookmarklet source
// This runs inside the Steel City backoffice page when clicked.
// Wrap in: javascript:(async function(){"use strict"; [SOURCE] })()

// Toggle: clicking bookmark again closes the panel
if (document.getElementById("_etds_bm")) {
  document.getElementById("_etds_bm").remove();
  const st = document.getElementById("_etds_bm_style");
  if (st) st.remove();
  return;
}

// ── Inject CSS ─────────────────────────────────────────────────────────────
const _css = document.createElement("style");
_css.id = "_etds_bm_style";
_css.textContent =
  "#_etds_bm{position:fixed;bottom:24px;right:24px;z-index:2147483647;width:390px;background:#fff;border-radius:18px;" +
  "box-shadow:0 8px 40px rgba(0,0,0,.16),0 0 0 1px rgba(0,0,0,.07);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;overflow:hidden;}" +
  "#_etds_bm_hd{display:flex;justify-content:space-between;align-items:center;padding:15px 18px;background:#F8F4F4;border-bottom:1px solid #EDE6E6;}" +
  "#_etds_bm_hd h3{margin:0;font-size:14px;font-weight:700;color:#18100F;display:flex;align-items:center;gap:8px;}" +
  "#_etds_bm_hd h3 span{background:#E04B3E;color:#fff;font-size:10px;padding:2px 8px;border-radius:99px;letter-spacing:.05em;}" +
  "#_etds_bm_close{background:none;border:none;cursor:pointer;color:#A09098;font-size:18px;padding:2px 6px;border-radius:6px;line-height:1;}" +
  "#_etds_bm_close:hover{background:#EDE6E6;color:#18100F;}" +
  "#_etds_bm_body{padding:16px 18px;}" +
  "._eb_hint{font-size:12.5px;color:#6B6070;line-height:1.6;background:#F8F4F4;border:1px solid #EDE6E6;border-radius:8px;padding:10px 12px;margin-bottom:14px;}" +
  "._eb_hint b{color:#18100F;}" +
  "._eb_folder{font-size:12.5px;color:#0E7A57;font-weight:600;margin-bottom:12px;display:none;}" +
  "._eb_row{display:flex;gap:8px;margin-bottom:12px;}" +
  "._eb_btn{flex:1;border:none;border-radius:10px;padding:11px 14px;font-size:13.5px;font-weight:700;cursor:pointer;font-family:inherit;transition:background .15s;}" +
  "._eb_pick{background:#F8F4F4;color:#18100F;border:1.5px solid #E2D4D4;}" +
  "._eb_pick:hover{background:#EDE6E6;}" +
  "._eb_run{background:#E04B3E;color:#fff;box-shadow:0 2px 8px rgba(224,75,62,.3);}" +
  "._eb_run:hover{background:#C73A2E;}" +
  "._eb_run:disabled{background:#D0BFBF;cursor:not-allowed;box-shadow:none;}" +
  "._eb_stop{background:#fff;color:#6B6070;border:1.5px solid #E2D4D4;}" +
  "._eb_stop:hover{background:#F8F4F4;}" +
  "._eb_prog{display:none;}" +
  "._eb_bar_wrap{background:#EDE6E6;border-radius:99px;height:6px;margin-bottom:6px;overflow:hidden;}" +
  "._eb_bar{height:100%;width:0%;background:linear-gradient(90deg,#C73A2E,#E04B3E);border-radius:99px;transition:width .25s;}" +
  "._eb_plabel{font-size:12px;color:#A09098;margin-bottom:10px;}" +
  "._eb_log{max-height:160px;overflow-y:auto;font-size:12px;font-family:ui-monospace,'SF Mono',Menlo,Consolas,monospace;}" +
  "._eb_log_row{padding:3px 0;border-top:1px solid #F2ECEC;display:flex;gap:7px;}" +
  "._eb_log_row:first-child{border-top:none;}" +
  "._ok{color:#0E7A57;flex-shrink:0;}" +
  "._fail{color:#B42318;flex-shrink:0;}" +
  "._warn{color:#92400E;flex-shrink:0;}" +
  "._lname{color:#18100F;word-break:break-all;}" +
  "._lreason{color:#A09098;font-size:11px;flex-shrink:0;}" +
  "._eb_summary{background:#F8F4F4;border:1px solid #EDE6E6;border-radius:8px;padding:12px 14px;font-size:13px;margin-top:12px;display:none;}" +
  "._eb_summary b{display:block;margin-bottom:8px;font-weight:700;}" +
  "._eb_srow{display:flex;justify-content:space-between;padding:2px 0;color:#6B6070;}" +
  "._eb_srow span:last-child{font-weight:700;}" +
  "._s_ok{color:#0E7A57;}._s_fail{color:#B42318;}._s_warn{color:#92400E;}";
document.head.appendChild(_css);

// ── Panel HTML ─────────────────────────────────────────────────────────────
const _panel = document.createElement("div");
_panel.id = "_etds_bm";
_panel.innerHTML =
  '<div id="_etds_bm_hd">' +
    '<h3><span>ETDS</span> Batch Upload</h3>' +
    '<button id="_etds_bm_close" title="Close">&#x2715;</button>' +
  '</div>' +
  '<div id="_etds_bm_body">' +
    '<div class="_eb_hint">Navigate to <b>e-Governance &rarr; TIN Services &rarr; e TDS-TCS</b> first, then pick the folder of renamed PDFs.</div>' +
    '<div class="_eb_folder" id="_eb_folder_info"></div>' +
    '<div class="_eb_row">' +
      '<button class="_eb_btn _eb_pick" id="_eb_pick">&#128193; Pick Folder</button>' +
      '<button class="_eb_btn _eb_run" id="_eb_run" disabled>&#9654; Start Upload</button>' +
    '</div>' +
    '<div class="_eb_prog" id="_eb_prog">' +
      '<div class="_eb_bar_wrap"><div class="_eb_bar" id="_eb_bar"></div></div>' +
      '<div class="_eb_plabel" id="_eb_plabel"></div>' +
      '<div class="_eb_log" id="_eb_log"></div>' +
    '</div>' +
    '<div class="_eb_summary" id="_eb_summary"></div>' +
  '</div>';
document.body.appendChild(_panel);

// ── Helpers ────────────────────────────────────────────────────────────────
const _sleep = ms => new Promise(r => setTimeout(r, ms));

function _waitFor(fn, timeout, interval) {
  timeout = timeout || 15000; interval = interval || 250;
  return new Promise(function(resolve, reject) {
    const end = Date.now() + timeout;
    (function check() {
      const r = fn();
      if (r) return resolve(r);
      if (Date.now() > end) return reject(new Error("Timeout"));
      setTimeout(check, interval);
    })();
  });
}

function _allWins() {
  const wins = [];
  function _c(w) {
    try {
      if (w.document.body) wins.push(w);
      for (let i = 0; i < w.frames.length; i++) _c(w.frames[i]);
    } catch(e) {}
  }
  _c(window);
  return wins;
}

function _findTds() {
  for (const w of _allWins()) {
    try {
      const d = w.document;
      const hasGo = d.querySelector('input[value="GO"],input[value="Go"]');
      const hasRadios = d.querySelectorAll("input[type=radio]").length >= 2;
      if (hasGo && hasRadios) return w;
    } catch(e) {}
  }
  return null;
}

function _findDetail() {
  for (const w of _allWins()) {
    try {
      const d = w.document;
      if (d.querySelector("input[type=file]") &&
          d.querySelector('input[value=Update],input[value=update]')) return w;
    } catch(e) {}
  }
  return null;
}

// Selector helpers with fallbacks
function _clickAckRadio(doc) {
  const strategies = [
    () => [...doc.querySelectorAll("label")].find(l => /ack\s*no/i.test(l.textContent))?.querySelector("input[type=radio]"),
    () => doc.querySelector('input[type=radio][value=AckNo]'),
    () => doc.querySelector('input[type=radio][value="2"]'),
    () => [...doc.querySelectorAll("input[type=radio]")].find(r => /ack\s*no/i.test(r.parentElement?.textContent || "")),
  ];
  for (const fn of strategies) {
    try { const el = fn(); if (el) { el.checked = true; el.click(); el.dispatchEvent(new Event("change", {bubbles:true})); return true; } } catch(e) {}
  }
  return false;
}

function _fillAck(doc, val) {
  const strategies = [
    () => doc.querySelector("input[type=text][name*=Ack],input[type=text][id*=Ack],input[type=text][name*=ack]"),
    () => [...doc.querySelectorAll("input[type=text]")].find(el => el.offsetParent !== null),
  ];
  for (const fn of strategies) {
    try { const el = fn(); if (el) { el.value = val; el.dispatchEvent(new Event("input",{bubbles:true})); el.dispatchEvent(new Event("change",{bubbles:true})); return true; } } catch(e) {}
  }
  return false;
}

function _clickGo(doc) {
  const el = doc.querySelector('input[value="GO"],input[value="Go"]');
  if (el) { el.click(); return true; }
  return false;
}

function _findAknoLink(stem) {
  for (const w of _allWins()) {
    try {
      const link = [...w.document.querySelectorAll("a")].find(a => a.textContent.trim() === stem);
      if (link) return { link, win: w };
    } catch(e) {}
  }
  return null;
}

function _setFile(doc, file) {
  try {
    const input = doc.querySelector("input[type=file]");
    if (!input) return false;
    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
    input.dispatchEvent(new Event("change", {bubbles:true}));
    return true;
  } catch(e) { return false; }
}

function _clickUpdate(doc) {
  const el = doc.querySelector('input[value=Update],input[value=update]');
  if (el) { el.click(); return true; }
  return false;
}

// ── UI helpers ─────────────────────────────────────────────────────────────
function _setBar(pct, label) {
  document.getElementById("_eb_bar").style.width = pct + "%";
  document.getElementById("_eb_plabel").textContent = label;
}

function _logRow(icon, cls, name, reason) {
  const log = document.getElementById("_eb_log");
  const row = document.createElement("div");
  row.className = "_eb_log_row";
  row.innerHTML = '<span class="' + cls + '">' + icon + '</span>' +
    '<span class="_lname">' + name + '</span>' +
    (reason ? '<span class="_lreason">' + reason + '</span>' : "");
  log.appendChild(row);
  log.scrollTop = log.scrollHeight;
}

// ── Event: Close ───────────────────────────────────────────────────────────
document.getElementById("_etds_bm_close").onclick = function() {
  document.getElementById("_etds_bm").remove();
  const st = document.getElementById("_etds_bm_style");
  if (st) st.remove();
};

// ── Event: Pick Folder ─────────────────────────────────────────────────────
let _pdfFiles = [];
let _aborted = false;

document.getElementById("_eb_pick").onclick = async function() {
  if (!window.showDirectoryPicker) {
    alert("Folder picker requires Chrome or Edge 86+. Please update your browser.");
    return;
  }
  try {
    const dir = await window.showDirectoryPicker({ mode: "read" });
    _pdfFiles = [];
    for await (const entry of dir.values()) {
      if (entry.kind === "file" && /\.pdf$/i.test(entry.name)) {
        const file = await entry.getFile();
        _pdfFiles.push({ stem: entry.name.replace(/\.pdf$/i, ""), file });
      }
    }
    _pdfFiles.sort((a, b) => a.stem.localeCompare(b.stem));

    if (!_pdfFiles.length) { alert("No PDF files found in that folder."); return; }

    const info = document.getElementById("_eb_folder_info");
    info.style.display = "block";
    info.textContent = "✓ " + _pdfFiles.length + " PDF(s) from "" + dir.name + """;

    document.getElementById("_eb_run").disabled = false;
  } catch(e) {
    if (e.name !== "AbortError") alert("Could not open folder: " + e.message);
  }
};

// ── Event: Start Upload ────────────────────────────────────────────────────
document.getElementById("_eb_run").onclick = async function() {
  if (!_pdfFiles.length) return;

  _aborted = false;
  document.getElementById("_eb_run").disabled = true;
  document.getElementById("_eb_pick").disabled = true;
  document.getElementById("_eb_prog").style.display = "block";
  document.getElementById("_eb_log").innerHTML = "";
  document.getElementById("_eb_summary").style.display = "none";

  const tdsWin = _findTds();
  if (!tdsWin) {
    alert("Please navigate to e-Governance → TIN Services → e TDS-TCS first, then click Start Upload.");
    document.getElementById("_eb_run").disabled = false;
    document.getElementById("_eb_pick").disabled = false;
    return;
  }

  const masterUrl = tdsWin.location.href;
  const total = _pdfFiles.length;
  let ok = 0, notFound = 0, failed = 0, i = 0;

  for (; i < total; i++) {
    if (_aborted) break;
    const { stem, file } = _pdfFiles[i];
    _setBar(Math.round(i / total * 100), "[" + (i+1) + "/" + total + "]  " + stem);

    try {
      // Re-find TDS form (may have reloaded)
      const tWin = await _waitFor(_findTds, 15000);
      if (!tWin) throw new Error("Lost the TDS TCS form");

      if (!_clickAckRadio(tWin.document)) throw new Error("'Ack No' radio not found");
      if (!_fillAck(tWin.document, stem))  throw new Error("Ack No input not found");
      if (!_clickGo(tWin.document))        throw new Error("GO button not found");

      // Wait for AKNO link to appear in results
      const found = await _waitFor(() => _findAknoLink(stem), 15000);
      if (!found) {
        _logRow("?", "_warn", stem, "not found in backoffice");
        notFound++;
        tWin.location.href = masterUrl;
        await _waitFor(_findTds, 12000);
        continue;
      }

      found.link.click();

      // Wait for detail page with file input
      const dWin = await _waitFor(_findDetail, 15000);
      if (!dWin) throw new Error("Detail page did not load");

      await _sleep(400);
      if (!_setFile(dWin.document, file)) throw new Error("File input not found");

      await _sleep(300);
      if (!_clickUpdate(dWin.document)) throw new Error("Update button not found");

      // Wait for detail page to disappear (navigation away)
      await _sleep(1200);
      await _waitFor(() => !_findDetail(), 12000).catch(() => {});

      _logRow("✓", "_ok", stem, "");
      ok++;

    } catch(err) {
      _logRow("✗", "_fail", stem, err.message);
      failed++;
      try {
        const tw = _findTds();
        if (tw) tw.location.href = masterUrl;
        await _waitFor(_findTds, 10000).catch(() => {});
      } catch(e) {}
    }
  }

  // Summary
  _setBar(100, _aborted ? "Cancelled." : "Done.");
  const sum = document.getElementById("_eb_summary");
  sum.style.display = "block";
  sum.innerHTML =
    "<b>" + (_aborted ? "Cancelled" : "Completed") + " — " + i + " of " + total + " processed</b>" +
    '<div class="_eb_srow"><span>Uploaded</span><span class="_s_ok">' + ok + "</span></div>" +
    '<div class="_eb_srow"><span>Not in backoffice</span><span class="_s_warn">' + notFound + "</span></div>" +
    '<div class="_eb_srow"><span>Errors</span><span class="_s_fail">' + failed + "</span></div>";

  document.getElementById("_eb_run").disabled = false;
  document.getElementById("_eb_pick").disabled = false;
};
