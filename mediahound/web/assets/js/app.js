/* MediaHound portal — read-only default view + password-gated admin view.
   All fields render on the card (aligned); the only overlay is the image zoom. */
(() => {
  "use strict";

  const SEEN_KEY = "mediahound:seen";
  const CORR_KEY = "mediahound:corrections";
  const LOANS_KEY = "mediahound:loans";
  const COLS_KEY = "mediahound:columns";
  const ADMIN_KEY = "mediahound:admin";
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => [...document.querySelectorAll(s)];

  const ALL_FIELDS = [
    ["poster", "Poster / photos"], ["title", "Title & year"],
    ["meta", "Rating · format · runtime · language"], ["genres", "Genres"],
    ["people", "Director & cast"], ["studio", "Studio & distributor"],
    ["watch", "Where to watch"], ["resale", "Resale value"],
    ["intro", "Intro hook"], ["overview", "Full summary"],
  ];
  const DEFAULT_FIELDS = {
    poster: true, title: true, meta: true, genres: true, people: true,
    studio: true, watch: true, resale: true, intro: true, overview: false,
  };

  let movies = [], site = {}, view = { columns: 4, fields: { ...DEFAULT_FIELDS } };
  let seen = load(SEEN_KEY, {}), corrections = load(CORR_KEY, {}), loans = load(LOANS_KEY, {});
  let isAdmin = sessionStorage.getItem(ADMIN_KEY) === "1";
  let mediaType = "all";                 // "all" | "movie" | "music"
  const imgIndex = new Map();
  const isMusic = (m) => (m.media_type || "movie") === "music";

  if (new URLSearchParams(location.search).get("embed") === "1") document.body.classList.add("embed");

  // Phone mode: an access token may arrive in the URL (?t=…). Stash it for write calls,
  // then strip it from the address bar so it isn't left visible or shared by accident.
  const TOKEN_KEY = "mediahound:token";
  (function () {
    const u = new URLSearchParams(location.search);
    const t = u.get("t");
    if (t) {
      sessionStorage.setItem(TOKEN_KEY, t);
      u.delete("t");
      history.replaceState(null, "", location.pathname + (u.toString() ? "?" + u : "") + location.hash);
    }
  })();
  function authHeaders() {
    const h = { "Content-Type": "application/json" };
    const t = sessionStorage.getItem(TOKEN_KEY);
    if (t) h["X-MediaHound-Token"] = t;
    return h;
  }

  // ---- boot ---------------------------------------------------------------
  const loader = window.MEDIAHOUND_DATA
    ? Promise.resolve(window.MEDIAHOUND_DATA)
    : Promise.all([j("data/site.json", {}), j("data/collection.json", []),
                   j("data/unidentified.json", []), j("data/view-config.json", null)])
        .then(([s, c, u, v]) => ({ site: s, collection: c, unidentified: u, view: v }));

  loader.then((d) => {
    site = d.site || {};
    if (d.view) view = Object.assign(view, d.view, { fields: Object.assign({ ...DEFAULT_FIELDS }, d.view.fields || {}) });
    movies = (d.collection || [])
      .filter((m) => !(corrections[m.id] && corrections[m.id].delete))
      .map(applyCorrection).map(mergeSeen);
    applyLibrary();
    $("#loading").hidden = true;
    setupUnidentified(d.unidentified || []);
    buildFilters();
    wire();
    applyAdminUI();
    render();
    pingServer().then(() => { applyAdminUI(); hydratePersonal(); if (!movies.length) render(); });   // detect `serve --admin`; refresh welcome CTA
  }).catch((e) => { $("#loading").innerHTML = "<p>Couldn't load the collection.</p>"; console.error(e); });

  // ---- helpers ------------------------------------------------------------
  function j(url, fb) { return fetch(url, { cache: "no-store" }).then((r) => r.ok ? r.json() : fb).catch(() => fb); }
  function load(k, fb) { try { return JSON.parse(localStorage.getItem(k)) || fb; } catch { return fb; } }
  function save(k, v) { localStorage.setItem(k, JSON.stringify(v)); }
  function esc(s) { return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
  // only allow http(s) or site-relative URLs in links — blocks javascript:/data: etc. (XSS)
  function safeUrl(u) {
    u = String(u ?? "").trim();
    if (/^https?:\/\//i.test(u)) return u;
    if (/^[a-z][a-z0-9+.\-]*:/i.test(u)) return "#";   // any other scheme → block
    return u;                                          // relative path (posters/…, etc.)
  }
  function trim(s, n) { s = s || ""; return s.length > n ? s.slice(0, n - 1) + "…" : s; }
  function mergeSeen(m) { if (m.id in seen) { m.seen = seen[m.id].seen; m.date_seen = seen[m.id].date_seen; } return m; }
  function applyCorrection(m) {
    const c = corrections[m.id];
    if (c) { if (c.title) m.title = c.title; if (c.year) m.year = c.year; if (c.format) m.format = c.format;
             if (c.media_type) m.media_type = c.media_type; if ("artist" in c) m.artist = c.artist || null;
             if ("studio" in c) m.studio = c.studio || null; if ("distributor" in c) m.distributor = c.distributor || null;
             if (c.default_image) m.poster = c.default_image; m._requery = !!c.requery;
             // personal catalog (admin-only; stripped from the published site)
             m.my_rating = "my_rating" in c ? c.my_rating : null;
             m.my_note = "my_note" in c ? c.my_note : null;
             m.tags = Array.isArray(c.tags) ? c.tags : []; }
    else { m.my_rating = null; m.my_note = null; m.tags = []; }
    applyLoan(m);
    // a movie-only format on a music item (or vice-versa) is wrong — normalise to the type's default
    const valid = FORMATS_BY_TYPE[m.media_type || "movie"];
    if (valid && m.format && !valid.includes(m.format)) m.format = valid[0];
    return m;
  }
  // Lending: an open loan (not yet returned) marks an item "on loan". Admin-only.
  function applyLoan(m) { const l = loans[m.id]; m.loan = (l && !l.returned) ? l : null; return m; }
  function allTags() { return [...new Set(movies.flatMap((m) => m.tags || []))].sort((a, b) => a.localeCompare(b)); }
  function saveCorrections() { save(CORR_KEY, corrections); persist("api/corrections", corrections); }
  function setCorr(m, patch) { corrections[m.id] = Object.assign({}, corrections[m.id], patch); saveCorrections(); }
  // Loans live in their own file (replace-on-write, like seen-overrides) so they stay separate
  // from catalog corrections. Admin-only; loans.json is never published.
  function saveLoans() {
    Object.keys(loans).forEach((k) => { if (!loans[k]) delete loans[k]; });
    save(LOANS_KEY, loans); persist("api/loans", loans);
  }
  function setLoan(m, loan) { if (loan) loans[m.id] = loan; else delete loans[m.id]; saveLoans(); applyLoan(m); }
  // On a served admin session, seed personal data (ratings/notes/tags + loans) from the
  // local data/ files so it shows on any browser — not just the one that made the edits.
  function hydratePersonal() {
    if (!(isAdmin && serverAdmin)) return;
    Promise.all([j("data/corrections.json", {}), j("data/loans.json", {})]).then(([c, l]) => {
      for (const [id, sv] of Object.entries(c || {})) {
        const lv = corrections[id] || (corrections[id] = {});
        ["my_rating", "my_note", "tags"].forEach((k) => { if (lv[k] === undefined && sv[k] !== undefined) lv[k] = sv[k]; });
      }
      loans = Object.assign({}, l || {}, loans);
      movies.forEach(applyCorrection);
      buildFilters(); render();
    });
  }

  // ---- admin-server persistence (mediahound serve --admin) ----------------
  // When the site is served by the local admin server, every edit is written
  // straight into data/ — so it survives the next `mediahound build` with no
  // "Export changes → drop file in" step. Falls back to localStorage-only.
  let serverAdmin = false, phoneMode = false, pingDone = false;
  function pingServer() {
    return j("api/ping", null).then((r) => {
      serverAdmin = !!(r && r.admin); phoneMode = !!(r && r.phone); pingDone = true; return serverAdmin;
    });
  }
  function persist(endpoint, payload) {
    if (!serverAdmin) return;
    fetch(endpoint, { method: "POST", headers: authHeaders(), body: JSON.stringify(payload) })
      .then((r) => r.json()).then((r) => { if (r && r.ok) flashSaved(); })
      .catch(() => {/* offline export still available */});
  }
  function flashSaved() {
    const el = $("#saveState"); if (!el) return;
    el.textContent = "✓ Saved to disk"; el.hidden = false;
    clearTimeout(flashSaved._t); flashSaved._t = setTimeout(() => { el.hidden = true; }, 1600);
  }
  function rebuildSite() {
    const el = $("#saveState"); if (el) { el.textContent = "↻ Rebuilding…"; el.hidden = false; }
    fetch("api/rebuild", { method: "POST", headers: authHeaders(), body: "{}" })
      .then((r) => r.json()).then((r) => {
        if (r && r.ok) { if (el) el.textContent = "✓ Rebuilt — reloading"; location.reload(); }
        else alert("Rebuild failed: " + ((r && r.error) || "unknown"));
      }).catch((e) => alert("Rebuild failed: " + e));
  }
  function doPublish(token) {
    const el = $("#saveState"); if (el) { el.textContent = "🌐 Publishing…"; el.hidden = false; }
    fetch("api/publish", { method: "POST", headers: authHeaders(), body: JSON.stringify(token ? { token } : {}) })
      .then((r) => r.json()).then((r) => {
        if (el) el.hidden = true;
        if (r && r.ok) {
          window.prompt("✓ Published! Copy your shareable link:", r.url);
        } else if (r && r.need_token) {
          const t = window.prompt(
            "Paste a Netlify access token to publish (saved securely in your keychain).\n" +
            "Get one free at netlify.com → User settings → Applications → New access token:");
          if (t && t.trim()) doPublish(t.trim());
        } else {
          alert("Publish failed: " + ((r && r.error) || "unknown"));
        }
      }).catch((e) => { if (el) el.hidden = true; alert("Publish failed: " + e); });
  }
  function openImport() {
    if (!serverAdmin) {
      alert("Bulk import needs the local admin server.\n\nRun:  mediahound serve --admin\n" +
            "…then use this button — or from a terminal:  mediahound import yourlist.csv [--online]");
      return;
    }
    $("#importNote").hidden = true; $("#importDialog").hidden = false;
    setTimeout(() => $("#importCsv").focus(), 30);
  }
  function doImport() {
    const csv = $("#importCsv").value.trim();
    const note = $("#importNote"); note.hidden = false;
    if (!csv) { note.textContent = "Paste or load a CSV first."; return; }
    const online = $("#importOnline").checked;
    note.textContent = online ? "Importing & enriching online — this can take a moment…" : "Importing…";
    fetch("api/import", { method: "POST", headers: authHeaders(),
                          body: JSON.stringify({ csv, online }) })
      .then((r) => r.json()).then((r) => {
        if (r && r.ok) { note.textContent = `✓ Added ${r.added}${r.enriched ? `, enriched ${r.enriched}` : ""} — reloading`; location.reload(); }
        else { note.textContent = "Import failed: " + ((r && r.error) || "unknown"); }
      }).catch((e) => { note.textContent = "Import failed: " + e; });
  }

  // ---- Discogs collection import ------------------------------------------
  function openDiscogs() {
    if (!serverAdmin) {
      alert("Importing from Discogs needs the local app.\n\nRun:  mediahound app\n" +
            "…or from a terminal:  mediahound import-discogs <username>");
      return;
    }
    const user = (window.prompt("Import a Discogs collection — enter the Discogs username:") || "").trim();
    if (!user) return;
    const el = $("#saveState"); if (el) { el.textContent = "💿 Importing from Discogs…"; el.hidden = false; }
    fetch("api/import-discogs", { method: "POST", headers: authHeaders(), body: JSON.stringify({ username: user }) })
      .then((r) => r.json()).then((r) => {
        if (r && r.ok) { if (el) el.textContent = `✓ Imported ${r.added} — reloading`; location.reload(); }
        else { if (el) el.hidden = true; alert("Discogs import failed: " + ((r && r.error) || "unknown")); }
      }).catch((e) => { if (el) el.hidden = true; alert("Discogs import failed: " + e); });
  }

  // ---- Library switcher (open / create / switch the served catalog) -------
  function openLibrary() {
    if (!serverAdmin) {
      alert("Switching libraries needs the local app.\n\nRun:  mediahound app\n(or  mediahound serve --admin)");
      return;
    }
    $("#libraryNote").hidden = true; $("#libraryPath").value = "";
    $("#libraryList").textContent = "Loading…"; $("#libraryDialog").hidden = false;
    j("api/libraries", null).then((r) => {
      if (!r || !r.ok) { $("#libraryList").textContent = "Couldn't load libraries."; return; }
      $("#libraryCurrent").textContent = "Current: " + (r.current && r.current.title ? r.current.title : "(this library)") +
        (r.current && r.current.path ? "  ·  " + r.current.path : "");
      const list = $("#libraryList"); list.innerHTML = "";
      const recent = (r.recent || []).filter((x) => !(r.current && x.path === r.current.path));
      if (!recent.length) { list.innerHTML = '<p class="dialog-sub">No other recent libraries yet.</p>'; return; }
      recent.forEach((lib) => {
        const row = document.createElement("button"); row.className = "library-row";
        row.innerHTML = `<span class="lib-title">${esc(lib.title)}</span><span class="lib-path">${esc(lib.path)}</span>`;
        row.onclick = () => switchLibrary(lib.path, false);
        list.appendChild(row);
      });
    });
  }
  function switchLibrary(path, create) {
    const note = $("#libraryNote"); note.hidden = false;
    note.textContent = (create ? "Creating " : "Opening ") + path + "…";
    fetch(create ? "api/create-library" : "api/switch-library",
          { method: "POST", headers: authHeaders(), body: JSON.stringify({ path }) })
      .then((r) => r.json()).then((r) => {
        if (r && r.ok) { note.textContent = "✓ " + (r.title || "Opened") + " — reloading"; location.reload(); }
        else { note.textContent = "Couldn't switch: " + ((r && r.error) || "unknown"); }
      }).catch((e) => { note.textContent = "Couldn't switch: " + e; });
  }

  // ---- Add photos (drag-and-drop upload) ----------------------------------
  let uploadFiles = [];
  function openUpload() {
    if (!serverAdmin) {
      alert("Adding photos needs the local app.\n\nStart it with:  mediahound app\n(or  mediahound serve --admin)");
      return;
    }
    uploadFiles = []; renderUploadList();
    $("#uploadNote").hidden = true; $("#uploadDialog").hidden = false;
  }
  function addUploadFiles(list) {
    for (const f of list) if (f.type.startsWith("image/")) uploadFiles.push(f);
    renderUploadList();
  }
  function renderUploadList() {
    $("#uploadList").textContent = uploadFiles.length ? `${uploadFiles.length} photo(s) ready` : "";
    $("#uploadGo").disabled = uploadFiles.length === 0;
  }
  function fileToBase64(file) {
    return new Promise((res, rej) => {
      const r = new FileReader();
      r.onload = () => res(String(r.result).split(",", 2)[1]);   // strip the data: prefix
      r.onerror = rej; r.readAsDataURL(file);
    });
  }
  async function doUpload() {
    const note = $("#uploadNote"); note.hidden = false;
    const type = (document.querySelector('input[name="upType"]:checked') || {}).value || "movie";
    $("#uploadGo").disabled = true;
    let ok = 0;
    for (let i = 0; i < uploadFiles.length; i++) {
      const f = uploadFiles[i];
      note.textContent = `Uploading ${i + 1} / ${uploadFiles.length}…`;
      try {
        const data = await fileToBase64(f);
        const r = await fetch("api/upload", { method: "POST", headers: authHeaders(),
          body: JSON.stringify({ filename: f.name, media_type: type, data }) }).then((x) => x.json());
        if (r && r.ok) ok++;
      } catch (e) { /* keep going */ }
    }
    note.textContent = `Cataloguing ${ok} photo(s)… this can take a moment.`;
    fetch("api/rebuild", { method: "POST", headers: authHeaders(), body: "{}" })
      .then((r) => r.json()).then(() => location.reload())
      .catch(() => location.reload());
  }

  // ---- Barcode scan / type → identify the exact release -------------------
  let scanStream = null, scanTimer = null, scanDetector = null;
  function openScan() {
    if (!serverAdmin) {
      alert("Scanning needs the local app.\n\nRun:  mediahound app\n(or  mediahound serve --admin)");
      return;
    }
    $("#scanNote").hidden = true; $("#scanUpc").value = "";
    $("#scanVideo").hidden = true; $("#scanDialog").hidden = false;
    setTimeout(() => $("#scanUpc").focus(), 30);
  }
  async function startCamera() {
    if (!("BarcodeDetector" in window)) {
      $("#scanNote").hidden = false;
      $("#scanNote").textContent = "Live scanning isn't supported in this browser — type the digits instead.";
      return;
    }
    try {
      scanDetector = scanDetector || new window.BarcodeDetector({ formats: ["ean_13", "upc_a", "ean_8", "upc_e"] });
      scanStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      const v = $("#scanVideo"); v.hidden = false; v.srcObject = scanStream; await v.play();
      $("#scanNote").hidden = false; $("#scanNote").textContent = "Point the camera at the barcode…";
      scanTimer = setInterval(async () => {
        try {
          const codes = await scanDetector.detect(v);
          const hit = codes.find((c) => /^\d{8,14}$/.test(c.rawValue || ""));
          if (hit) { $("#scanUpc").value = hit.rawValue; stopCamera(); submitScan(); }
        } catch (e) { /* keep trying */ }
      }, 400);
    } catch (e) {
      $("#scanNote").hidden = false; $("#scanNote").textContent = "Couldn't open the camera — type the digits instead.";
    }
  }
  function stopCamera() {
    if (scanTimer) { clearInterval(scanTimer); scanTimer = null; }
    if (scanStream) { scanStream.getTracks().forEach((t) => t.stop()); scanStream = null; }
    const v = $("#scanVideo"); if (v) { v.srcObject = null; v.hidden = true; }
  }
  function submitScan() {
    const upc = ($("#scanUpc").value || "").replace(/\D/g, "");
    const note = $("#scanNote"); note.hidden = false;
    if (!/^\d{8,14}$/.test(upc)) { note.textContent = "Enter a valid UPC/EAN (8–14 digits)."; return; }
    const type = (document.querySelector('input[name="scanType"]:checked') || {}).value || "music";
    note.textContent = "Looking up " + upc + "…";
    fetch("api/identify-barcode", { method: "POST", headers: authHeaders(), body: JSON.stringify({ upc, media_type: type }) })
      .then((r) => r.json()).then((r) => {
        if (r && r.ok && r.matched) { note.textContent = `✓ ${r.title}${r.artist ? " — " + r.artist : ""} — reloading`; stopCamera(); location.reload(); }
        else if (r && r.ok) { note.textContent = "No match for that barcode. Try the other media type, or add it by photo."; }
        else { note.textContent = "Lookup failed: " + ((r && r.error) || "unknown"); }
      }).catch((e) => { note.textContent = "Lookup failed: " + e; });
  }

  // ---- first-run welcome (empty catalog) ----------------------------------
  function showWelcome() {
    $("#loading").hidden = true; $("#empty").hidden = true; $("#grid").innerHTML = "";
    $("#mediaTabs").hidden = true;
    let w = $("#welcome");
    if (!w) { w = document.createElement("div"); w.id = "welcome"; w.className = "welcome";
      document.querySelector("main.wrap").prepend(w); }
    w.innerHTML =
      '<div class="welcome-card"><div class="welcome-emoji">🎬🎵</div>' +
      "<h2>Your catalog is empty — let's fill it.</h2>" +
      "<p>Add photos of your DVD, VHS, CD &amp; vinyl covers and MediaHound builds your searchable collection.</p>" +
      (serverAdmin
        ? '<button class="btn btn-primary" id="welcomeAdd">➕ Add your first photos</button>'
        : "<p class=\"welcome-hint\">To add photos, start the app with <code>mediahound app</code>.</p>");
    w.hidden = false;
    const add = $("#welcomeAdd");
    if (add) add.onclick = () => { if (!isAdmin) openLogin(); else openUpload(); };
  }
  function galleryOf(m) {
    const removed = (corrections[m.id] && corrections[m.id].removed_images) || [];
    const g = [];
    [m.poster, ...(m.images || [])].forEach((u) => { if (u && !g.includes(u) && !removed.includes(u)) g.push(u); });
    return g;
  }
  function deleteImage(m) {
    const g = galleryOf(m);
    if (g.length <= 1) { alert("Can't delete the last image — a title must keep at least one photo."); return; }
    const cur = g[imgIndex.get(m.id) || 0];
    if (!confirm("Remove this photo from the gallery?")) return;
    const c = corrections[m.id] = Object.assign({}, corrections[m.id]);
    c.removed_images = [...(c.removed_images || []), cur];
    if (m.poster === cur) { const next = g.find((x) => x !== cur); m.poster = next; c.default_image = next; }
    saveCorrections();
    imgIndex.set(m.id, 0);
    render();
  }
  function rotationFor(m, p) { const r = corrections[m.id] && corrections[m.id].rotations; return (r && r[p]) || 0; }

  // ---- columns ------------------------------------------------------------
  function userCols() { const c = parseInt(localStorage.getItem(COLS_KEY) || "", 10); return c || view.columns || 4; }
  function effectiveCols() {
    const w = window.innerWidth, want = userCols();
    if (w < 480) return 1;
    if (w < 720) return Math.min(want, 2);
    if (w < 1100) return Math.min(want, 3);
    return Math.min(want, 8);
  }
  function applyCols() { $("#grid").style.setProperty("--cols", effectiveCols()); $("#colCount").textContent = userCols(); }
  function setCols(n) { n = Math.max(1, Math.min(8, n)); localStorage.setItem(COLS_KEY, String(n)); applyCols(); }

  // ---- filters ------------------------------------------------------------
  const uniq = (a) => [...new Set(a.filter(Boolean))].sort();
  // Filter options reflect the ACTIVE media tab — pick 🎵 Music and the format/genre/label
  // dropdowns narrow to what's in your music (and vice-versa); "All" shows everything.
  function buildFilters() {
    const list = mediaType === "all" ? movies : movies.filter((m) => (m.media_type || "movie") === mediaType);
    fill("#filterFormat", uniq(list.map((m) => m.format)));
    fill("#filterGenre", uniq(list.flatMap((m) => m.genres || [])));
    fill("#filterStudio", uniq([...list.map((m) => m.studio), ...list.map((m) => m.label)]));  // studio (movie) or label (music)
    fill("#filterLanguage", uniq(list.map((m) => m.language)));
    fill("#filterCategory", uniq(list.map((m) => m.category)));
    // Tag/shelf filter — admin-only (personal data); `.admin-only` hides it for public viewers.
    if ($("#filterTag")) fill("#filterTag", uniq(list.flatMap((m) => m.tags || [])));
    const provs = uniq(list.flatMap((m) => ((m.streaming && m.streaming.providers) || []).map((p) => p.name)));
    const ss = clearOptions($("#filterStream"));
    [["any", "▶ On any service"]].concat(provs.map((p) => [p, "▶ " + p])).concat([["none", "Not streaming"]])
      .forEach(([v, l]) => { const o = document.createElement("option"); o.value = v; o.textContent = l; ss.appendChild(o); });
  }
  function clearOptions(el) { while (el.options.length > 1) el.remove(1); return el; }  // keep the "All …" placeholder
  function fill(sel, vals) {
    const el = clearOptions($(sel));
    vals.forEach((v) => { const o = document.createElement("option"); o.value = v; o.textContent = v; el.appendChild(o); });
  }
  function setupUnidentified(u) { const n = u.length, l = $("#unidentifiedLink"); if (n > 0) { l.textContent = `⚠ ${n} unidentified`; l.dataset.has = "1"; } }

  function currentView() {
    const q = $("#search").value.trim().toLowerCase();
    const f = $("#filterFormat").value, g = $("#filterGenre").value, st = $("#filterStudio").value;
    const l = $("#filterLanguage").value, c = $("#filterCategory").value, s = $("#filterSeen").value;
    const sv = $("#filterStream").value;
    const tag = ($("#filterTag") && $("#filterTag").value) || "";
    const loan = ($("#filterLoan") && $("#filterLoan").value) || "";
    let v = movies.filter((m) => {
      if (mediaType !== "all" && (m.media_type || "movie") !== mediaType) return false;
      if (f && m.format !== f) return false;
      if (g && !(m.genres || []).includes(g)) return false;
      if (st && m.studio !== st && m.label !== st) return false;   // studio (movie) or label (music)
      if (l && m.language !== l) return false;
      if (c && m.category !== c) return false;
      if (isAdmin && tag && !(m.tags || []).includes(tag)) return false;
      if (isAdmin && loan === "out" && !m.loan) return false;
      if (isAdmin && loan === "available" && m.loan) return false;
      if (sv) {
        const ps = ((m.streaming && m.streaming.providers) || []).map((p) => p.name);
        if (sv === "any" && !ps.length) return false;
        else if (sv === "none" && ps.length) return false;
        else if (sv !== "any" && sv !== "none" && !ps.includes(sv)) return false;
      }
      if (s === "seen" && !m.seen) return false;
      if (s === "unseen" && m.seen) return false;
      if (q) { const hay = [m.title, m.intro, m.overview, (m.genres || []).join(" "), m.language,
        String(m.year), m.director, (m.actors || []).join(" "), m.studio, m.distributor,
        m.artist, m.label, (m.tracklist || []).join(" ")].join(" ").toLowerCase();
        if (!hay.includes(q)) return false; }
      return true;
    });
    const cmp = {
      "title": (a, b) => (a.title || "").localeCompare(b.title || ""),
      "year-desc": (a, b) => (b.year || 0) - (a.year || 0),
      "year-asc": (a, b) => (a.year || 0) - (b.year || 0),
      "added": (a, b) => String(b.added_at || "").localeCompare(String(a.added_at || "")),
      "value-desc": (a, b) => (b.resale?.mid || 0) - (a.resale?.mid || 0),
      "rating-desc": (a, b) => (b.rating || 0) - (a.rating || 0),
      "myrating-desc": (a, b) => (b.my_rating || 0) - (a.my_rating || 0),
    }[$("#sort").value];
    return v.sort(cmp);
  }

  function render() {
    // First run: empty catalog → a friendly welcome instead of a bare grid.
    if (!movies.length) { showWelcome(); return; }
    $("#welcome") && ($("#welcome").hidden = true);
    // show the 🎬/🎵 switch only when the catalog actually mixes types (recomputed after edits)
    $("#mediaTabs").hidden = new Set(movies.map((m) => m.media_type || "movie")).size < 2;
    const v = currentView();
    const grid = $("#grid");
    grid.innerHTML = "";
    grid.classList.toggle("admin", isAdmin);
    $("#empty").hidden = v.length !== 0;
    // apply field-visibility flags as body classes (drives alignment via CSS)
    ALL_FIELDS.forEach(([k]) => document.body.classList.toggle(`hide-${k}`, !view.fields[k]));
    v.forEach((m) => grid.appendChild(card(m)));
    applyCols();
    $("#resultCount").textContent = `${v.length} of ${movies.length} titles · ${movies.filter((m) => m.seen).length} seen`;
    const tot = movies.reduce((s, m) => s + (m.resale?.mid || 0), 0);
    $("#headerStats").innerHTML = `${movies.length} titles<br>est. value ~$${Math.round(tot).toLocaleString()}`;
  }

  // ---- card (all fields, aligned) ----------------------------------------
  function fieldOn(k) { return view.fields[k]; }

  function card(m) {
    const el = document.createElement("article");
    el.className = "card";

    if (fieldOn("poster")) el.appendChild(posterEl(m));

    const b = document.createElement("div");
    b.className = "card-body";

    if (fieldOn("title")) {
      const t = lineEl("title");
      t.innerHTML = `<span class="ttl">${esc(m.title)}</span>` + (m.year ? ` <span class="yr">${m.year}</span>` : "");
      if (isAdmin) { const s = t.querySelector(".ttl"); s.style.cursor = "pointer"; s.title = "Click to edit"; s.addEventListener("click", () => editCard(m, el)); }
      b.appendChild(t);
    }
    if (fieldOn("meta")) {
      const parts = isMusic(m)
        ? [m.rating ? "★ " + m.rating : null, m.format, (m.tracklist && m.tracklist.length) ? m.tracklist.length + " tracks" : null].filter(Boolean)
        : [m.rating ? "★ " + m.rating : null, m.format, m.runtime ? m.runtime + " min" : null, m.language].filter(Boolean);
      b.appendChild(line("meta", parts.join(" · ")));
    }
    if (fieldOn("genres")) {
      const g = lineEl("genres");
      (m.genres || []).slice(0, 4).forEach((x) => g.appendChild(chip(x, () => setFilter("#filterGenre", x))));
      b.appendChild(g);
    }
    if (fieldOn("people")) {
      const p = lineEl("people");
      if (isMusic(m)) {
        if (m.artist) p.appendChild(person("🎤 " + m.artist, m.artist));
        if (m.tracklist && m.tracklist.length) p.title = m.tracklist.join("  ·  ");
      } else {
        if (m.director) p.appendChild(person("🎬 " + m.director, m.director));
        (m.actors || []).slice(0, 4).forEach((a) => p.appendChild(person(a, a)));
        const full = [m.director ? "Dir: " + m.director : null, (m.actors || []).join(", ") || null].filter(Boolean).join("  ·  ");
        if (full) p.title = full;
      }
      b.appendChild(p);
    }
    if (fieldOn("studio")) {
      const s = lineEl("studio");
      if (isMusic(m)) {
        if (m.label) { const x = person("🏷 " + m.label, null); x.onclick = () => setFilter("#filterStudio", m.label); s.appendChild(x); }
      } else {
        if (m.studio) { const x = person("🏛 " + m.studio, null); x.onclick = () => setFilter("#filterStudio", m.studio); s.appendChild(x); }
        if (m.distributor) s.insertAdjacentHTML("beforeend", `<span class="dist">${m.studio ? " · " : ""}↗ ${esc(m.distributor)}</span>`);
      }
      b.appendChild(s);
    }
    if (fieldOn("intro")) b.appendChild(line("intro", m.intro || "", true));
    if (fieldOn("overview")) b.appendChild(line("overview", m.overview || "", true));

    // foot: where-to-watch (left) + resale (right) on one line
    const foot = lineEl("foot");
    if (fieldOn("watch")) { const w = document.createElement("span"); w.className = "watch-inline"; w.innerHTML = isMusic(m) ? listenPills(m) : watchPills(m); foot.appendChild(w); }
    if (fieldOn("resale") && m.resale) {
      foot.insertAdjacentHTML("beforeend",
        `<span class="value">${esc(m.resale.display || "")}` +
        (m.resale.sold_listings_url ? ` <a class="sell" target="_blank" rel="noopener" href="${esc(safeUrl(m.resale.sold_listings_url))}">↗</a>` : "") + `</span>`);
    }
    b.appendChild(foot);

    if (isAdmin) { b.appendChild(personalEl(m)); b.appendChild(seenToggle(m)); b.appendChild(adminBar(m, el)); }
    el.appendChild(b);
    return el;
  }

  // ---- personal catalog: my rating / note / tags / loan (admin-only) -------
  function personalEl(m) {
    const d = lineEl("personal");
    // ★ my rating — 1..10, click a star to set, click the active high star again to clear
    const stars = document.createElement("div"); stars.className = "my-stars";
    stars.title = "Your rating (1–10)";
    for (let n = 1; n <= 10; n++) {
      const s = document.createElement("button");
      s.className = "my-star" + (m.my_rating >= n ? " on" : "");
      s.textContent = "★"; s.dataset.n = n; s.setAttribute("aria-label", `${n} of 10`);
      s.onclick = () => { const v = (m.my_rating === n) ? null : n; setCorr(m, { my_rating: v }); applyCorrection(m); render(); };
      stars.appendChild(s);
    }
    const num = document.createElement("span"); num.className = "my-star-num";
    num.textContent = m.my_rating ? m.my_rating + "/10" : "";
    stars.appendChild(num);
    d.appendChild(stars);

    // tags / shelves
    const tags = document.createElement("div"); tags.className = "my-tags";
    (m.tags || []).forEach((t) => {
      const c = document.createElement("button"); c.className = "my-tag";
      c.textContent = t; c.title = "Filter by this shelf";
      c.onclick = () => { if ($("#filterTag")) { $("#filterTag").value = t; render(); scrollTop(); } };
      tags.appendChild(c);
    });
    const addTag = document.createElement("button"); addTag.className = "my-tag-add";
    addTag.textContent = "＋ shelf"; addTag.title = "Add a tag / shelf";
    addTag.onclick = () => {
      const t = (window.prompt("Add to shelf / tag:") || "").trim();
      if (!t) return;
      const next = [...new Set([...(m.tags || []), t])];
      setCorr(m, { tags: next }); applyCorrection(m); buildFilters(); render();
    };
    tags.appendChild(addTag);
    d.appendChild(tags);

    // note
    if (m.my_note) {
      const note = document.createElement("div"); note.className = "my-note"; note.textContent = m.my_note;
      note.title = "Click to edit your note"; note.onclick = () => editNote(m);
      d.appendChild(note);
    } else {
      const add = document.createElement("button"); add.className = "my-note-add";
      add.textContent = "✎ Add a note"; add.onclick = () => editNote(m);
      d.appendChild(add);
    }

    // loan status
    const loanRow = document.createElement("div"); loanRow.className = "my-loan";
    if (m.loan) {
      loanRow.innerHTML = `<span class="loan-out">📤 Out to ${esc(m.loan.to || "someone")}` +
        (m.loan.since ? ` · since ${esc(m.loan.since)}` : "") + `</span>`;
      const back = document.createElement("button"); back.className = "btn-mini"; back.textContent = "↩ Returned";
      back.onclick = () => { setLoan(m, null); render(); };
      loanRow.appendChild(back);
    } else {
      const out = document.createElement("button"); out.className = "btn-mini"; out.textContent = "📤 Loan out";
      out.onclick = () => {
        const who = (window.prompt(`Lend “${m.title}” to:`) || "").trim();
        if (!who) return;
        setLoan(m, { to: who, since: new Date().toISOString().slice(0, 10), returned: false }); render();
      };
      loanRow.appendChild(out);
    }
    d.appendChild(loanRow);
    return d;
  }
  function editNote(m) {
    const cur = m.my_note || "";
    const next = window.prompt("Your private note (saved to data/, never published):", cur);
    if (next === null) return;
    setCorr(m, { my_note: next.trim() || null }); applyCorrection(m); render();
  }

  function lineEl(key) { const d = document.createElement("div"); d.className = "f f-" + key; return d; }
  function line(key, text, clamp) {
    const d = lineEl(key); if (clamp) d.classList.add("clamp");
    d.textContent = text; if (clamp && text) d.title = text; return d;
  }
  function chip(text, on) { const c = document.createElement("button"); c.className = "chip chip-btn"; c.textContent = text; c.onclick = on; return c; }
  function person(label, name) {
    const x = document.createElement("button"); x.className = "person-link"; x.textContent = label;
    if (name) { x.title = name; x.onclick = () => { $("#filterGenre").value = ""; $("#filterStudio").value = ""; $("#search").value = name; render(); scrollTop(); }; }
    return x;
  }
  function watchPills(m) {
    const p = (m.streaming && m.streaming.providers) || [];
    if (!p.length) return "";
    const short = { "Amazon Prime Video": "Prime", "Netflix": "Netflix", "Hulu": "Hulu" };
    return p.map((x) => `<a class="watch-pill watch-yes" target="_blank" rel="noopener" href="${esc(safeUrl(x.url))}" title="${esc(x.name)} — ${esc(x.type_label)}">▶ ${esc(short[x.name] || x.name)}</a>`).join("");
  }
  function listenPills(m) {
    const p = (m.listen && m.listen.providers) || [];
    if (!p.length) return "";
    const short = { "Apple Music": "Apple", "YouTube Music": "YouTube" };
    return p.map((x) => `<a class="watch-pill listen-yes" target="_blank" rel="noopener" href="${esc(safeUrl(x.url))}" title="Listen on ${esc(x.name)}">♫ ${esc(short[x.name] || x.name)}</a>`).join("");
  }
  function seenToggle(m) {
    const d = lineEl("seentoggle");
    const btn = document.createElement("button");
    btn.className = "btn-seen" + (m.seen ? " is-seen" : "");
    btn.textContent = m.seen ? `✓ Seen ${m.date_seen || ""}`.trim() : "Mark as seen";
    btn.onclick = () => toggleSeen(m);
    d.appendChild(btn);
    return d;
  }
  function setFilter(sel, val) { $("#search").value = ""; $(sel).value = val; render(); scrollTop(); }
  function scrollTop() { window.scrollTo({ top: 0, behavior: "smooth" }); }

  // 🎲 Surprise me — pick a random title from what's currently filtered (preferring unseen)
  // and pop it open in the lightbox. Pure client-side; changes no data.
  function surpriseMe() {
    let pool = currentView();
    const unseen = pool.filter((m) => !m.seen);
    if (unseen.length) pool = unseen;
    if (!pool.length) { alert("Nothing matches the current filters to pick from."); return; }
    const m = pool[Math.floor(Math.random() * pool.length)];
    if (galleryOf(m).length) openZoom(m, 0);
    else { $("#search").value = m.title; render(); scrollTop(); }
  }

  function toggleSeen(m) {
    m.seen = !m.seen; m.date_seen = m.seen ? new Date().toISOString().slice(0, 10) : null;
    seen[m.id] = { seen: m.seen, date_seen: m.date_seen }; save(SEEN_KEY, seen);
    persist("api/seen", seen); render();
  }

  // ---- poster with arrows + zoom -----------------------------------------
  function posterEl(m) {
    const gallery = galleryOf(m);
    const pw = document.createElement("div");
    pw.className = "poster-wrap";
    let idx = imgIndex.get(m.id) || 0; if (idx >= gallery.length) idx = 0;
    const img = gallery.length ? document.createElement("img") : null;
    if (img) {
      img.loading = "lazy"; img.src = gallery[idx]; img.alt = m.title; img.className = "rot-" + rotationFor(m, gallery[idx]);
      img.onerror = () => img.replaceWith(fallbackImg(m));
      img.addEventListener("click", () => openZoom(m, imgIndex.get(m.id) || 0));
      pw.appendChild(img);
    } else { pw.appendChild(fallbackImg(m)); }

    const provs = (m.streaming && m.streaming.providers) || [];
    const watchUrl = provs[0] ? provs[0].url : (m.streaming && m.streaming.justwatch_url);
    pw.insertAdjacentHTML("beforeend",
      `<span class="badge-format">${esc(m.format || "—")}</span>` +
      (m.seen ? `<span class="badge-seen">✓</span>` : "") +
      (isAdmin && m.loan ? `<span class="badge-loan" title="On loan to ${esc(m.loan.to || "someone")}">📤</span>` : "") +
      (provs.length ? `<a class="badge-stream" href="${esc(safeUrl(watchUrl))}" target="_blank" rel="noopener" title="Watch on ${esc(provs.map((p) => p.name).join(", "))}" onclick="event.stopPropagation()">▶</a>` : "") +
      `<span class="zoom-hint" title="Click to zoom">⤢</span>`);

    if (gallery.length > 1) {
      pw.insertAdjacentHTML("beforeend",
        `<button class="img-arrow img-prev" aria-label="Previous photo">‹</button>` +
        `<button class="img-arrow img-next" aria-label="Next photo">›</button>` +
        `<span class="img-dots">${idx + 1}/${gallery.length}</span>` +
        (isAdmin ? `<button class="set-default" title="Make this the default image">★</button>` +
                   `<button class="del-image" title="Delete this photo">🗑</button>` : ""));
      const step = (dir) => {
        const ni = ((imgIndex.get(m.id) || 0) + dir + gallery.length) % gallery.length;
        imgIndex.set(m.id, ni); img.src = gallery[ni]; img.className = "rot-" + rotationFor(m, gallery[ni]);
        pw.querySelector(".img-dots").textContent = `${ni + 1}/${gallery.length}`;
      };
      pw.querySelector(".img-prev").addEventListener("click", (e) => { e.stopPropagation(); step(-1); });
      pw.querySelector(".img-next").addEventListener("click", (e) => { e.stopPropagation(); step(1); });
      if (isAdmin) {
        pw.querySelector(".set-default").addEventListener("click", (e) => {
          e.stopPropagation(); const cur = gallery[imgIndex.get(m.id) || 0];
          setCorr(m, { default_image: cur }); m.poster = cur; imgIndex.set(m.id, 0); render();
        });
        pw.querySelector(".del-image").addEventListener("click", (e) => { e.stopPropagation(); deleteImage(m); });
      }
    }
    return pw;
  }
  function fallbackImg(m) { const d = document.createElement("div"); d.className = "poster-fallback"; d.textContent = m.title; return d; }

  // ---- zoom lightbox ------------------------------------------------------
  let zoomState = null;
  function openZoom(m, idx) {
    const g = galleryOf(m); if (!g.length) return;
    zoomState = { m, g, idx: idx % g.length };
    drawZoom();
    $("#lightbox").hidden = false; document.body.style.overflow = "hidden";
  }
  function drawZoom() {
    const { m, g, idx } = zoomState;
    const im = $("#lbImg"); im.src = g[idx]; im.className = "lb-img rot-" + rotationFor(m, g[idx]);
    $("#lbCaption").textContent = `${m.title} — photo ${idx + 1} of ${g.length}`;
    $("#lbPrev").style.visibility = $("#lbNext").style.visibility = g.length > 1 ? "visible" : "hidden";
  }
  function zoomStep(d) { zoomState.idx = (zoomState.idx + d + zoomState.g.length) % zoomState.g.length; drawZoom(); }
  function closeZoom() { $("#lightbox").hidden = true; document.body.style.overflow = ""; zoomState = null; }

  // ---- admin: inline edit + toolbar --------------------------------------
  function adminBar(m, el) {
    const bar = document.createElement("div"); bar.className = "admin-bar";
    bar.innerHTML = `<button class="btn-mini" data-a="edit">✎ Edit</button>` +
                    `<button class="btn-mini" data-a="rotate">⟳ Rotate</button>` +
                    `<button class="btn-mini btn-danger" data-a="del">🗑 Delete</button>`;
    bar.querySelector('[data-a="edit"]').onclick = () => editCard(m, el);
    bar.querySelector('[data-a="del"]').onclick = () => { if (confirm(`Remove “${m.title}”?`)) { setCorr(m, { delete: true }); movies = movies.filter((x) => x.id !== m.id); render(); } };
    bar.querySelector('[data-a="rotate"]').onclick = () => {
      const g = galleryOf(m), p = g[imgIndex.get(m.id) || 0]; if (!p) return;
      const cur = rotationFor(m, p), next = (cur + 90) % 360;
      const c = corrections[m.id] = Object.assign({}, corrections[m.id]);
      c.rotations = Object.assign({}, c.rotations, { [p]: next }); if (next === 0) delete c.rotations[p];
      saveCorrections(); render();
    };
    return bar;
  }
  const FORMATS_BY_TYPE = {
    movie: ["DVD", "VHS", "Blu-ray", "VideoCD", "Unknown"],
    music: ["CD", "Vinyl", "Cassette", "Unknown"],
  };
  function fmtOptions(type, current) {
    return (FORMATS_BY_TYPE[type] || FORMATS_BY_TYPE.movie)
      .map((f) => `<option ${current === f ? "selected" : ""}>${f}</option>`).join("");
  }
  function editCard(m, el) {
    const b = el.querySelector(".card-body");
    if (b.querySelector(".inline-edit")) return;
    const startType = (m.media_type || "movie");
    const ed = document.createElement("div"); ed.className = "inline-edit";
    ed.innerHTML =
      `<input id="e_t" type="text" value="${esc(m.title)}" placeholder="Title">` +
      `<div class="ie-row">` +
        `<select id="e_mt" title="Media type">` +
          `<option value="movie" ${startType === "movie" ? "selected" : ""}>🎬 Movie</option>` +
          `<option value="music" ${startType === "music" ? "selected" : ""}>🎵 Music</option>` +
        `</select>` +
        `<input id="e_y" type="number" value="${esc(m.year || "")}" placeholder="Year">` +
        `<select id="e_f">${fmtOptions(startType, m.format)}</select>` +
      `</div>` +
      `<input id="e_artist" type="text" value="${esc(m.artist || "")}" placeholder="Artist (for music)" ${startType === "music" ? "" : "hidden"}>` +
      `<input id="e_s" type="text" value="${esc(m.studio || "")}" placeholder="Studio / company" ${startType === "music" ? "hidden" : ""}>` +
      `<input id="e_d" type="text" value="${esc(m.distributor || "")}" placeholder="Distributor" ${startType === "music" ? "hidden" : ""}>` +
      `<label class="ie-check"><input id="e_r" type="checkbox"> Re-query internet on next online rebuild</label>` +
      `<div class="ie-row"><button class="btn-mini btn-primary" id="e_save">Save</button><button class="btn-mini" id="e_cancel">Cancel</button></div>`;
    b.appendChild(ed);
    ed.querySelector("#e_t").focus();

    // switching type swaps the format list + relevant fields, and suggests a re-query
    ed.querySelector("#e_mt").addEventListener("change", (e) => {
      const t = e.target.value;
      ed.querySelector("#e_f").innerHTML = fmtOptions(t, t === "music" ? "CD" : "DVD");
      ed.querySelector("#e_artist").hidden = t !== "music";
      ed.querySelector("#e_s").hidden = t === "music";
      ed.querySelector("#e_d").hidden = t === "music";
      if (t !== startType) ed.querySelector("#e_r").checked = true;   // re-enrich with the right provider
    });

    ed.querySelector("#e_save").onclick = () => {
      const title = ed.querySelector("#e_t").value.trim(); if (!title) return;
      const type = ed.querySelector("#e_mt").value;
      const patch = {
        title, media_type: type,
        year: ed.querySelector("#e_y").value ? Number(ed.querySelector("#e_y").value) : null,
        format: ed.querySelector("#e_f").value,
        requery: ed.querySelector("#e_r").checked,
      };
      if (type === "music") patch.artist = ed.querySelector("#e_artist").value.trim();
      else { patch.studio = ed.querySelector("#e_s").value.trim(); patch.distributor = ed.querySelector("#e_d").value.trim(); }
      setCorr(m, patch);
      applyCorrection(m); render();
    };
    ed.querySelector("#e_cancel").onclick = () => render();
  }

  // ---- auth ---------------------------------------------------------------
  async function sha256(s) {
    const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
    return [...new Uint8Array(buf)].map((x) => x.toString(16).padStart(2, "0")).join("");
  }
  function applyLibrary() {
    const t = view.site_title || site.title || "Movie Collection";
    const s = (view.site_subtitle != null ? view.site_subtitle : site.subtitle) || "";
    $("#siteTitle").textContent = t; document.title = t;
    $("#siteSubtitle").textContent = s;
    const bi = $("#brandImg"), bm = $("#brandMark");
    // user logo if set, else the MediaHound hound mark (never the bare ▶ fallback)
    bi.src = view.site_image || "assets/img/mediahound-icon.png";
    bi.hidden = false; bm.hidden = true;
  }
  function applyAdminUI() {
    document.body.classList.toggle("is-admin", isAdmin);
    $$(".admin-only").forEach((e) => { e.hidden = !isAdmin; if (e.id === "unidentifiedLink" && !e.dataset.has) e.hidden = true; });
    $("#adminBtn").textContent = isAdmin ? "🔓 Exit admin" : "🔒 Admin";
    $("#adminBtn").classList.toggle("active", isAdmin);
    $("#adminBadge").hidden = !isAdmin;
    // serve --admin: edits auto-save to disk, so the manual export buttons become optional
    // and a one-click Rebuild appears. Static hosting (no server) keeps the export flow.
    const live = isAdmin && serverAdmin;
    document.body.classList.toggle("server-admin", live);
    const rb = $("#rebuildBtn"); if (rb) rb.hidden = !live;
    const ib = $("#importBtn"); if (ib) ib.hidden = !live;
    const db = $("#discogsBtn"); if (db) db.hidden = !(live && !phoneMode);
    const ab = $("#addPhotosBtn"); if (ab) ab.hidden = !live;
    const sc = $("#scanBtn"); if (sc) sc.hidden = !live;                        // scan works over LAN (phone) too
    const bk = $("#backupBtn"); if (bk) bk.hidden = !(live && !phoneMode);     // full-library download — local only
    const lbn = $("#libraryBtn"); if (lbn) lbn.hidden = !(live && !phoneMode); // switch served library — local only
    const pb = $("#publishBtn"); if (pb) pb.hidden = !(live && !phoneMode);   // publish uses your Netlify token — local only
    if (live) {
      $("#adminBadge").textContent = "● ADMIN — saving to disk";
      const ex = $("#exportChanges"); if (ex) ex.title = "Optional — your edits are already saved to data/ by the server";
    } else {
      $("#adminBadge").textContent = "● ADMIN MODE";
    }
    // Static copy (no admin server): warn that edits live only in THIS browser and won't reach
    // data/ — so opening the same library in the app won't show them. Only after the ping resolves.
    const sw = $("#staticWarn");
    if (sw) sw.hidden = !(isAdmin && pingDone && !serverAdmin);
  }
  function openLogin() { $("#loginErr").hidden = true; $("#loginPw").value = ""; $("#loginDialog").hidden = false; setTimeout(() => $("#loginPw").focus(), 30); }
  // ---- inline help (how to use) -------------------------------------------
  function helpSections() { return $$("#helpDialog .help-sec"); }
  function visibleHelpSections() { return helpSections().filter((d) => !d.hidden); }
  function openHelp() {
    // show the admin tools section only when signed in
    const adminBlock = document.querySelector("#helpDialog .help-admin");
    if (adminBlock) adminBlock.hidden = !isAdmin;
    const note = $("#helpModeNote");
    if (note) note.textContent = isAdmin
      ? "You're in admin mode — the editing tools below are available. Every edit saves to disk."
      : "A quick tour of what you can do here. Unlock 🔒 Admin to edit your catalog and see the editing tools.";
    // reset: clear search, collapse all but the first visible section
    if ($("#helpSearch")) $("#helpSearch").value = "";
    filterHelp("");
    const vis = visibleHelpSections();
    helpSections().forEach((d) => { d.open = false; });
    if (vis[0]) vis[0].open = true;
    $("#helpDialog").hidden = false;
  }
  function setAllHelp(open) { visibleHelpSections().forEach((d) => { d.open = open; }); }
  function filterHelp(q) {
    q = (q || "").trim().toLowerCase();
    let shown = 0;
    helpSections().forEach((d) => {
      const inAdmin = d.closest(".help-admin");
      const adminHidden = inAdmin && !isAdmin;
      const match = !q || d.textContent.toLowerCase().includes(q);
      d.hidden = adminHidden || !match;
      if (!d.hidden) { shown++; if (q) d.open = true; }
    });
    if ($("#helpEmpty")) $("#helpEmpty").hidden = shown !== 0;
  }
  async function tryLogin() {
    const h = await sha256($("#loginPw").value);
    if (h === site.admin_password_sha256) { isAdmin = true; sessionStorage.setItem(ADMIN_KEY, "1"); $("#loginDialog").hidden = true; applyAdminUI(); hydratePersonal(); render(); }
    else $("#loginErr").hidden = false;
  }
  function exitAdmin() { isAdmin = false; sessionStorage.removeItem(ADMIN_KEY); applyAdminUI(); render(); }

  // ---- admin settings (library + field visibility + columns + password) --
  const STOCK_ICONS = [
    ["Play", '<rect width="40" height="40" rx="9" fill="#ff5252"/><path d="M16 13l12 7-12 7z" fill="#fff"/>'],
    ["Film reel", '<rect width="40" height="40" rx="9" fill="#1f2937"/><circle cx="20" cy="20" r="11" fill="none" stroke="#fff" stroke-width="2.5"/><circle cx="20" cy="20" r="2.6" fill="#fff"/><circle cx="20" cy="12.5" r="1.9" fill="#fff"/><circle cx="20" cy="27.5" r="1.9" fill="#fff"/><circle cx="12.5" cy="20" r="1.9" fill="#fff"/><circle cx="27.5" cy="20" r="1.9" fill="#fff"/>'],
    ["Clapperboard", '<rect width="40" height="40" rx="9" fill="#0ea5e9"/><rect x="9" y="18" width="22" height="13" rx="2" fill="#fff"/><path d="M9 13.5l21.6-2.2 0.6 4.9-21.6 2.2z" fill="#111827"/><path d="M13 12.6l-1.4 4M18 12l-1.4 4M23 11.5l-1.4 4M28 11l-1.4 4" stroke="#fff" stroke-width="1.5"/>'],
    ["VHS tape", '<rect width="40" height="40" rx="9" fill="#6d28d9"/><rect x="8" y="13" width="24" height="14" rx="2.5" fill="#fff"/><circle cx="16" cy="20" r="3.2" fill="#6d28d9"/><circle cx="24" cy="20" r="3.2" fill="#6d28d9"/>'],
    ["DVD disc", '<rect width="40" height="40" rx="9" fill="#111827"/><circle cx="20" cy="20" r="11" fill="#aeb4c2"/><circle cx="20" cy="20" r="11" fill="none" stroke="#54c7ec" stroke-width="1"/><circle cx="20" cy="20" r="3.2" fill="#111827"/>'],
    ["Popcorn", '<rect width="40" height="40" rx="9" fill="#f2c14e"/><path d="M13.5 17h13l-1.6 14H15.1z" fill="#fff"/><path d="M13.5 17h13l-.5 4H14z" fill="#ff5252"/><circle cx="15.5" cy="14.5" r="2.8" fill="#fff"/><circle cx="20" cy="12.6" r="3.2" fill="#fff"/><circle cx="24.5" cy="14.5" r="2.8" fill="#fff"/>'],
    ["Camera", '<rect width="40" height="40" rx="9" fill="#0f766e"/><rect x="9" y="16" width="16" height="11" rx="2" fill="#fff"/><path d="M25 19l6-3v9l-6-3z" fill="#fff"/><circle cx="14" cy="13" r="3" fill="#fff"/><circle cx="20" cy="13" r="3" fill="#fff"/>'],
    ["Heart", '<rect width="40" height="40" rx="9" fill="#be123c"/><path d="M20 29s-9-5.6-9-11.5C11 14 13.4 12 16 12c1.8 0 3.3 1 4 2.3.7-1.3 2.2-2.3 4-2.3 2.6 0 5 2 5 5.5C29 23.4 20 29 20 29z" fill="#fff"/>'],
  ];
  function stockDataURL(inner) {
    return "data:image/svg+xml;utf8," + encodeURIComponent(
      '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 40" width="84" height="84">' + inner + "</svg>");
  }
  function populateStock() {
    const wrap = $("#stockIcons");
    if (!wrap || wrap.childElementCount) return; // build once
    STOCK_ICONS.forEach(([name, inner]) => {
      const url = stockDataURL(inner);
      const b = document.createElement("button");
      b.type = "button"; b.className = "stock-icon"; b.title = name;
      b.innerHTML = `<img src="${url}" alt="${esc(name)}">`;
      b.onclick = () => {
        pendingImage = url;
        const p = $("#setImagePreview"); p.src = url; p.hidden = false; $("#clearImage").hidden = false;
      };
      wrap.appendChild(b);
    });
  }

  let pendingImage; // undefined = unchanged, "" = remove, dataURL = new logo
  function openSettings() {
    pendingImage = undefined;
    populateStock();
    $("#setTitle").value = view.site_title || site.title || "";
    $("#setSubtitle").value = (view.site_subtitle != null ? view.site_subtitle : site.subtitle) || "";
    const prev = $("#setImagePreview");
    if (view.site_image) { prev.src = view.site_image; prev.hidden = false; $("#clearImage").hidden = false; }
    else { prev.hidden = true; $("#clearImage").hidden = true; }
    const wrap = $("#fieldToggles"); wrap.innerHTML = "";
    ALL_FIELDS.forEach(([k, label]) => {
      const id = "fld_" + k;
      wrap.insertAdjacentHTML("beforeend",
        `<label class="fld-toggle"><input type="checkbox" id="${id}" ${view.fields[k] ? "checked" : ""}${k === "title" || k === "poster" ? " disabled" : ""}> ${esc(label)}</label>`);
    });
    $("#setColumns").value = view.columns || 4;
    $("#setPassword").value = "";
    $("#settingsPwNote").hidden = true;
    loadApiKeys();
    loadLibraryInfo();
    $("#settingsDialog").hidden = false;
  }

  // ---- library / data folder (in Settings) --------------------------------
  function loadLibraryInfo() {
    // only meaningful with the local admin server (no server → no way to switch the data dir)
    const show = serverAdmin && !phoneMode;
    const block = $("#libraryBlock"); if (block) block.hidden = !show;
    if (!show) return;
    j("api/libraries", null).then((r) => {
      const cur = (r && r.current) || {};
      $("#libCurrentPath").textContent = cur.path || "(this library)";
      $("#libCurrentPath").title = cur.path || "";
    });
  }

  // ---- API keys (stored in the OS keychain by the local app) --------------
  const KEY_NAMES = ["TMDB_API_KEY", "OMDB_API_KEY", "ANTHROPIC_API_KEY", "DISCOGS_TOKEN"];
  function loadApiKeys() {
    // only when the local app is running and NOT exposed to the phone/LAN
    const show = serverAdmin && !phoneMode;
    $("#apiKeysBlock").hidden = !show;
    if (!show) return;
    KEY_NAMES.forEach((n) => { $("#key_" + n).value = ""; });
    $("#keysNote").hidden = true;
    j("api/keys", null).then((r) => {
      const set = (r && r.keys) || {};
      KEY_NAMES.forEach((n) => {
        const el = $("#keyState_" + n); if (!el) return;
        el.textContent = set[n] ? "✓ set" : "not set";
        el.className = "key-state " + (set[n] ? "is-set" : "is-unset");
      });
    });
  }
  function saveApiKeys() {
    const payload = {};
    KEY_NAMES.forEach((n) => { const v = $("#key_" + n).value.trim(); if (v) payload[n] = v; });
    const note = $("#keysNote"); note.hidden = false;
    if (!Object.keys(payload).length) { note.textContent = "Nothing to save (leave blank to keep)."; return; }
    note.textContent = "Saving to keychain…";
    fetch("api/keys", { method: "POST", headers: authHeaders(), body: JSON.stringify(payload) })
      .then((r) => r.json()).then((r) => {
        if (r && r.ok) {
          note.textContent = `✓ Saved: ${(r.changed || []).join(", ")}. Run ↻ Rebuild (online) to use them.`;
          KEY_NAMES.forEach((n) => { $("#key_" + n).value = ""; });
          loadApiKeys();
        } else { note.textContent = "Couldn't save: " + ((r && r.error) || "keychain unavailable"); }
      }).catch((e) => { note.textContent = "Couldn't save: " + e; });
  }
  async function saveSettings() {
    view.site_title = $("#setTitle").value.trim() || null;
    view.site_subtitle = $("#setSubtitle").value.trim();
    if (pendingImage !== undefined) { view.site_image = pendingImage || null; pendingImage = undefined; }
    ALL_FIELDS.forEach(([k]) => { const c = $("#fld_" + k); if (c) view.fields[k] = c.checked; });
    view.fields.title = true; view.fields.poster = true;
    view.columns = Math.max(1, Math.min(8, parseInt($("#setColumns").value, 10) || 4));
    localStorage.removeItem(COLS_KEY); // let new default take effect
    if ($("#setPassword").value.trim()) {
      view._password_sha256 = await sha256($("#setPassword").value.trim());
      site.admin_password_sha256 = view._password_sha256;
      $("#settingsPwNote").textContent = "Password updated locally — included in the exported view-config.json.";
      $("#settingsPwNote").hidden = false;
    }
    applyLibrary(); applyCols(); render();
  }
  function exportSettings() {
    const out = { columns: view.columns, fields: view.fields };
    if (view.site_title) out.site_title = view.site_title;
    if (view.site_subtitle != null) out.site_subtitle = view.site_subtitle;
    if (view.site_image) out.site_image = view.site_image;
    if (view._password_sha256) out.admin_password_sha256 = view._password_sha256;
    download("view-config.json", JSON.stringify(out, null, 2));
    alert("Downloaded view-config.json.\nDrop it into the site's data/ folder so everyone gets these settings (library name, logo, description, fields, columns).");
  }
  function fileToDataURL(file, maxEdge, cb) {
    const r = new FileReader();
    r.onload = () => {
      const im = new Image();
      im.onload = () => {
        const scale = Math.min(1, maxEdge / Math.max(im.width, im.height));
        const c = document.createElement("canvas");
        c.width = Math.round(im.width * scale); c.height = Math.round(im.height * scale);
        c.getContext("2d").drawImage(im, 0, 0, c.width, c.height);
        cb(c.toDataURL("image/png"));
      };
      im.src = r.result;
    };
    r.readAsDataURL(file);
  }

  // ---- exports ------------------------------------------------------------
  async function exportCorrections() {
    if (!Object.keys(corrections).length) { alert("No edits yet."); return; }
    // Merge with the corrections already baked into the site so an export can NEVER
    // silently drop a previously-saved fix (which would make it revert on the next build).
    // Local (this browser's) edits win over the server copy for any shared key.
    const server = await j("data/corrections.json", {});
    const merged = {};
    for (const [k, v] of Object.entries(server)) merged[k] = Object.assign({}, v);
    for (const [k, v] of Object.entries(corrections)) merged[k] = Object.assign({}, merged[k], v);
    download("corrections.json", JSON.stringify(merged, null, 2));
    const n = Object.keys(corrections).length, total = Object.keys(merged).length;
    alert(`Downloaded corrections.json — ${n} edit(s) from this browser, merged with the site's existing ${total - n} so nothing is lost.\n\n` +
          "To make them permanent:\n" +
          "1. Save this file into the site's data/ folder (replace the old corrections.json).\n" +
          "2. Run `mediahound build` and redeploy.\n\n" +
          "Your fixes are now baked into the catalog and survive every future rebuild.");
  }
  function exportSeen() {
    const out = {}; movies.forEach((m) => { if (m.seen) out[m.id] = { seen: true, date_seen: m.date_seen || null }; });
    Object.assign(out, seen); Object.keys(out).forEach((k) => { if (out[k] && !out[k].seen) delete out[k]; });
    download("seen-overrides.json", JSON.stringify(out, null, 2));
    alert("Downloaded seen-overrides.json → drop into data/ and rebuild to make permanent.");
  }
  function download(name, text) { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type: "application/json" })); a.download = name; a.click(); URL.revokeObjectURL(a.href); }
  function downloadCsv(name, text) { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type: "text/csv" })); a.download = name; a.click(); URL.revokeObjectURL(a.href); }

  // ⬇ Backup — stream a zip of the whole library from the local admin server.
  function doBackup() {
    if (!serverAdmin) { alert("Backup needs the local app — run:  mediahound app  (or serve --admin)."); return; }
    const a = document.createElement("a"); a.href = "api/backup"; a.download = ""; a.click();
  }
  // 🎬 Letterboxd — build an import CSV of your movies (Title, Year, Rating10, WatchedDate, Tags)
  // entirely client-side from the loaded catalog + your personal ratings/tags.
  function exportLetterboxd() {
    const csvField = (v) => { v = String(v ?? ""); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
    const rows = [["Title", "Year", "Rating10", "WatchedDate", "Tags"]];
    let n = 0;
    movies.filter((m) => (m.media_type || "movie") === "movie").forEach((m) => {
      rows.push([m.title || "", m.year || "", m.my_rating || "",
                 m.seen ? (m.date_seen || "") : "", (m.tags || []).join(", ")]);
      n++;
    });
    if (!n) { alert("No movies to export."); return; }
    downloadCsv("letterboxd.csv", rows.map((r) => r.map(csvField).join(",")).join("\n"));
    alert(`Exported ${n} movie(s) → letterboxd.csv.\nImport at letterboxd.com/import.`);
  }

  // ---- wiring -------------------------------------------------------------
  function wire() {
    ["#search", "#sort", "#filterFormat", "#filterGenre", "#filterStudio", "#filterStream", "#filterLanguage", "#filterCategory", "#filterSeen", "#filterTag", "#filterLoan"]
      .forEach((s) => { const el = $(s); if (el) el.addEventListener("input", render); });
    if ($("#surpriseBtn")) $("#surpriseBtn").onclick = surpriseMe;
    $$("#mediaTabs .mt-btn").forEach((btn) => btn.addEventListener("click", () => {
      mediaType = btn.dataset.mt;
      $$("#mediaTabs .mt-btn").forEach((b) => b.classList.toggle("is-on", b === btn));
      // narrow the filter dropdowns to the chosen type, resetting any now-irrelevant selection
      ["#filterFormat", "#filterGenre", "#filterStudio", "#filterStream", "#filterLanguage", "#filterCategory", "#filterTag", "#filterLoan"].forEach((s) => { const el = $(s); if (el) el.value = ""; });
      buildFilters();
      render();
    }));
    // only show the Movies/Music switch when the catalog actually mixes media types
    if (new Set(movies.map((m) => m.media_type || "movie")).size < 2) $("#mediaTabs").hidden = true;
    $("#clearFilters").onclick = () => { ["#search", "#filterFormat", "#filterGenre", "#filterStudio", "#filterStream", "#filterLanguage", "#filterCategory", "#filterSeen", "#filterTag", "#filterLoan"].forEach((s) => { const el = $(s); if (el) el.value = ""; }); $("#sort").value = "title"; render(); };
    $("#colMinus").onclick = () => setCols(userCols() - 1);
    $("#colPlus").onclick = () => setCols(userCols() + 1);
    $("#adminBtn").onclick = () => isAdmin ? exitAdmin() : openLogin();
    if ($("#helpBtn")) $("#helpBtn").onclick = openHelp;
    if ($("#helpExpand")) $("#helpExpand").onclick = () => setAllHelp(true);
    if ($("#helpCollapse")) $("#helpCollapse").onclick = () => setAllHelp(false);
    if ($("#helpSearch")) $("#helpSearch").addEventListener("input", (e) => filterHelp(e.target.value));
    $("#exitAdmin").onclick = exitAdmin;
    $("#settingsBtn").onclick = openSettings;
    $("#settingsSave").onclick = saveSettings;
    $("#settingsExport").onclick = exportSettings;
    if ($("#keysSave")) $("#keysSave").onclick = saveApiKeys;
    $("#setImage").addEventListener("change", (e) => {
      const f = e.target.files[0]; if (!f) return;
      fileToDataURL(f, 200, (url) => {
        pendingImage = url;
        const p = $("#setImagePreview"); p.src = url; p.hidden = false; $("#clearImage").hidden = false;
      });
    });
    $("#clearImage").onclick = () => { pendingImage = ""; $("#setImagePreview").hidden = true; $("#clearImage").hidden = true; };
    $("#exportChanges").onclick = exportCorrections;
    if ($("#staticWarnExport")) $("#staticWarnExport").onclick = exportCorrections;
    if ($("#rebuildBtn")) $("#rebuildBtn").onclick = rebuildSite;
    if ($("#importBtn")) $("#importBtn").onclick = openImport;
    if ($("#discogsBtn")) $("#discogsBtn").onclick = openDiscogs;
    if ($("#importGo")) $("#importGo").onclick = doImport;
    if ($("#importFile")) $("#importFile").addEventListener("change", (e) => {
      const f = e.target.files[0]; if (!f) return;
      const rd = new FileReader(); rd.onload = () => { $("#importCsv").value = rd.result; }; rd.readAsText(f);
    });
    // Add photos (upload + drag-drop)
    if ($("#addPhotosBtn")) $("#addPhotosBtn").onclick = openUpload;
    if ($("#scanBtn")) $("#scanBtn").onclick = openScan;
    if ($("#scanCamera")) $("#scanCamera").onclick = startCamera;
    if ($("#scanGo")) $("#scanGo").onclick = submitScan;
    if ($("#scanUpc")) $("#scanUpc").addEventListener("keydown", (e) => { if (e.key === "Enter") submitScan(); });
    if ($("#publishBtn")) $("#publishBtn").onclick = () => doPublish();
    if ($("#libraryBtn")) $("#libraryBtn").onclick = openLibrary;
    if ($("#settingsManageLib")) $("#settingsManageLib").onclick = () => { $("#settingsDialog").hidden = true; openLibrary(); };
    if ($("#libraryOpen")) $("#libraryOpen").onclick = () => { const p = $("#libraryPath").value.trim(); if (p) switchLibrary(p, false); };
    if ($("#libraryCreate")) $("#libraryCreate").onclick = () => { const p = $("#libraryPath").value.trim(); if (p) switchLibrary(p, true); };
    if ($("#uploadGo")) $("#uploadGo").onclick = doUpload;
    if ($("#uploadFiles")) $("#uploadFiles").addEventListener("change", (e) => addUploadFiles(e.target.files));
    const dz = $("#dropZone");
    if (dz) {
      ["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); }));
      ["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); }));
      dz.addEventListener("drop", (e) => { if (e.dataTransfer && e.dataTransfer.files) addUploadFiles(e.dataTransfer.files); });
    }
    $("#exportSeen").onclick = exportSeen;
    if ($("#backupBtn")) $("#backupBtn").onclick = doBackup;
    if ($("#exportLetterboxd")) $("#exportLetterboxd").onclick = exportLetterboxd;
    $("#loginGo").onclick = tryLogin;
    $("#loginPw").addEventListener("keydown", (e) => { if (e.key === "Enter") tryLogin(); });
    $("#lbPrev").onclick = () => zoomStep(-1);
    $("#lbNext").onclick = () => zoomStep(1);
    // dialog + lightbox close
    $$("[data-close]").forEach((e) => e.addEventListener("click", () => { closeZoom(); stopCamera(); $("#loginDialog").hidden = true; $("#settingsDialog").hidden = true; $("#importDialog").hidden = true; $("#uploadDialog").hidden = true; $("#scanDialog").hidden = true; $("#libraryDialog").hidden = true; $("#helpDialog").hidden = true; }));
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { closeZoom(); stopCamera(); $("#loginDialog").hidden = true; $("#settingsDialog").hidden = true; $("#importDialog").hidden = true; $("#uploadDialog").hidden = true; $("#scanDialog").hidden = true; $("#libraryDialog").hidden = true; $("#helpDialog").hidden = true; }
      if (zoomState && e.key === "ArrowLeft") zoomStep(-1);
      if (zoomState && e.key === "ArrowRight") zoomStep(1);
    });
    window.addEventListener("resize", applyCols);
  }
})();
