// ANCHOR browser demo.
//
// Runs the real Python core (anchor/core.py) inside the browser with Pyodide.
// The page's /api/ requests are answered by anchor/api.py right here, so the
// demo uses the same code path as the local server and nothing leaves the
// browser. Data is kept in this browser's IndexedDB between visits.

(() => {
  const config = window.ANCHOR_DEMO || {};
  const PYODIDE_URL = config.pyodideUrl || "https://cdn.jsdelivr.net/pyodide/v0.29.5/full/";
  const DATA_DIR = "/data";
  const DB_PATH = DATA_DIR + "/anchor.db";

  let pyodide = null;
  let handleJson = null;
  let saved = true; // false when IndexedDB is not available (private windows, etc.)

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = src;
      s.onload = resolve;
      s.onerror = () => reject(new Error("could not load " + src));
      document.head.appendChild(s);
    });
  }

  function sync(populate) {
    return new Promise((resolve) => {
      pyodide.FS.syncfs(populate, (err) => {
        if (err) saved = false;
        resolve();
      });
    });
  }

  async function start() {
    await loadScript(PYODIDE_URL + "pyodide.js");
    pyodide = await loadPyodide({ indexURL: PYODIDE_URL });
    const [src] = await Promise.all([
      fetch("anchor-src.json" + (config.version ? "?v=" + config.version : "")).then((r) => r.json()),
      pyodide.loadPackage("sqlite3"),
    ]);

    pyodide.FS.mkdirTree("/app/anchor");
    for (const [name, text] of Object.entries(src)) pyodide.FS.writeFile("/app/anchor/" + name, text);

    pyodide.FS.mkdirTree(DATA_DIR);
    try {
      pyodide.FS.mount(pyodide.FS.filesystems.IDBFS, {}, DATA_DIR);
      await sync(true);
    } catch (e) {
      saved = false;
    }

    pyodide.runPython(`
import os, sys
sys.path.insert(0, "/app")
from anchor.api import handle_json
from anchor.core import Store
from anchor.seed import seed

DB_PATH = ${JSON.stringify(DB_PATH)}

def open_store(fresh=False):
    global store
    if fresh:
        for suffix in ("", "-wal", "-shm", "-journal"):
            if os.path.exists(DB_PATH + suffix):
                os.remove(DB_PATH + suffix)
    new = not os.path.exists(DB_PATH)
    try:
        store = Store(DB_PATH)
    except Exception:
        if fresh:
            raise
        # Saved data this version cannot open, for example from an older
        # demo. Start fresh with the sample team rather than fail to load.
        return open_store(fresh=True)
    if new:
        seed(store)

def api(method, path, body):
    return handle_json(store, method, path, body)

open_store()
`);
    handleJson = pyodide.globals.get("api");
    await sync(false);
  }

  const ready = start();

  let saveTimer = null;
  function scheduleSave() {
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => sync(false), 200);
  }

  // Answer the page's /api/ requests in the browser. Everything else is a normal fetch.
  const realFetch = window.fetch.bind(window);
  window.fetch = async (input, init = {}) => {
    if (typeof input !== "string" || !input.startsWith("/api/")) return realFetch(input, init);
    await ready;
    const method = (init.method || "GET").toUpperCase();
    const { status, data } = JSON.parse(handleJson(method, input, init.body || ""));
    if (method === "POST") scheduleSave();
    return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json" } });
  };

  // Reset works even when loading failed: then it clears the saved data
  // directly, and the reload starts fresh.
  async function reset() {
    if (!confirm("Reset the demo? This clears your changes and reloads the sample workspace.")) return;
    try {
      await ready;
      pyodide.globals.get("open_store")(true);
      await sync(false);
    } catch (e) {
      await new Promise((done) => {
        try {
          const req = indexedDB.deleteDatabase(DATA_DIR);
          req.onsuccess = req.onerror = req.onblocked = () => done();
        } catch (err) { done(); }
      });
    }
    try { localStorage.removeItem("anchor-me"); } catch (e) {}
    location.hash = "";
    location.reload();
  }

  document.addEventListener("DOMContentLoaded", () => {
    const banner = document.createElement("div");
    banner.className = "demo-banner";
    banner.innerHTML = `
      <div><b>Demo.</b> This runs entirely in your browser. Nothing you type leaves your device.
        <span id="demo-status">Loading (the first visit takes a few seconds)...</span></div>
      <div class="demo-tips">Try it: open the workspace and pick Map or Flow at the top. Tap a block to see
        what it is based on. Under To do, start a Focus session to resolve a conflict or check blocks.
        Be Jordan to check your AI drafts, or Sam (an SME) to check other people's blocks. Switch person any time at the top.</div>
      <div class="row"><button id="demo-reset" type="button">Reset demo</button>
        <a href="https://github.com/mitchh14/amped-insights">Source on GitHub</a></div>`;
    document.body.prepend(banner);
    document.getElementById("demo-reset").onclick = reset;

    const status = document.getElementById("demo-status");
    ready.then(
      () => { status.textContent = saved ? "Your changes are saved in this browser." : "Changes last until you close this tab."; },
      (e) => { status.className = "err"; status.textContent = "The demo could not load: " + e.message; },
    );
  });
})();
