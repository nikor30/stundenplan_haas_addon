/*
 * Stundenplan card for Home Assistant.
 *
 * mode: popup (default) - invisible on the dashboard; slides up a sheet while a
 *       kid's pop-up binary sensor is on.
 * mode: inline          - renders the timetable as a normal card.
 *
 * Motion follows Apple's fluid-interface rules: springs instead of fixed-duration
 * animations, 1:1 drag tracking, velocity handoff and momentum projection on
 * release, rubber-banding at the top edge, and cross-fades for reduced motion.
 */

const VERSION = "0.1.3";

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ---------- physics ---------- */

// Apple's two-parameter spring: damping ratio (1 = no overshoot) and response (s).
class Spring {
  constructor({ damping = 1, response = 0.4 } = {}) {
    this.k = (2 * Math.PI / response) ** 2;
    this.c = (4 * Math.PI * damping) / response;
    this.frame = 0;
  }

  // Animates from the current value, so it can be interrupted at any frame.
  run(from, to, velocity, onUpdate, onDone) {
    this.stop();
    let x = from;
    let v = velocity;
    let last = performance.now();
    const tick = (now) => {
      let dt = Math.min((now - last) / 1000, 1 / 20);
      last = now;
      while (dt > 0) {
        const h = Math.min(dt, 1 / 240);
        v += (-this.k * (x - to) - this.c * v) * h;
        x += v * h;
        dt -= h;
      }
      if (Math.abs(x - to) < 0.3 && Math.abs(v) < 4) {
        onUpdate(to);
        this.frame = 0;
        onDone?.();
        return;
      }
      onUpdate(x);
      this.frame = requestAnimationFrame(tick);
    };
    this.frame = requestAnimationFrame(tick);
  }

  stop() {
    if (this.frame) cancelAnimationFrame(this.frame);
    this.frame = 0;
  }
}

// Where a flick would come to rest (UIScrollView deceleration).
const project = (velocity, rate = 0.998) => ((velocity / 1000) * rate) / (1 - rate);

const rubberband = (overshoot, dimension, constant = 0.55) =>
  (overshoot * dimension * constant) / (dimension + constant * Math.abs(overshoot));

/* ---------- timetable rendering (shared by sheet and inline card) ---------- */

const STYLES = `
  :host {
    --sp-font: -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, "Segoe UI", Roboto, sans-serif;
    --sp-text: #1d1d1f;
    --sp-secondary: rgba(60, 60, 67, 0.62);
    --sp-tertiary: rgba(60, 60, 67, 0.32);
    --sp-separator: rgba(60, 60, 67, 0.12);
    --sp-fill: rgba(120, 120, 128, 0.12);
    --sp-material: rgba(250, 250, 252, 0.74);
    --sp-today: rgba(255, 255, 255, 0.9);
    --sp-orange: #ff9500;
    --sp-red: #ff3b30;
    font-family: var(--sp-font);
    color: var(--sp-text);
    -webkit-font-smoothing: antialiased;
  }
  :host([data-theme="dark"]) {
    --sp-text: #f5f5f7;
    --sp-secondary: rgba(235, 235, 245, 0.62);
    --sp-tertiary: rgba(235, 235, 245, 0.3);
    --sp-separator: rgba(84, 84, 88, 0.5);
    --sp-fill: rgba(118, 118, 128, 0.24);
    --sp-material: rgba(30, 30, 32, 0.72);
    --sp-today: rgba(58, 58, 60, 0.85);
    --sp-orange: #ff9f0a;
    --sp-red: #ff453a;
  }

  .head { display: flex; align-items: flex-start; gap: 1rem; }
  .head-text { flex: 1; min-width: 0; }
  .overline {
    margin: 0;
    font-size: 0.8125rem; font-weight: 600; letter-spacing: 0.01em;
    text-transform: uppercase; color: var(--accent);
  }
  .title {
    margin: 0.125rem 0 0;
    font-size: clamp(1.75rem, 3.4vw, 2.25rem); font-weight: 700;
    line-height: 1.08; letter-spacing: -0.022em;
  }
  .subtitle {
    margin: 0.25rem 0 0;
    font-size: 0.9375rem; line-height: 1.35; color: var(--sp-secondary);
    font-variant-numeric: tabular-nums;
  }

  .chips { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.875rem; }
  .chip {
    display: inline-flex; align-items: center; gap: 0.375rem;
    padding: 0.375rem 0.75rem; border-radius: 999px;
    font-size: 0.875rem; font-weight: 600; letter-spacing: -0.005em;
    background: rgba(128, 128, 128, 0.16);
    background: color-mix(in srgb, var(--accent) 14%, transparent);
    color: var(--accent);
  }
  .chip.warn {
    background: rgba(128, 128, 128, 0.16);
    background: color-mix(in srgb, var(--sp-orange) 16%, transparent);
    color: var(--sp-orange);
  }

  .grid {
    position: relative;
    display: grid;
    grid-template-columns: 3.75rem repeat(var(--days), minmax(0, 1fr));
    grid-template-rows: auto repeat(var(--rows), auto);
    column-gap: 0.375rem;
    row-gap: 0.375rem;
    margin-top: 1.25rem;
  }
  .today-col {
    grid-row: 1 / -1;
    margin: -0.375rem -0.1875rem;
    border-radius: 1.125rem;
    background: var(--sp-today);
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06), 0 8px 24px rgba(0, 0, 0, 0.08);
  }
  .day-head {
    z-index: 1;
    padding: 0.25rem 0 0.375rem;
    text-align: center;
    font-size: 0.8125rem; font-weight: 600; color: var(--sp-secondary);
  }
  .day-head .num { display: block; font-size: 1.25rem; font-weight: 600; color: var(--sp-text); letter-spacing: -0.01em; }
  .day-head.today { color: var(--accent); }
  .day-head.today .num {
    display: inline-grid; place-items: center;
    min-width: 2rem; height: 2rem; margin-top: 0.125rem; border-radius: 999px;
    background: var(--accent); color: #fff;
  }
  .time {
    z-index: 1;
    display: flex; flex-direction: column; justify-content: center;
    font-variant-numeric: tabular-nums;
  }
  .time b { font-size: 0.9375rem; font-weight: 600; }
  .time span { font-size: 0.75rem; color: var(--sp-secondary); }
  .time.now b { color: var(--accent); }

  .cell { z-index: 1; display: grid; gap: 0.25rem; min-height: 3.25rem; }
  .cell.past { opacity: 0.45; }
  .cell.dim { opacity: 0.72; }
  .cell.dim .lesson { filter: saturate(0.6); }
  .lesson {
    position: relative;
    display: flex; flex-direction: column; justify-content: center;
    min-width: 0; padding: 0.4375rem 0.625rem 0.4375rem 0.75rem;
    border-radius: 0.75rem;
    background: rgba(128, 128, 128, 0.16);
    background: color-mix(in srgb, var(--c) 15%, transparent);
    overflow: hidden;
  }
  .lesson::before {
    content: ""; position: absolute; inset: 0.4375rem auto 0.4375rem 0.3125rem;
    width: 0.1875rem; border-radius: 999px; background: var(--c);
  }
  .lesson .name {
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    font-size: 0.9375rem; font-weight: 600; line-height: 1.2; letter-spacing: -0.01em;
  }
  .lesson .meta {
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    font-size: 0.75rem; line-height: 1.3; color: var(--sp-secondary);
  }
  .lesson .change { font-size: 0.75rem; font-weight: 600; line-height: 1.3; color: var(--sp-orange); }
  .lesson.cancelled .name { text-decoration: line-through; color: var(--sp-secondary); }
  .lesson.cancelled .change { color: var(--sp-red); }
  .cell.now .lesson { box-shadow: inset 0 0 0 2px var(--accent); }
  .free { border-radius: 0.75rem; }

  .foot {
    margin: 1rem 0 0; font-size: 0.75rem; color: var(--sp-tertiary); text-align: right;
  }
  .empty { padding: 2rem 0; text-align: center; color: var(--sp-secondary); }

  @media (max-width: 640px) {
    .grid { grid-template-columns: 2.75rem repeat(var(--days), minmax(0, 1fr)); column-gap: 0.25rem; }
    .lesson { padding: 0.375rem 0.375rem 0.375rem 0.625rem; }
    .lesson .name { font-size: 0.8125rem; }
    .lesson .meta { display: none; }
  }
`;

const minutes = (hhmm) => {
  const [h, m] = String(hhmm || "").split(":").map(Number);
  return Number.isFinite(h) ? h * 60 + (m || 0) : NaN;
};

function renderTimetable(state, { showHeader = true } = {}) {
  const a = state.attributes;
  const days = a.days || [];
  const periods = a.periods || [];
  const now = new Date();
  const todayIso = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
  const nowMin = now.getHours() * 60 + now.getMinutes();
  const todayIndex = days.findIndex((d) => d.date === todayIso);
  const today = days[todayIndex];

  const todaySlots = (today?.slots || []).map((slot, i) => ({ slot, i })).filter((s) => s.slot.length);
  const first = todaySlots[0] && periods[todaySlots[0].i];
  const last = todaySlots.at(-1) && periods[todaySlots.at(-1).i];
  const changes = (today?.slots || []).flat().filter((l) => l.change).length;

  const dateLabel = now.toLocaleDateString("de-DE", { weekday: "long", day: "numeric", month: "long" });
  const summary = today
    ? todaySlots.length
      ? `${todaySlots.length} ${todaySlots.length === 1 ? "Stunde" : "Stunden"} · ${first.start}–${last.end}`
      : "Heute kein Unterricht"
    : "Kein Schultag";

  const chips = [
    ...(a.today_hints || []).map((h) => `<span class="chip">🎒 ${esc(h)}</span>`),
    changes ? `<span class="chip warn">⚠︎ ${changes} ${changes === 1 ? "Änderung" : "Änderungen"} heute</span>` : "",
  ].join("");

  const head = showHeader
    ? `<div class="head-text">
         <p class="overline">${esc(dateLabel)}</p>
         <h2 class="title">${esc(a.kid || state.attributes.friendly_name)}</h2>
         <p class="subtitle">Klasse ${esc(a.school_class)} · ${esc(summary)}</p>
       </div>`
    : "";

  if (!days.length || !periods.length) {
    return { head, body: `<div class="empty">Kein Stundenplan verfügbar.</div>` };
  }

  const cells = [];
  if (todayIndex >= 0) {
    cells.push(`<div class="today-col" style="grid-column:${todayIndex + 2}"></div>`);
  }
  days.forEach((d, di) => {
    const date = new Date(`${d.date}T00:00:00`);
    const isToday = di === todayIndex;
    cells.push(
      `<div class="day-head${isToday ? " today" : ""}" style="grid-row:1;grid-column:${di + 2}">
         ${esc(isToday ? "Heute" : d.short)}<span class="num">${date.getDate()}</span>
       </div>`,
    );
  });

  periods.forEach((p, pi) => {
    const row = pi + 2;
    const isNow = todayIndex >= 0 && nowMin >= minutes(p.start) && nowMin < minutes(p.end);
    cells.push(
      `<div class="time${isNow ? " now" : ""}" style="grid-row:${row};grid-column:1">
         <b>${p.number}.</b><span>${esc(p.start)}</span>
       </div>`,
    );
    days.forEach((d, di) => {
      const slot = d.slots[pi] || [];
      const isToday = di === todayIndex;
      const classes = ["cell"];
      if (isToday && nowMin >= minutes(p.end)) classes.push("past");
      if (isToday && isNow) classes.push("now");
      if (todayIndex >= 0 && !isToday) classes.push("dim");
      const lessons = slot
        .map((l) => {
          const ch = l.change;
          const meta = [l.room && `Raum ${l.room}`, l.teacher].filter(Boolean).join(" · ");
          const changeText = ch
            ? [ch.cancelled ? ch.kind : ch.subject || ch.kind, ch.teacher, ch.room && `Raum ${ch.room}`]
                .filter(Boolean)
                .join(" · ")
            : "";
          return `<div class="lesson${ch?.cancelled ? " cancelled" : ""}" style="--c:${esc(l.color)}">
              <span class="name">${l.icon ? `${esc(l.icon)} ` : ""}${esc(l.name)}</span>
              ${ch ? `<span class="change">${esc(changeText)}</span>` : meta ? `<span class="meta">${esc(meta)}</span>` : ""}
            </div>`;
        })
        .join("");
      cells.push(
        `<div class="${classes.join(" ")}" style="grid-row:${row};grid-column:${di + 2}">${lessons || '<div class="free"></div>'}</div>`,
      );
    });
  });

  const updated = new Date(state.last_updated).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  return {
    head,
    body: `${chips ? `<div class="chips">${chips}</div>` : ""}
      <div class="grid" style="--days:${days.length};--rows:${periods.length}">${cells.join("")}</div>
      <p class="foot">Aktualisiert ${esc(updated)}</p>`,
  };
}

/* ---------- the sheet that slides up over the dashboard ---------- */

const SHEET_STYLES = `
  :host { position: fixed; inset: 0; z-index: 1000; display: block; pointer-events: none; }
  :host([open]) { pointer-events: auto; }
  .scrim {
    position: absolute; inset: 0;
    background: rgba(0, 0, 0, 0.32);
    opacity: 0;
  }
  .sheet {
    position: absolute; left: 50%; bottom: 1rem;
    width: min(70rem, calc(100vw - 2rem));
    max-height: calc(100vh - 2rem);
    max-height: calc(100dvh - 2rem);
    display: flex; flex-direction: column;
    box-sizing: border-box;
    border-radius: 1.75rem;
    background: var(--sp-material);
    -webkit-backdrop-filter: blur(40px) saturate(180%);
    backdrop-filter: blur(40px) saturate(180%);
    box-shadow:
      inset 0 0.5px 0 rgba(255, 255, 255, 0.5),
      0 0 0 0.5px rgba(0, 0, 0, 0.08),
      0 24px 64px rgba(0, 0, 0, 0.22);
    transform: translate(-50%, 110%);
    will-change: transform;
    --accent: #0a84ff;
  }
  .drag {
    flex: none;
    padding: 0.5rem 1.75rem 0;
    touch-action: none;
    cursor: grab;
    user-select: none;
  }
  .drag:active { cursor: grabbing; }
  .grabber {
    width: 2.25rem; height: 0.3125rem; margin: 0 auto 0.75rem;
    border-radius: 999px; background: var(--sp-tertiary);
  }
  .close {
    flex: none;
    display: grid; place-items: center;
    width: 2.25rem; height: 2.25rem; margin-top: 0.125rem;
    border: 0; border-radius: 999px; padding: 0;
    background: var(--sp-fill); color: var(--sp-secondary);
    font: 600 1rem/1 var(--sp-font);
    cursor: pointer;
    transition: transform 100ms ease-out, background-color 100ms ease-out;
    -webkit-tap-highlight-color: transparent;
  }
  .close:active { transform: scale(0.9); background: var(--sp-separator); }
  .close:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

  .tabs {
    display: inline-flex; gap: 0.125rem; margin-top: 0.875rem; padding: 0.125rem;
    border-radius: 0.5625rem; background: var(--sp-fill);
  }
  .tab {
    border: 0; padding: 0.375rem 1rem; border-radius: 0.4375rem;
    background: transparent; color: var(--sp-text);
    font: 500 0.875rem/1.2 var(--sp-font);
    cursor: pointer; -webkit-tap-highlight-color: transparent;
  }
  .tab[aria-selected="true"] {
    background: var(--sp-today); font-weight: 600;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.12), 0 0 0 0.5px rgba(0, 0, 0, 0.04);
  }
  .tab:active { opacity: 0.6; }

  .content {
    flex: 1; min-height: 0; overflow: auto;
    padding: 0 1.75rem 1.5rem;
    overscroll-behavior: contain;
    transition: opacity 180ms ease;
  }
  .content.switching { opacity: 0; }

  @media (max-width: 640px) {
    .sheet { bottom: 0; width: 100vw; border-radius: 1.5rem 1.5rem 0 0; max-height: 94vh; max-height: 94dvh; }
    .drag { padding: 0.5rem 1rem 0; }
    .content { padding: 0 1rem 1.25rem; }
  }
  @media (prefers-reduced-transparency: reduce) {
    .sheet { -webkit-backdrop-filter: none; backdrop-filter: none; background: var(--sp-today); }
  }
  @media (prefers-contrast: more) {
    .sheet { box-shadow: 0 0 0 1px var(--sp-text); }
  }
`;

class StundenplanSheet extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `
      <style>${STYLES}${SHEET_STYLES}</style>
      <div class="scrim"></div>
      <section class="sheet" role="dialog" aria-modal="true" aria-labelledby="sp-title">
        <div class="drag">
          <div class="grabber" aria-hidden="true"></div>
          <div class="head">
            <div class="head-slot" style="flex:1;min-width:0"></div>
            <button class="close" type="button" aria-label="Schließen">✕</button>
          </div>
          <div class="tabs-slot"></div>
        </div>
        <div class="content"></div>
      </section>`;
    this.$ = (sel) => this.shadowRoot.querySelector(sel);
    this.spring = new Spring({ damping: 1, response: 0.4 });
    this.y = null; // translateY in px; null = hidden
    this.kids = [];
    this.selected = null;
    this.onDismiss = null;

    this.$(".close").addEventListener("click", () => this.dismiss());
    this.$(".scrim").addEventListener("click", () => this.dismiss());
    this.addEventListener("keydown", (e) => e.key === "Escape" && this.dismiss());
    this._bindDrag();
  }

  get height() {
    return this.$(".sheet").getBoundingClientRect().height + 16;
  }

  setTheme(dark) {
    this.toggleAttribute("data-theme", false);
    if (dark) this.setAttribute("data-theme", "dark");
  }

  update(kids) {
    this.kids = kids;
    if (!kids.some((k) => k.entity_id === this.selected)) this.selected = kids[0]?.entity_id;
    const tabs = this.$(".tabs-slot");
    tabs.innerHTML =
      kids.length > 1
        ? `<div class="tabs" role="tablist">${kids
            .map(
              (k) =>
                `<button class="tab" role="tab" data-id="${esc(k.entity_id)}" aria-selected="${k.entity_id === this.selected}">${esc(k.attributes.kid)}</button>`,
            )
            .join("")}</div>`
        : "";
    tabs.querySelectorAll(".tab").forEach((t) =>
      t.addEventListener("click", () => {
        if (t.dataset.id === this.selected) return;
        this.selected = t.dataset.id;
        const content = this.$(".content");
        content.classList.add("switching");
        setTimeout(() => {
          this.update(this.kids);
          content.classList.remove("switching");
        }, 180);
      }),
    );
    const kid = kids.find((k) => k.entity_id === this.selected);
    if (!kid) return;
    const { head, body } = renderTimetable(kid);
    this.$(".head-slot").innerHTML = head.replace('class="title"', 'class="title" id="sp-title"');
    this.$(".content").innerHTML = body;
    this.$(".sheet").style.setProperty("--accent", kid.attributes.accent_color || "#0a84ff");
  }

  present() {
    if (this.hasAttribute("open")) return;
    this.setAttribute("open", "");
    if (reducedMotion()) return this._fade(1);
    if (this.y === null) this._set(this.height);
    this.spring = new Spring({ damping: 1, response: 0.4 });
    this.spring.run(this.y, 0, 0, (y) => this._set(y));
    this.$(".close").focus({ preventScroll: true });
  }

  // Closes along the same path it came in, optionally carrying a flick's velocity.
  close(velocity = 0, done) {
    this.removeAttribute("open");
    if (reducedMotion()) return this._fade(0, done);
    this.spring = new Spring({ damping: 1, response: 0.35 });
    this.spring.run(this.y ?? 0, this.height, velocity, (y) => this._set(y), () => {
      this.y = null;
      done?.();
    });
  }

  dismiss(velocity = 0) {
    this.close(velocity);
    this.onDismiss?.(this.kids);
  }

  _set(y) {
    this.y = y;
    const h = this.height;
    this.$(".sheet").style.transform = `translate(-50%, ${y}px)`;
    this.$(".scrim").style.opacity = String(Math.max(0, Math.min(1, 1 - y / h)));
  }

  _fade(to, done) {
    const sheet = this.$(".sheet");
    const scrim = this.$(".scrim");
    if (to && this.y === null) {
      sheet.style.transition = scrim.style.transition = "none";
      sheet.style.opacity = scrim.style.opacity = "0";
      sheet.getBoundingClientRect(); // commit the start state before fading in
    }
    sheet.style.transform = "translate(-50%, 0)";
    for (const el of [sheet, scrim]) {
      el.style.transition = "opacity 200ms ease";
      el.style.opacity = String(to);
    }
    this.y = to ? 0 : null;
    setTimeout(() => done?.(), 200);
  }

  _bindDrag() {
    const handle = this.$(".drag");
    let start = null;
    let samples = [];

    handle.addEventListener("pointerdown", (e) => {
      if (e.target.closest("button") || !this.hasAttribute("open") || reducedMotion()) return;
      handle.setPointerCapture(e.pointerId);
      this.spring.stop(); // grab it mid-flight; continue from where it is on screen
      start = { pointerY: e.clientY, sheetY: this.y ?? 0 };
      samples = [{ y: e.clientY, t: e.timeStamp }];
    });

    handle.addEventListener("pointermove", (e) => {
      if (!start) return;
      let y = start.sheetY + (e.clientY - start.pointerY);
      if (y < 0) y = rubberband(y, this.height);
      this._set(y);
      samples.push({ y: e.clientY, t: e.timeStamp });
      samples = samples.filter((s) => e.timeStamp - s.t < 100);
    });

    const release = (e) => {
      if (!start) return;
      start = null;
      const first = samples[0];
      const last = samples.at(-1);
      const dt = (last.t - first.t) / 1000;
      const velocity = dt > 0 ? (last.y - first.y) / dt : 0;
      const projected = this.y + project(velocity);
      if (projected > this.height * 0.4 && velocity >= 0) {
        this.dismiss(velocity);
      } else {
        // Thrown back up: a touch of bounce, because the gesture carried momentum.
        this.spring = new Spring({ damping: 0.8, response: 0.3 });
        this.spring.run(this.y, 0, velocity, (y) => this._set(y));
      }
    };
    handle.addEventListener("pointerup", release);
    handle.addEventListener("pointercancel", release);
  }
}

/* ---------- the card ---------- */

const DISMISSED_KEY = "stundenplan-card-dismissed";

const loadDismissed = () => {
  try {
    return new Set(JSON.parse(localStorage.getItem(DISMISSED_KEY) || "[]"));
  } catch {
    return new Set();
  }
};

const saveDismissed = (set) => {
  try {
    localStorage.setItem(DISMISSED_KEY, JSON.stringify([...set].slice(-50)));
  } catch {
    /* storage unavailable: dismissals last until reload */
  }
};

class StundenplanCard extends HTMLElement {
  static getStubConfig() {
    return { mode: "popup" };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.dismissed = loadDismissed();
    this.signature = "";
  }

  setConfig(config) {
    if (config.mode && !["popup", "inline"].includes(config.mode)) {
      throw new Error('mode must be "popup" or "inline"');
    }
    this.config = { mode: "popup", ...config };
    this.signature = "";
    this.ids = null;
    if (this._hass) this.hass = this._hass;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this.config) return;
    const kids = this._kids(hass);
    const dark = Boolean(hass.themes?.darkMode);
    const signature = JSON.stringify([
      dark,
      this.editMode,
      kids.map((k) => [k.entity_id, k.last_updated, hass.states[k.attributes.popup_entity]?.last_updated]),
    ]);
    if (signature === this.signature) return;
    this.signature = signature;
    this._render(kids, dark);
  }

  connectedCallback() {
    this.signature = "";
    if (this._hass) this.hass = this._hass;
    // Re-evaluate once a minute so the current period and past lessons stay right.
    this.timer = setInterval(() => {
      this.signature = "";
      this.ids = null;
      if (this._hass) this.hass = this._hass;
    }, 60_000);
  }

  disconnectedCallback() {
    clearInterval(this.timer);
    // Leave the dashboard -> take the sheet with us.
    const sheet = this.sheet;
    this.sheet = null;
    sheet?.close(0, () => sheet.remove());
  }

  getCardSize() {
    return this.config?.mode === "inline" ? 6 : 0;
  }

  _kids(hass) {
    // Scanning all states is cheap but not free; refresh the list once a minute.
    this.ids ??= this.config.entities?.length
      ? this.config.entities
      : Object.keys(hass.states).filter(
          (id) => id.startsWith("sensor.") && Array.isArray(hass.states[id].attributes.days) && "popup_entity" in hass.states[id].attributes,
        );
    return this.ids
      .map((id) => hass.states[id])
      .filter(Boolean)
      .sort((a, b) => String(a.attributes.popup_start).localeCompare(String(b.attributes.popup_start)));
  }

  _render(kids, dark) {
    if (this.config.mode === "inline") return this._renderInline(kids, dark);

    // Popup mode: a quiet placeholder while editing the dashboard, otherwise nothing.
    const editing = this.editMode || this.preview;
    this.shadowRoot.innerHTML = editing
      ? `<ha-card style="padding:16px">
           <b>Stundenplan-Pop-up</b><br>
           ${kids.map((k) => `${esc(k.attributes.kid)}: ${esc(k.attributes.popup_start)}–${esc(k.attributes.popup_end)}`).join("<br>") || "Keine Kinder gefunden."}
         </ha-card>`
      : `<style>:host{display:none}</style>`;

    const active = kids.filter((k) => {
      const popup = this._hass.states[k.attributes.popup_entity];
      return popup?.state === "on" && !this.dismissed.has(this._dismissKey(k));
    });

    if (!active.length) {
      if (this.sheet?.hasAttribute("open")) this.sheet.close();
      return;
    }
    if (!this.sheet) {
      this.sheet = document.createElement("stundenplan-sheet");
      this.sheet.onDismiss = (shown) => {
        shown.forEach((k) => this.dismissed.add(this._dismissKey(k)));
        saveDismissed(this.dismissed);
      };
      document.body.appendChild(this.sheet);
    }
    this.sheet.setTheme(dark);
    this.sheet.update(active);
    requestAnimationFrame(() => this.sheet?.present());
  }

  // One key per showing (each day's window, each button press), so a closed sheet comes back next time.
  _dismissKey(kid) {
    const popup = this._hass.states[kid.attributes.popup_entity];
    return `${kid.entity_id}@${popup?.attributes.shown_since || popup?.last_changed}`;
  }

  _renderInline(kids, dark) {
    this.toggleAttribute("data-theme", false);
    if (dark) this.setAttribute("data-theme", "dark");
    const kid = kids.find((k) => k.entity_id === this.selected) || kids[0];
    if (!kid) {
      this.shadowRoot.innerHTML = `<ha-card style="padding:16px">Kein Stundenplan gefunden.</ha-card>`;
      return;
    }
    const { head, body } = renderTimetable(kid);
    const tabs =
      kids.length > 1
        ? kids
            .map(
              (k) =>
                `<button class="tab" data-id="${esc(k.entity_id)}" aria-selected="${k === kid}">${esc(k.attributes.kid)}</button>`,
            )
            .join("")
        : "";
    this.shadowRoot.innerHTML = `
      <style>${STYLES}
        ha-card { padding: 1.25rem 1.25rem 0.75rem; --accent: ${esc(kid.attributes.accent_color || "#0a84ff")}; }
        .tabs { display: inline-flex; gap: 0.125rem; margin-top: 0.75rem; padding: 0.125rem; border-radius: 0.5625rem; background: var(--sp-fill); }
        .tab { border: 0; padding: 0.3125rem 0.875rem; border-radius: 0.4375rem; background: transparent; color: var(--sp-text); font: 500 0.8125rem/1.2 var(--sp-font); cursor: pointer; }
        .tab[aria-selected="true"] { background: var(--sp-today); font-weight: 600; box-shadow: 0 1px 3px rgba(0,0,0,.12); }
        .today-col { box-shadow: none; background: var(--sp-fill); }
      </style>
      <ha-card>
        <div class="head">${head}</div>
        ${tabs ? `<div class="tabs">${tabs}</div>` : ""}
        ${body}
      </ha-card>`;
    this.shadowRoot.querySelectorAll(".tab").forEach((t) =>
      t.addEventListener("click", () => {
        this.selected = t.dataset.id;
        this.signature = "";
        this.hass = this._hass;
      }),
    );
  }
}

if (!customElements.get("stundenplan-sheet")) customElements.define("stundenplan-sheet", StundenplanSheet);
if (!customElements.get("stundenplan-card")) customElements.define("stundenplan-card", StundenplanCard);

window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "stundenplan-card")) {
  window.customCards.push({
    type: "stundenplan-card",
    name: "Stundenplan",
    description: "Stundenplan als Pop-up zu festen Zeiten oder als Karte.",
    preview: false,
  });
}

console.info(`%c STUNDENPLAN-CARD %c ${VERSION} `, "background:#0a84ff;color:#fff;border-radius:3px 0 0 3px", "background:#1d1d1f;color:#fff;border-radius:0 3px 3px 0");
