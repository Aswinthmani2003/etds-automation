# ETDS Automation — Amirtharaj Investment
## Project Context for Claude

---

## What this project is

Two-phase automation for uploading TDS acknowledgment PDFs to Steel City backoffice.

- **Phase 1** (`etds-renamer.html`) — **COMPLETE. DO NOT TOUCH.**
  Reads ETDS Excel report + scanned PDFs → decodes Code 128 barcodes → renames each PDF to its 15-digit receipt number. Runs entirely in the browser. Nothing uploaded anywhere.

- **Phase 2** — Upload renamed PDFs to `backoffice.steelcitynettrade.com`.
  Current working solution: **bookmarklet inside `etds-renamer.html`** (Phase 2 section at bottom).

---

## Files

| File | Purpose |
|---|---|
| `etds-renamer.html` | Phase 1 renamer + Phase 2 bookmarklet drag link |
| `upload_etds.py` | Playwright CDP script (kept but NOT the primary solution) |
| `run_uploader.bat` | Launcher for the Playwright script |
| `setup_uploader.bat` | One-time Playwright install |

---

## Phase 2 — Current Working Approach: Bookmarklet

The bookmarklet is embedded in `etds-renamer.html`. The user drags the **ETDS Upload** button to their Chrome bookmarks bar once, then clicks it on the Steel City TDS page.

**Why it works:**
- Uses `DataTransfer` API to set the file on `<input type=file>`
- Clicks the Update button directly (normal form POST)
- **No `fetch()` calls** → no CSP restrictions
- Runs entirely inside the user's existing browser session (already logged in)

**Flow the bookmarklet automates:**
1. Find TDS search frame (searches all `window.frames` in the frameset)
2. Click "Ack No" radio button
3. Type receipt number (PDF filename without .pdf) into text input
4. Click GO button
5. Find and click the AKNO result link
6. Wait for detail page with `<input type=file>`
7. Set file via `DataTransfer` → `input.files = dt.files`
8. Click Update button
9. Navigate frame back to TDS search URL
10. Repeat for next PDF

---

## Steel City Site Architecture (critical)

- URL: `https://backoffice.steelcitynettrade.com/backoffice/SCwbb/Default.aspx`
- Uses **`<frameset><frame>`** layout — NOT iframes. Content lives in child frame documents.
- Must use `window.frames` / `page.frames` to access content — `document.querySelector` on the top document finds nothing.
- After login, the app loads in a **new tab/window** opened by the login page.
- Session cookies are scoped to the domain normally.

---

## FAILED Approaches — DO NOT RETRY THESE

### 1. Bookmarklet using `fetch()` to submit forms
**Why it failed:** Steel City CSP blocks `fetch()` from inline scripts.
**Fix applied:** Replaced `fetch()` with `DataTransfer` + button click. This works.

### 2. Playwright with its own Chromium browser (`browser.launch()`)
**Why it failed:** Playwright opens a **fresh Chromium with no session**. The user always logged into their REGULAR Chrome browser (different process, different cookies). Playwright's browser remained unauthenticated.
- Tried: `context.on("page", ...)` listener — only captured the logout page, not the Default.aspx tab
- Tried: `page.goto(Default.aspx)` after login — redirected back to login (no session in Playwright's context)
- Tried: searching all `browser.contexts` for logged-in page — found only 1 page (logout URL)
- **All variants failed for the same reason: two separate browser processes, two separate cookie stores.**

### 3. Playwright connecting to Chrome via CDP (`connect_over_cdp`)
**Why it failed:** Chrome must be fully closed before relaunching with `--remote-debugging-port=9222`. If ANY Chrome process is still running, the new launch opens a window in the existing process — which ignores the debug port flag entirely.
- Error seen: `ECONNREFUSED ::1:9222` (also tried `127.0.0.1:9222`)
- Partially fixed with `taskkill /F /T /IM chrome.exe` (twice) + longer wait, but unreliable.
- **This approach is kept in `upload_etds.py` as a fallback but is NOT recommended.**

---

## Python Environment (if touching the Playwright scripts)

- Two Python installations on this machine:
  - `C:\Users\aswinthmani_v\AppData\Local\Programs\Python\Python311\python.exe` — **has Playwright installed**
  - `C:\Program Files (x86)\wapt\python.exe` — WAPT Python, does NOT have Playwright
- Both bat files hardcode the Python311 path. Do not change this.

---

## Security Constraint

**Files never leave the user's computer.** All barcode decoding, PDF reading, and renaming is local. The only network calls are to `backoffice.steelcitynettrade.com` (the user's own backoffice system).

---

## How to use (normal workflow)

1. Open `etds-renamer.html` in Chrome
2. Upload ETDS Excel report + scanned PDFs → click **Process & Rename**
3. Click **Save to Folder** → pick a folder (e.g. `Downloads\Upload`)
4. Go to Steel City → log in → navigate to **e-Governance → TIN Services → e TDS-TCS**
5. Click **ETDS Upload** bookmark in bookmarks bar
6. Click **Pick Folder** → select the folder from step 3
7. Click **Start Upload** → automation runs, shows live progress
