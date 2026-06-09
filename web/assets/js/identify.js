/* Manual identification page — collect title/year/format for unidentified covers. */
(() => {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const queue = {}; // hash -> { title, year, format }

  const source = window.REELSHELF_DATA
    ? Promise.resolve(window.REELSHELF_DATA.unidentified || [])
    : fetch("data/unidentified.json", { cache: "no-store" }).then((r) => (r.ok ? r.json() : []));

  source
    .then((items) => {
      $("#intro").textContent = `${items.length} cover(s) need a title.`;
      if (!items.length) { $("#none").hidden = false; return; }
      const list = $("#list");
      items.forEach((it) => list.appendChild(row(it)));
      updateCount();
    })
    .catch(() => { $("#intro").textContent = "Couldn't load data/unidentified.json."; });

  function row(it) {
    const el = document.createElement("article");
    el.className = "card";
    el.style.cursor = "default";

    const pw = document.createElement("div");
    pw.className = "poster-wrap";
    if (it.thumbnail) {
      const img = document.createElement("img");
      img.loading = "lazy"; img.src = it.thumbnail; img.alt = it.source_image;
      pw.appendChild(img);
    } else {
      const d = document.createElement("div");
      d.className = "poster-fallback";
      d.textContent = it.source_image || "cover";
      pw.appendChild(d);
    }

    const body = document.createElement("div");
    body.className = "card-body";

    const fname = document.createElement("div");
    fname.className = "meta-mini";
    fname.textContent = it.source_image || "";

    const title = input("Title", it.guess_title || "");
    const year = input("Year (optional)", it.guess_year || "");
    year.type = "number"; year.min = "1900"; year.max = "2100";

    const fmt = document.createElement("select");
    ["Unknown", "DVD", "VHS", "Blu-ray"].forEach((f) => {
      const o = document.createElement("option");
      o.value = f; o.textContent = f;
      if ((it.guess_format || "Unknown") === f) o.selected = true;
      fmt.appendChild(o);
    });

    let discarded = false;
    function sync() {
      if (discarded) queue[it.hash] = { delete: true };
      else {
        const t = title.value.trim();
        if (t) queue[it.hash] = { title: t, year: year.value ? Number(year.value) : null, format: fmt.value, requery: true };
        else delete queue[it.hash];
      }
      updateCount();
    }
    [title, year].forEach((i) => i.addEventListener("input", sync));
    fmt.addEventListener("change", sync);

    const actions = document.createElement("div");
    actions.style.cssText = "display:flex;gap:8px;margin-top:8px;align-items:center;";
    const del = document.createElement("button");
    del.className = "btn-mini btn-danger"; del.textContent = "🗑 Discard";
    del.title = "Delete this item from the collection (e.g. a blank tape)";
    del.onclick = () => {
      discarded = !discarded;
      el.style.opacity = discarded ? "0.45" : "1";
      del.textContent = discarded ? "↩ Undo" : "🗑 Discard";
      [title, year, fmt].forEach((x) => { x.disabled = discarded; });
      sync();
    };
    actions.appendChild(del);

    body.append(fname, title, year, fmt, actions);
    el.append(pw, body);
    return el;
  }

  function input(placeholder, value) {
    const i = document.createElement("input");
    i.type = "text"; i.placeholder = placeholder; i.value = value || "";
    i.style.cssText = "padding:9px 11px;border-radius:9px;border:1px solid var(--line);" +
      "background:var(--bg-soft);color:var(--text);font-size:13px;width:100%";
    return i;
  }

  function updateCount() {
    const vals = Object.values(queue);
    const named = vals.filter((v) => !v.delete).length, del = vals.filter((v) => v.delete).length;
    $("#filledCount").textContent = (named || del)
      ? `${named} to identify · ${del} to discard` : "";
  }

  $("#export").addEventListener("click", () => {
    if (!Object.keys(queue).length) { alert("Name or discard at least one item first."); return; }
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(queue, null, 2)], { type: "application/json" }));
    a.download = "identify-queue.json"; a.click(); URL.revokeObjectURL(a.href);
    alert("Downloaded identify-queue.json — drop it into the site's data/ folder, then:\n" +
          "• `reelshelf build` → named items become catalog entries (with your cover photo); discarded items are removed.\n" +
          "• `reelshelf build --online` → also runs DISCOVERY: fetches poster, genres, cast & studio for the names you gave.");
  });
})();
