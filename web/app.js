"use strict";
/* ตรวจล็อต · ขายแทน — หน้าเว็บ LIFF ของ TGR-49
   ?mock=ready|drying|selling|sold|alert|stale  ใช้ไฟล์ mock/*.json ข้าม LIFF
   ?lot=LOT-…                                   เปิดล็อตตรง ๆ (จากปุ่มใน Push)
   ?demo=1                                      แถบปุ่มเดโม (ทำทีหลัง) */

const CFG = window.APP_CONFIG || {};
// เปิดผ่าน https://liff.line.me/<LIFF_ID>?lot=… ครั้งแรก LINE จะส่ง query มาใน liff.state (เช่น "?lot=LOT-T49-1")
// รวมเข้ามาด้วย ไม่งั้นปุ่มใน Push จะไม่เปิดล็อตที่ถูก
const params = (() => {
  const p = new URLSearchParams(location.search);
  const st = p.get("liff.state");
  if (st && st.includes("?")) new URLSearchParams(st.slice(st.indexOf("?"))).forEach((v, k) => { if (!p.has(k)) p.set(k, v); });
  return p;
})();
let MOCK = /^[a-z0-9_-]+$/i.test(params.get("mock") || "") ? params.get("mock") : null;
// โหมด mock: POST แล้วสลับไปใช้ไฟล์ mock ของสถานะถัดไป (จำลองสิ่งที่ backend ตอบ)
const MOCK_AFTER_POST = [[/\/sell$/, "selling"], [/\/inspect/, "ready"], [/^\/lots$/, "drying"], [/^\/demo\/reset$/, "drying"]];

const STALE_MS = 30 * 60 * 1000;
const POLL_MS = 10000, POLL_SELLING_MS = 5000;

const state = {
  lot: null,            // ล็อตล่าสุดที่โหลดได้
  lotId: params.get("lot"),
  idToken: null,
  loadError: null,      // ข้อความเมื่อโหลดไม่สำเร็จครั้งล่าสุด
  lastJson: "",
  pollTimer: null,
};

/* ================= เครื่องมือเล็ก ๆ ================= */
const $ = (sel) => document.querySelector(sel);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (v, d = 1) => (v == null || isNaN(v) ? "—" : Number(v).toFixed(d));
const timeFmt = new Intl.DateTimeFormat("th-TH", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Bangkok" });
const hhmm = (iso) => (iso ? timeFmt.format(new Date(iso)) : "—");
const GRADE_TH = { PREMIUM: "พรีเมียม", GRADE_1: "เกรด 1", GRADE_2: "เกรด 2", GRADE_3: "เกรด 3", BELOW_STANDARD: "ต่ำกว่ามาตรฐาน", REJECT: "ไม่ผ่าน" };
const gradeName = (g) => GRADE_TH[g] || g || "—";
const isSimulated = (lot) => !!lot?.simulated && Object.values(lot.simulated).some(Boolean);

/* ไอคอน (เส้น 24×24 ตามดีไซน์) */
const svg = (d, sw = 2) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
const ICON = {
  sun: svg('<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>'),
  checkCircle: svg('<circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/>', 2.2),
  swap: svg('<path d="M4 8h14l-4-4M20 16H6l4 4"/>'),
  check: svg('<path d="M5 12l5 5 9-10"/>', 3),
  checkBold: svg('<path d="M5 12l5 5 9-10"/>', 2.2),
  warn: svg('<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18v.5"/>'),
  clock: svg('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'),
  shield: svg('<path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/><path d="M9 12l2 2 4-4"/>'),
  chevron: svg('<path d="M9 6l6 6-6 6"/>'),
  drop: svg('<path d="M12 3s6 6.5 6 11a6 6 0 0 1-12 0c0-4.5 6-11 6-11z"/>'),
  bean: svg('<ellipse cx="12" cy="12" rx="6" ry="8.5" transform="rotate(30 12 12)"/><path d="M9.5 5.5c2.5 3 2 9 5 13"/>'),
  ruler: svg('<path d="M3 17L17 3l4 4L7 21z"/><path d="M7 13l2 2M10 10l2 2M13 7l2 2"/>'),
  bell: svg('<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z"/><path d="M10 20a2 2 0 0 0 4 0"/>'),
  retry: svg('<path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v5h-5"/>', 2.2),
  offline: svg('<path d="M3 3l18 18"/><path d="M8.5 16.5a5 5 0 0 1 7 0M5 12.5a10 10 0 0 1 4-2.4M19 12.5a10 10 0 0 0-3.5-2.2M2 8.8a15 15 0 0 1 4.5-2.7M22 8.8A15 15 0 0 0 12 5"/><circle cx="12" cy="20" r=".8"/>'),
};

const STATUS_CHIP = {
  DRYING: ["chip-drying", ICON.sun, "กำลังตาก"],
  READY: ["chip-ready", ICON.checkCircle, "พร้อมขาย"],
  SELLING: ["chip-selling", ICON.swap, "กำลังขาย"],
  SOLD: ["chip-sold", ICON.checkBold, "ขายแล้ว"],
  ALERT: ["chip-alert", ICON.warn, "ต้องดูแล"],
};
function chip(status) {
  const [cls, icon, text] = STATUS_CHIP[status] || ["chip-sold", "", status];
  return `<span class="chip ${cls}">${icon}${text}</span>`;
}
let staleRender = false; // ตอนวาดเนื้อหาเดิมในหน้า 10 ให้เขียนว่า "ค่าเมื่อ" แทน "อัปเดต"
const updatedAt = (iso) => `<span class="updated">${ICON.clock}${staleRender ? "ค่าเมื่อ" : "อัปเดต"} ${hhmm(iso)}</span>`;
function agoText(iso) {
  const min = Math.max(0, Math.floor((Date.now() - new Date(iso)) / 60000));
  if (min < 60) return `${min} นาที`;
  if (min < 24 * 60) return `${Math.floor(min / 60)} ชั่วโมง`;
  return `${Math.floor(min / 1440)} วัน`;
}

/* URL ภาพจาก backend: แทน <API_BASE> ในไฟล์ mock / ต่อ path แบบสัมพัทธ์ */
function imageUrl(u) {
  if (!u) return null;
  if (u.includes("<API_BASE>")) return CFG.API_BASE ? u.replace(/^https?:\/\/<API_BASE>/, CFG.API_BASE) : null;
  if (u.startsWith("/")) return CFG.API_BASE ? CFG.API_BASE + u : null;
  return u;
}

let toastTimer;
function toast(msg, ms = 3500) {
  const el = $("#toast");
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), ms);
}

/* ================= ข้อมูล ================= */
// mock มีเวลาตายตัว เลื่อนให้เป็น "เพิ่งอัปเดต" (stale = 2 ชม.ก่อน) ไม่งั้นทุกหน้าจะกลายเป็นหน้าข้อมูลไม่อัปเดต
function shiftMockTimes(lot) {
  const minute = 60000;
  const target = Math.floor(Date.now() / minute) * minute - (MOCK === "stale" ? 120 * minute : minute);
  const delta = target - new Date(lot.updated_at).getTime();
  (function walk(o) {
    if (Array.isArray(o)) return o.forEach(walk);
    if (o && typeof o === "object") {
      for (const k of Object.keys(o)) {
        if ((k === "ts" || k === "updated_at") && typeof o[k] === "string") o[k] = new Date(new Date(o[k]).getTime() + delta).toISOString();
        else walk(o[k]);
      }
    }
  })(lot);
  return lot;
}

async function api(path, opts = {}) {
  if (MOCK) {
    if (opts.method === "POST") {
      await new Promise((r) => setTimeout(r, 900)); // หน่วงเหมือนเรียกผ่านเน็ต
      const next = MOCK_AFTER_POST.find(([re]) => re.test(path.split("?")[0]));
      if (next) MOCK = next[1]; // ไม่เปลี่ยน URL: โหลดหน้าใหม่ = กลับไปเริ่มที่ mock เดิม
    }
    const r = await fetch(`mock/${MOCK}.json`, { cache: "no-store" });
    if (!r.ok) throw Object.assign(new Error(`ไม่พบข้อมูลตัวอย่าง "${MOCK}"`), { status: r.status });
    return shiftMockTimes(await r.json());
  }
  if (!CFG.API_BASE) throw new Error("ยังไม่ได้ตั้งค่าที่อยู่ระบบ (API_BASE)");
  const headers = { "Content-Type": "application/json" };
  if (state.idToken) headers.Authorization = `Bearer ${state.idToken}`;
  else headers["X-Dev-User"] = "dev"; // ตอน backend ยังไม่เปิดตรวจ LINE
  let r;
  try {
    r = await fetch(CFG.API_BASE + path, { ...opts, headers: { ...headers, ...(opts.headers || {}) }, signal: AbortSignal.timeout(8000) });
  } catch {
    throw Object.assign(new Error("เชื่อมต่อระบบไม่ได้"), { status: 0 });
  }
  const body = await r.json().catch(() => ({}));
  if (!r.ok) throw Object.assign(new Error(body.detail || "เชื่อมต่อระบบไม่ได้"), { status: r.status });
  return body;
}

/* 401 = ID token ใช้ไม่ได้ (หมดอายุ / ยังไม่ได้ล็อกอิน)
   นอก LINE: พาไปล็อกอินใหม่ · ใน LINE: โหลดหน้าใหม่ 1 ครั้งเพื่อขอ token ใหม่ (liff.login ใช้ในแอป LINE ไม่ได้)
   LIFF ยังไม่พร้อม (ไม่มี LIFF_ID / init ไม่ผ่าน): คืน false ให้แสดงข้อความจาก backend ตามปกติ */
function handleAuthError() {
  if (!state.liffReady) return false;
  if (!liff.isInClient()) { liff.login({ redirectUri: location.href }); return true; }
  try {
    if (sessionStorage.getItem("tgr49-reauth")) return false; // ลองไปแล้ว ไม่วนซ้ำ
    sessionStorage.setItem("tgr49-reauth", "1");
  } catch { return false; }
  location.reload();
  return true;
}

const fetchLot = () => api(state.lotId ? `/lots/${encodeURIComponent(state.lotId)}` : "/lots/latest");

async function refresh() {
  clearTimeout(state.pollTimer);
  try {
    setLot(await fetchLot());
  } catch (e) {
    if (e.status === 401 && handleAuthError()) return;
    if (e.status === 404 && state.lotId) { state.lotId = null; return refresh(); }
    state.loadError = e.message || "เชื่อมต่อระบบไม่ได้";
    render();
  }
  schedulePoll();
}

function setLot(lot) {
  try { sessionStorage.removeItem("tgr49-reauth"); } catch { /* ไม่เป็นไร */ }
  const recovered = state.loadError != null;
  state.loadError = null;
  state.lotId = lot.lot_id;
  const json = JSON.stringify(lot);
  // วาดใหม่เมื่อข้อมูลเปลี่ยน · เน็ตกลับมา · เวลาผ่านไปจนข้ามเกณฑ์ 30 นาที · หน้า 10 (ให้ "มา X นาที" เดินต่อ)
  const name = screenFor(lot);
  if (json === state.lastJson && !recovered && name === state.lastScreen && name !== "stale") return;
  state.lastJson = json;
  state.lastScreen = name;
  state.lot = lot;
  render();
}

function schedulePoll() {
  clearTimeout(state.pollTimer);
  if (document.hidden) return;
  const ms = state.lot?.status === "SELLING" ? POLL_SELLING_MS : POLL_MS;
  state.pollTimer = setTimeout(refresh, ms);
}

/* ================= เลือกหน้าจอ ================= */
function screenFor(lot) {
  const stale = Date.now() - new Date(lot.updated_at) > STALE_MS;
  if (stale && ["DRYING", "READY", "ALERT"].includes(lot.status)) return "stale";
  return { DRYING: "drying", READY: "ready", SELLING: "selling", SOLD: "sold", ALERT: "alert" }[lot.status] || "unknown";
}

const SCREENS = {
  drying: renderDrying,
  ready: renderReady,
  selling: renderSelling,
  sold: renderSold,
  alert: renderAlert,
  inspection: renderInspection,
  stale: renderStale,
  offline: renderStale,
};

/* หน้าย่อย (ผลตรวจเมล็ด) ใช้ #inspection ใน URL ให้ปุ่มย้อนกลับของมือถือพากลับหน้าหลักได้ */
const currentView = () => (location.hash === "#inspection" ? "inspection" : "main");
let mainScroll = 0;
function goView(view) {
  if (view === currentView()) return;
  if (view === "inspection") {
    mainScroll = window.scrollY;
    history.pushState({ view }, "", "#inspection");
  } else if (history.state?.view === "inspection") return history.back(); // popstate จะ render ให้
  else history.replaceState(null, "", location.pathname + location.search);
  afterViewChange();
}
function afterViewChange() {
  render();
  window.scrollTo(0, currentView() === "main" ? mainScroll : 0);
}
// ปุ่มย้อนกลับ: ถ้ามี sheet เปิดอยู่ ปิด sheet อย่างเดียว · ไม่งั้นสลับหน้า
let ignorePop = false;
window.addEventListener("popstate", () => {
  if (ignorePop) { ignorePop = false; return; }
  if (sheetOpen) return closeSheet(true);
  afterViewChange();
});

function render() {
  const screen = $("#screen"), footer = $("#footer");
  const lot = state.lot;
  $("#sim-badge").hidden = !isSimulated(lot);

  if (!lot) {
    footer.innerHTML = "";
    screen.className = "screen";
    screen.innerHTML = state.loadError ? errorView(state.loadError) : skeletonView();
    return;
  }
  // มีข้อมูลเดิมแต่โหลดใหม่ไม่ได้ → แสดงแบบหน้า 10 (เนื้อหาเดิมจาง + แถบเตือน)
  const name = state.loadError ? "offline"
    : currentView() === "inspection" && lot.inspection ? "inspection" : screenFor(lot);
  const view = (SCREENS[name] || renderTodo)(lot, name);
  screen.innerHTML = view.body;
  footer.innerHTML = view.footer ? `<div class="footer">${view.footer}</div>` : "";
  screen.className = "screen";
  // เว้นที่ด้านล่างเท่าความสูงแถบปุ่มจริง (บางหน้ามี 2 ปุ่ม) เนื้อหาจะได้ไม่ถูกบัง
  const demoH = document.querySelector(".demo-bar")?.offsetHeight || 0;
  screen.style.paddingBottom = view.footer ? `${footer.firstElementChild.offsetHeight + demoH + 24}px` : demoH ? `${demoH + 24}px` : "";
  // ภาพโหลดไม่ขึ้น → ใช้ไอคอนเมล็ดแทน
  screen.querySelectorAll("img[data-fallback]").forEach((img) =>
    img.addEventListener("error", () => { img.parentElement.innerHTML = ICON.bean; }, { once: true }));
  screen.querySelectorAll("img[data-hide-on-error]").forEach((img) =>
    img.addEventListener("error", () => img.closest("figure")?.remove(), { once: true }));
}

/* ================= หน้าจอ ================= */
function skeletonView() {
  const box = (h, extra = "") => `<div class="sk" style="height:${h}px;${extra}"></div>`;
  return `<div class="status-row">${box(30, "width:110px;border-radius:999px")}${box(20, "width:90px")}</div>
    ${box(36, "width:75%")}${box(20, "width:40%")}
    ${box(170, "border-radius:16px")}
    <div class="tiles">${box(128, "border-radius:14px")}${box(128, "border-radius:14px")}${box(128, "border-radius:14px")}</div>
    ${box(72, "border-radius:14px")}`;
}

function errorView(msg) {
  return `<div class="error-box">${ICON.offline}
    <h1 class="title" style="font-size:22px;line-height:32px">เชื่อมต่อระบบไม่ได้</h1>
    <p class="subtitle">${esc(msg)}</p>
    <button class="btn btn-outline" data-action="retry">${ICON.retry}ลองใหม่</button></div>`;
}

function renderTodo(lot, name) {
  return { body: `<div class="status-row">${chip(lot.status)}${updatedAt(lot.updated_at)}</div>
    <h1 class="title">${esc(lot.lot_id)}</h1>
    <div class="note">${ICON.clock}<span>หน้าจอ "${esc(name)}" ยังไม่ได้ทำ</span></div>` };
}

/* ---------- 03 พร้อมขาย ---------- */
function renderReady(lot) {
  const p = lot.pricing, insp = lot.inspection, m = lot.moisture || {};
  const passMoist = m.current != null && m.current <= (m.target ?? 12.5);
  const img = imageUrl(insp?.vis_url);
  const buyers = [
    lot.buyers?.commercial && "ผู้ซื้อเกรดพาณิชย์",
    lot.buyers?.instant && "กาแฟสำเร็จรูป",
  ].filter(Boolean);

  const body = `
  <div class="status-row">${chip("READY")}${updatedAt(lot.updated_at)}</div>
  <div>
    <h1 class="title">ตากได้ที่แล้ว ขายได้เลย</h1>
    <p class="subtitle">${esc(lot.lot_id)} · ${esc(lot.sacks)} กระสอบ</p>
  </div>

  <section class="card card-raised price-card" aria-label="ราคาประเมิน">
    <div class="label">ราคาประเมิน</div>
    <div class="price-row"><span class="price-big">${num(p?.value)}</span><span class="price-unit">บาท/กก.</span></div>
    <div class="floor-line">${ICON.shield}<span>ระบบจะไม่ขายต่ำกว่า <b>${num(p?.floor)}</b> บาท/กก.</span></div>
    <button class="link-row" data-action="price-info">ราคานี้มาจากไหน${ICON.chevron}</button>
  </section>

  <div class="tiles">
    <div class="tile">${ICON.drop}
      <span class="tile-label">ความชื้น</span>
      <span class="tile-value">${num(m.current)}%</span>
      ${passMoist
        ? `<span class="tile-note ok">${ICON.check}<span>ผ่าน ≤${num(m.target ?? 12.5)}%</span></span>`
        : `<span class="tile-note warn">เกิน ${num(m.target ?? 12.5)}%</span>`}
    </div>
    <div class="tile">${ICON.bean}
      <span class="tile-label">เมล็ดเสีย</span>
      <span class="tile-value">${num(insp?.defect_pct)}%</span>
      <span class="tile-note">${esc(gradeName(p?.grade))}</span>
    </div>
    <div class="tile">${ICON.ruler}
      <span class="tile-label">ขนาดเมล็ด</span>
      ${!p || p.size_source === "default"
        ? `<span class="tile-value">—</span><span class="tile-note plain">ใช้ค่ามาตรฐาน</span>`
        : `<span class="tile-value">×${num(p.S, 2)}</span><span class="tile-note plain">วัดแล้ว</span>`}
    </div>
  </div>

  ${buyers.length ? `<div class="buyers"><span class="buyers-label">ขายให้ได้</span>
    ${buyers.map((b) => `<span class="buyer-chip">${ICON.check}${b}</span>`).join("")}</div>` : ""}

  <button class="row-card" data-action="inspection">
    <span class="thumb">${img ? `<img src="${esc(img)}" alt="" data-fallback>` : ICON.bean}</span>
    <span class="row-card-text">
      <span class="row-card-title">ผลตรวจเมล็ด</span>
      <span class="row-card-sub">เสีย ${num(insp?.defect_pct)}% · ${esc(gradeName(p?.grade))}</span>
    </span>${ICON.chevron}
  </button>`;

  const footer = `<button class="btn btn-primary" data-action="sell">ยืนยันขาย</button>`;
  return { body, footer };
}

/* ---------- 02 กำลังตาก ---------- */
function moistureChart(history, target) {
  const pts = (history || []).filter((h) => h && h.value != null);
  if (pts.length < 2) return `<p class="caption">รอค่าความชื้นเพิ่มอีกนิดจึงจะแสดงกราฟ</p>`;
  const W = 313, H = 80, PAD = 6;
  const vals = pts.map((h) => Number(h.value));
  const lo = Math.min(...vals, target) - 0.5, hi = Math.max(...vals, target) + 0.5;
  const y = (v) => PAD + ((hi - v) / (hi - lo)) * (H - 2 * PAD);
  const x = (i) => (i / (pts.length - 1)) * W;
  const line = vals.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const last = vals[vals.length - 1];
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img"
      aria-label="กราฟความชื้นจาก ${num(vals[0])} เป็น ${num(last)} เปอร์เซ็นต์ เส้นประคือเกณฑ์ ${num(target)} เปอร์เซ็นต์">
    <line x1="0" y1="${y(target).toFixed(1)}" x2="${W}" y2="${y(target).toFixed(1)}" stroke="#006B34" stroke-width="1.5" stroke-dasharray="5 5"/>
    <polyline points="${line}" fill="none" stroke="#B36B00" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="${W}" cy="${y(last).toFixed(1)}" r="5" fill="#B36B00" stroke="#fff" stroke-width="2"/>
  </svg>
  <div class="chart-x"><span>${hhmm(pts[0].ts)}</span><span>ตอนนี้</span></div>
  <div class="chart-legend">- - - เกณฑ์ขาย ${num(target)}%</div>`;
}

function renderDrying(lot) {
  const m = lot.moisture || {}, p = lot.pricing, insp = lot.inspection;
  const target = m.target ?? 12.5, start = m.start ?? m.current;
  const left = m.current != null ? m.current - target : null;
  const dry = left != null && left <= 0;
  const progress = start > target && m.current != null ? Math.max(0, Math.min(100, ((start - m.current) / (start - target)) * 100)) : 0;

  const body = `
  <div class="status-row">${chip("DRYING")}${updatedAt(lot.updated_at)}</div>
  <div>
    <h1 class="title">${dry ? "แห้งได้ที่แล้ว รอผลตรวจเมล็ด" : "ตากต่ออีกนิด ใกล้ขายได้แล้ว"}</h1>
    <p class="subtitle">${esc(lot.lot_id)} · ${esc(lot.sacks)} กระสอบ</p>
  </div>

  <section class="card" aria-label="ความชื้น">
    <div class="label">ความชื้นตอนนี้</div>
    <div class="moist-row">
      <span class="moist-big">${num(m.current)}%</span>
      <span class="moist-left ${dry ? "done" : ""}">${left == null ? "" : dry ? "ถึงเกณฑ์แล้ว" : `อีก ${num(left)}% ถึงเกณฑ์`}</span>
    </div>
    <div class="dry-bar" role="img" aria-label="ความคืบหน้าการตาก ${Math.round(progress)} เปอร์เซ็นต์ จาก ${num(start)} ถึงเกณฑ์ ${num(target)} เปอร์เซ็นต์">
      <span style="width:${progress}%"></span></div>
    <div class="bar-labels"><span>เริ่มตาก ${num(start)}%</span><span>ขายได้เมื่อ ≤ ${num(target)}%</span></div>
  </section>

  <section class="card chart-card">
    <div class="card-sub-title">ความชื้นล่าสุด</div>
    ${moistureChart(m.history, target)}
  </section>

  ${p ? `<section class="card chart-card">
      <div class="kv kv-top"><span class="kv-key">ราคาประเมินตอนนี้</span><span class="kv-val">${num(p.value)} บ./กก.</span></div>
      ${insp ? `<button class="link-row link-row-ink" data-action="inspection">
        <span>ผลตรวจเมล็ดล่าสุด: เสีย ${num(insp.defect_pct)}% · ${esc(gradeName(p.grade))}</span>${ICON.chevron}</button>` : ""}
    </section>`
    : `<section class="card chart-card">
      <div class="card-sub-title">ตรวจเมล็ดเมื่อแห้งได้ที่</div>
      <p class="caption-body">เมื่อความชื้นถึง ${num(target)}% ระบบจะตรวจเมล็ดแล้วบอกเกรดและราคาประเมินให้</p>
    </section>`}

  <div class="note">${ICON.bell}<span>ไม่ต้องทำอะไรตอนนี้ ระบบจะแจ้งเตือนทาง LINE เมื่อพร้อมขาย</span></div>`;
  return { body };
}

/* ---------- 10 ข้อมูลไม่อัปเดต (และโหลดใหม่ไม่ได้แต่มีข้อมูลเดิม) ---------- */
function renderStale(lot, mode) {
  const offline = mode === "offline";
  const baseName = offline && currentView() === "inspection" && lot.inspection ? "inspection"
    : { DRYING: "drying", READY: "ready", SELLING: "selling", SOLD: "sold", ALERT: "alert" }[lot.status];
  staleRender = true;
  let inner;
  try { inner = (SCREENS[baseName] || renderTodo)(lot, baseName); } finally { staleRender = false; }

  const title = offline ? "เชื่อมต่อระบบไม่ได้" : `ข้อมูลไม่อัปเดตมา ${agoText(lot.updated_at)}`;
  const why = offline
    ? (state.loadError && state.loadError !== "เชื่อมต่อระบบไม่ได้" ? `${esc(state.loadError)} · ` : "เน็ตอาจหลุด ")
    : "เครื่องวัดหรือเน็ตที่ลานตากอาจหลุด ";
  const body = `
  <section class="stale-banner" role="alert">
    <div class="stale-msg">${ICON.offline}
      <span><span class="stale-title">${title}</span>
      <span class="stale-text">${why}ค่าด้านล่างเป็นค่าเดิมเมื่อ ${hhmm(lot.updated_at)}</span></span>
    </div>
    <button class="btn btn-danger-outline" data-action="retry">${ICON.retry}ลองโหลดใหม่</button>
  </section>
  <div class="stale-body" inert>${inner.body}</div>`;

  // ห้ามขายจากข้อมูลเก่า: แสดงปุ่มยืนยันขายแบบกดไม่ได้ เฉพาะสถานะที่ปกติขายได้
  const sellable = lot.status === "READY" || (lot.status === "ALERT" && lot.alert?.kind !== "moisture_up" && lot.pricing);
  const footer = sellable ? `<div class="footer-hint">${svg('<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>')}รอข้อมูลล่าสุดก่อน เพราะราคาอาจเปลี่ยนไปแล้ว</div>
    <button class="btn btn-primary" disabled>ยืนยันขาย</button>` : "";
  return { body, footer };
}

/* ---------- 07 กำลังขาย ---------- */
const RESULT_BADGE = {
  pending: ["badge-wait", "", "รอตอบ"],
  sold: ["badge-ok", ICON.check, "ขายได้"],
  rejected: ["badge-no", "", "ไม่ได้"],
};
function renderSelling(lot) {
  const p = lot.pricing, s = lot.sales || {};
  const sacks = Number(lot.sacks) || 0, sold = Math.min(Number(s.sold_sacks) || 0, sacks);
  // แถบแบ่งช่องเท่าจำนวนกระสอบ (ถ้ากระสอบเยอะเกินจะใช้แถบยาวแถบเดียว)
  const bar = sacks > 0 && sacks <= 24
    ? `<div class="sack-bar" style="grid-template-columns:repeat(${sacks},minmax(0,1fr))">${Array.from({ length: sacks }, (_, i) => `<span class="${i < sold ? "on" : ""}"></span>`).join("")}</div>`
    : `<div class="sack-bar sack-bar-solid"><span style="width:${sacks ? (sold / sacks) * 100 : 0}%"></span></div>`;
  const steps = (lot.events || []).filter((e) => ["start", "offer", "sold"].includes(e.kind));

  const body = `
  <div class="status-row">${chip("SELLING")}${updatedAt(lot.updated_at)}</div>
  <div>
    <h1 class="title">ระบบกำลังขายให้</h1>
    <p class="subtitle">${esc(lot.lot_id)} · ${esc(lot.sacks)} กระสอบ</p>
  </div>

  <section class="card" aria-label="ความคืบหน้าการขาย">
    <div class="label">ขายแล้ว</div>
    <div class="big-count">${sold} <span>จาก ${sacks} กระสอบ</span></div>
    <div role="img" aria-label="ขายแล้ว ${sold} จาก ${sacks} กระสอบ">${bar}</div>
    <div class="kv"><span class="kv-key">ราคาที่ขายได้</span>
      <span class="kv-val">${s.avg_price == null ? `<span class="muted">รอผล</span>` : `${num(s.avg_price)} บ./กก.`}</span></div>
    <div class="floor-mini">${ICON.shield}ไม่ขายต่ำกว่า ${num(p?.floor)} บ./กก.</div>
  </section>

  <section class="card steps-card">
    <h2 class="card-title">ระบบทำอะไรไปแล้ว</h2>
    ${steps.length ? `<ol class="steps">${steps.map((e) => {
      const badge = RESULT_BADGE[e.result];
      let text = esc(e.text);
      if (e.buyer) text = text.replace(esc(e.buyer), `<span class="nobr">${esc(e.buyer)}</span>`);
      return `<li><span class="step-time">${hhmm(e.ts)}</span><span class="step-text">${text}</span>${
        badge ? `<span class="badge ${badge[0]}">${badge[1]}${badge[2]}</span>` : ""}</li>`;
    }).join("")}</ol>` : `<p class="caption">เริ่มขายแล้ว รอผู้ซื้อตอบ</p>`}
  </section>

  <div class="note">${ICON.bell}<span>ไม่ต้องทำอะไร ระบบจะแจ้งทาง LINE เมื่อขายครบ</span></div>`;
  return { body };
}

/* ---------- 08 ขายแล้ว ---------- */
function renderSold(lot) {
  const p = lot.pricing, s = lot.sales || {}, items = s.items || [];
  const price = s.avg_price;
  const clamp = (x) => Math.max(0, Math.min(100, x));
  // แถบเทียบ: 0% = ราคาต่ำสุด, 100% = ราคาประเมิน × 1.02
  const span = p ? p.value * 1.02 - p.floor : 0;
  const pos = p && price != null && span > 0 ? clamp(((price - p.floor) / span) * 100) : 0;
  const tick = p && span > 0 ? clamp(((p.value - p.floor) / span) * 100) : 100;
  const diff = p && price != null ? price - p.floor : null;
  const pct = diff != null && p.floor ? Math.round((diff / p.floor) * 100) : null;

  const body = `
  <div class="status-row">${chip("SOLD")}<span class="updated">ปิดการขาย ${hhmm(lot.updated_at)}</span></div>
  <div class="sold-head">
    <span class="sold-check">${svg('<path d="M5 12l5 5 9-10"/>', 2.6)}</span>
    <div><h1 class="title">ขายครบ ${esc(s.sold_sacks ?? lot.sacks)} กระสอบ</h1><p class="subtitle">${esc(lot.lot_id)}</p></div>
  </div>

  <section class="card" aria-label="ราคาที่ได้">
    <div class="label">${items.length > 1 ? "ราคาเฉลี่ยที่ได้" : "ราคาที่ได้"}</div>
    <div class="price-row"><span class="price-sold">${num(price)}</span><span class="price-unit">บาท/กก.</span></div>
    ${p ? `<div class="cmp-bar" role="img" aria-label="ราคาที่ได้ ${num(price)} เทียบราคาต่ำสุด ${num(p.floor)} และราคาประเมิน ${num(p.value)}">
        <span class="cmp-fill" style="width:${pos}%"></span><span class="cmp-tick" style="left:${tick}%"></span></div>
      <div class="cmp-labels"><span>ต่ำสุด ${num(p.floor)}</span><span>ประเมิน ${num(p.value)} ▏</span></div>
      ${diff == null ? "" : diff >= 0
        ? `<div class="cmp-note good">สูงกว่าราคาต่ำสุด ${num(diff)} บ./กก. (+${pct}%)</div>`
        : `<div class="cmp-note bad">ต่ำกว่าราคาต่ำสุด ${num(-diff)} บ./กก. (${pct}%)</div>`}` : ""}
  </section>

  ${items.length > 1 ? `<section class="card items-card">
    <h2 class="card-title">รายกระสอบ</h2>
    ${items.map((it, i) => `<div class="item-row"><span class="item-no">${i + 1}</span>
      <span class="item-buyer">${esc(it.buyer || "ผู้ซื้อในตลาด")}${it.sacks > 1 ? ` <span class="muted">· ${esc(it.sacks)} กระสอบ</span>` : ""}</span>
      <span class="item-price">${num(it.price)}</span></div>`).join("")}
  </section>` : ""}

  <button class="btn btn-outline" data-action="new-lot">เริ่มล็อตใหม่</button>`;
  return { body };
}

// ปุ่มที่ส่ง POST แล้วได้ Lot กลับ (เริ่มล็อตใหม่ / ขอตรวจใหม่) · กันกดซ้ำ · บอกปัญหาเป็นภาษาไทย
async function runPost(btn, path, busyText) {
  if (sending) return null;
  sending = true;
  const idleHtml = btn.innerHTML;
  btn.disabled = true;
  btn.textContent = busyText;
  try {
    const lot = await api(path, { method: "POST" });
    state.lotId = lot.lot_id;
    setLot(lot);
    window.scrollTo(0, 0);
    schedulePoll();
    return lot;
  } catch (e) {
    if (e.status === 401 && handleAuthError()) return null;
    btn.disabled = false;
    btn.innerHTML = idleHtml;
    if (e.status === 409 || e.status === 423) { toast(e.message, 5000); state.lastJson = ""; refresh(); }
    else toast(`${e.message} ลองกดอีกครั้ง`, 5000);
    return null;
  } finally {
    sending = false;
  }
}
const startNewLot = (btn) => runPost(btn, "/lots", "กำลังเริ่ม…");
async function requestInspect(btn) {
  const demo = params.get("demo") === "1" ? "?improved=true" : ""; // โหมดเดโม: จำลองว่าคัดเมล็ดเสียออกแล้ว
  const lot = await runPost(btn, `/lots/${encodeURIComponent(state.lot.lot_id)}/inspect${demo}`, "กำลังส่ง…");
  if (lot && lot.status === "ALERT") toast(`ตรวจใหม่แล้ว เมล็ดเสีย ${num(lot.inspection?.defect_pct)}% ยังเกินเกณฑ์`, 5000);
  else if (lot && lot.status === "READY") toast("ตรวจใหม่แล้ว ผ่านเกณฑ์ ขายได้เลย", 4000);
}

/* ---------- 09 ต้องดูแล ---------- */
function renderAlert(lot) {
  const a = lot.alert || {}, p = lot.pricing, insp = lot.inspection, m = lot.moisture || {};
  const head = `
  <div class="status-row">${chip("ALERT")}${updatedAt(lot.updated_at)}</div>
  <div>
    <h1 class="title">${esc(a.message || "ล็อตนี้ต้องดูแล")}</h1>
    <p class="subtitle">${esc(lot.lot_id)} · ${esc(lot.sacks)} กระสอบ</p>
  </div>`;
  const steps = (items) => `<section class="card chart-card"><h2 class="card-title">ควรทำ</h2>
    <ol class="todo">${items.map((t, i) => `<li><span class="todo-no">${i + 1}</span><span>${t}</span></li>`).join("")}</ol></section>`;

  if (a.kind === "moisture_up") {
    const target = a.threshold ?? m.target ?? 12.5;
    const body = `${head}
    <section class="card alert-card">
      <div class="alert-num"><span class="label">ความชื้นตอนนี้</span><span class="alert-big">${num(m.current)}%</span></div>
      <div class="alert-text">กลับขึ้นเกินเกณฑ์ขาย <b class="nobr">(ไม่เกิน ${num(target)}%)</b> ควรตากต่อก่อนขาย</div>
    </section>
    <section class="card chart-card"><div class="card-sub-title">ความชื้นล่าสุด</div>${moistureChart(m.history, target)}</section>
    ${steps(["เกลี่ยกองตากต่อ หรือคลุมกันชื้นถ้าฝนจะตก", `ไม่ต้องกดอะไร เมื่อความชื้นกลับมาไม่เกิน ${num(target)}% ระบบจะเปลี่ยนเป็นพร้อมขายเอง`])}`;
    return { body };
  }

  // defect_high (ค่าเริ่มต้น)
  const canSell = !!(lot.buyers?.commercial || lot.buyers?.instant) && p;
  const buyerLine = lot.buyers?.instant ? "ตอนนี้ขายได้เฉพาะผู้ซื้อกาแฟสำเร็จรูป" : "ตอนนี้ยังไม่มีผู้ซื้อรับ";
  const body = `${head}
  <section class="card alert-card">
    <div class="alert-num"><span class="label">เมล็ดเสีย</span><span class="alert-big">${num(insp?.defect_pct)}%</span></div>
    <div class="alert-text">เกินเกณฑ์ผู้ซื้อเกรดพาณิชย์ <b class="nobr">(ไม่เกิน ${num(a.threshold ?? 7, 0)}%)</b> ${buyerLine}</div>
  </section>
  ${p ? `<section class="card chart-card">
    <div class="kv kv-top"><span class="kv-key">ราคาตอนนี้</span><span class="kv-val">${num(p.value)} บ./กก.</span></div>
    <button class="link-row" data-action="price-info">ราคานี้มาจากไหน${ICON.chevron}</button>
  </section>` : ""}
  ${steps(["คัดเมล็ดดำ เมล็ดแตก และเมล็ดผิดปกติออก", "เกลี่ยกองใหม่ แล้วกด “ขอตรวจใหม่”"])}`;
  const footer = `<button class="btn btn-primary" data-action="inspect">${ICON.retry}ขอตรวจใหม่</button>
    ${canSell ? `<button class="btn btn-text" data-action="sell">ขายเลยที่ราคานี้ (${num(p.value)})</button>` : ""}`;
  return { body, footer };
}

/* ---------- 05 ผลตรวจเมล็ด ---------- */
// ชื่อคลาสตาม backend (app/sim/inspector.py) · สีเดียวกับภาพที่ระบบระบาย
const BEAN_CLASSES = [
  ["good", "เมล็ดดี", "#3C9A5F"],
  ["broken", "แตกหัก", "#F08A24"],
  ["black", "เมล็ดดำ", "#222222"],
  ["shell", "หูช้าง", "#9C6ADE"],
  ["parchment", "กะลา", "#E8D27A"],
  ["immature", "ดิบ/อ่อน", "#7FB7E8"],
  ["husk", "เศษเปลือก", "#8C4A2F"],
];
function renderInspection(lot) {
  const insp = lot.inspection, p = lot.pricing;
  const img = imageUrl(insp.vis_url);
  const counts = insp.class_counts && typeof insp.class_counts === "object" ? insp.class_counts : null;
  const total = insp.total ?? (counts ? Object.values(counts).reduce((a, b) => a + (Number(b) || 0), 0) : null);
  const found = counts ? BEAN_CLASSES.filter(([k]) => counts[k] > 0) : [];
  const missing = counts ? BEAN_CLASSES.filter(([k]) => !(counts[k] > 0)) : [];

  const body = `
  <button class="back-btn" data-action="back">${svg('<path d="M15 6l-6 6 6 6"/>')}กลับ</button>
  <div>
    <h1 class="title-s">เมล็ดเสีย ${num(insp.defect_pct)}% · ${esc(gradeName(p?.grade))}</h1>
    <p class="caption">ตรวจเมื่อ ${hhmm(insp.ts)}${total ? ` · ${esc(total)} เมล็ด` : ""}</p>
  </div>
  ${img ? `<figure class="vis"><img src="${esc(img)}" alt="ภาพกองเมล็ดจากกล้อง ระบายสีตามประเภทเมล็ด" data-hide-on-error></figure>` : ""}
  ${counts ? `<div class="card class-list">
    ${found.map(([k, label, color]) => `<div class="class-row"><span class="dot" style="background:${color}"></span>
      <span class="class-name">${label}</span><span class="class-count">${esc(counts[k])}</span></div>`).join("")}
    ${missing.length ? `<div class="class-missing">ไม่พบ: ${missing.map(([, label]) => label).join(" · ")}</div>` : ""}
  </div>` : ""}
  ${!img && !counts ? `<div class="note">${ICON.bean}<span>ระบบส่งมาเฉพาะ % เมล็ดเสีย ยังไม่มีภาพหรือจำนวนแยกตามประเภท</span></div>` : ""}`;
  return { body };
}

/* ================= bottom sheet ================= */
// เปิด sheet แล้ว push history ไว้ 1 ชั้น ให้ปุ่มย้อนกลับของ Android/LINE ปิด sheet แทนการออกจากแอป
let sheetOpen = false, lastFocus = null;
function openSheet(html, label) {
  if (sheetOpen) closeSheet(true);
  lastFocus = document.activeElement;
  $("#sheet-root").innerHTML = `<div class="sheet-backdrop" data-action="close-sheet">
    <section class="sheet" role="dialog" aria-modal="true" aria-label="${esc(label)}" tabindex="-1">
      <div class="sheet-handle" aria-hidden="true"></div>${html}</section></div>`;
  document.body.classList.add("sheet-open");
  $(".sheet").focus();
  sheetOpen = true;
  history.pushState({ sheet: true }, "");
}
function closeSheet(fromHistory = false) {
  if (!sheetOpen) return;
  sheetOpen = false;
  $("#sheet-root").innerHTML = "";
  document.body.classList.remove("sheet-open");
  lastFocus?.focus?.();
  if (!fromHistory && history.state?.sheet) { ignorePop = true; history.back(); }
}
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeSheet(); });
const sheetHead = (title) => `<div class="sheet-head"><h2 class="sheet-title">${title}</h2>
  <button class="icon-btn" data-action="close-sheet" aria-label="ปิด">${svg('<path d="M6 6l12 12M18 6L6 18"/>')}</button></div>`;

/* ---------- 04 ราคานี้มาจากไหน ---------- */
// ขั้นเกรดถัดไป (ใช้ในคำแนะนำ "อยากได้ราคาสูงขึ้น") ตามตารางใน 01 ข้อ 5
const NEXT_GRADE = {
  GRADE_1: { max: 1, grade: "PREMIUM", mult: 1.08 },
  GRADE_2: { max: 3, grade: "GRADE_1", mult: 1.04 },
  GRADE_3: { max: 5, grade: "GRADE_2", mult: 1.0 },
  BELOW_STANDARD: { max: 7, grade: "GRADE_3", mult: 0.96 },
  REJECT: { max: 15, grade: "BELOW_STANDARD", mult: 0.85 },
};
function priceSheet(lot) {
  const p = lot.pricing;
  if (!p) return `${sheetHead("ราคานี้มาจากไหน")}<p class="sheet-sub">ยังไม่มีผลตรวจเมล็ด จึงยังคำนวณราคาไม่ได้</p>
    <button class="btn btn-outline" data-action="close-sheet">เข้าใจแล้ว</button>`;
  const d = lot.inspection?.defect_pct, m = lot.moisture?.current, target = lot.moisture?.target ?? 12.5;
  const ratio = Math.round((p.floor_ratio ?? 0.8) * 100);
  const row = (name, hint, val, cls = "", hintCls = "") => `<div class="calc-row ${cls}">
    <span class="calc-name"><span>${name}</span>${hint ? `<span class="calc-hint ${hintCls}">${hint}</span>` : ""}</span>
    <span class="calc-val">${val}</span></div>`;
  const moistHint = p.M < 1 ? `${num(m)}% ชื้นเกิน ${num(target)}% ราคาลด` : `${num(m)}% ไม่เกิน ${num(target)}% ได้เต็ม`;
  const sizeHint = p.size_source === "default" ? "ยังไม่ได้วัด ใช้ค่ามาตรฐาน" : "วัดจากเมล็ดจริง";
  const next = NEXT_GRADE[p.grade];

  return `${sheetHead("ราคานี้มาจากไหน")}
  <p class="sheet-sub">คิดตามสูตรที่ตลาดประกาศ ทุกล็อตใช้สูตรเดียวกัน</p>
  <div class="calc">
    ${row("ราคาตั้งต้นของตลาด", "", num(p.base, 2))}
    ${row("× คุณภาพเมล็ด", `เสีย ${num(d)}% → ${esc(gradeName(p.grade))} (×${num(p.grade_mult, 2)})`, `× ${num(p.G, 3)}`)}
    ${row("× ความชื้น", moistHint, `× ${num(p.M, 3)}`, "", p.M < 1 ? "down" : "")}
    ${row("× ขนาดเมล็ด", sizeHint, `× ${num(p.S, 3)}`, "last-factor")}
    ${row("= ราคาประเมิน", "", `${num(p.value)} <small>บ./กก.</small>`, "total")}
  </div>
  <div class="callout callout-green">${ICON.shield}
    <span class="callout-text"><span class="callout-title">ไม่ขายต่ำกว่า ${num(p.floor)} บ./กก. (${ratio}%)</span>
    <span>ถ้าขายไม่ออกจนตลาดปิด ตลาดรับซื้อที่ ${ratio}% ของราคาประเมินอยู่แล้ว ระบบจึงไม่ขายต่ำกว่านี้</span></span>
  </div>
  ${next ? `<div class="callout callout-amber">${svg('<path d="M9 18h6M10 21h4"/><path d="M12 3a6 6 0 0 0-4 10.5c.8.8 1 1.5 1 2.5h6c0-1 .2-1.7 1-2.5A6 6 0 0 0 12 3z"/>')}
    <span class="callout-text"><span class="callout-title">อยากได้ราคาสูงขึ้น</span>
    <span>คัดเมล็ดดำและเมล็ดแตกออกให้เสียไม่เกิน ${next.max}% จะได้${esc(gradeName(next.grade))} (×${num(next.mult, 2)})</span></span>
  </div>` : ""}
  <button class="btn btn-outline" data-action="close-sheet">เข้าใจแล้ว</button>`;
}

/* ---------- 06 ยืนยันขาย ---------- */
function sellSheet(lot) {
  const p = lot.pricing;
  const row = (k, v, cls = "") => `<div class="sum-row"><span class="sum-key">${k}</span><span class="sum-val ${cls}">${v}</span></div>`;
  const check = (t) => `<li>${svg('<path d="M5 12l5 5 9-10"/>', 2.5)}<span>${t}</span></li>`;
  return `<div class="sheet-icon">${ICON.swap}</div>
  <h2 class="sheet-title">ยืนยันให้ระบบขายล็อตนี้?</h2>
  <div class="summary">
    ${row("ล็อต", `${esc(lot.lot_id)} · ${esc(lot.sacks)} กระสอบ`)}
    ${row("ราคาประเมิน", `${num(p?.value)} บ./กก.`)}
    ${row("ไม่ขายต่ำกว่า", `${num(p?.floor)} บ./กก.`, "floor")}
  </div>
  <ul class="checks">
    ${check("ระบบเสนอราคาให้ผู้ซื้อในตลาดเองทันที")}
    ${check("แจ้งผลทาง LINE ทุกครั้งที่ขายได้")}
  </ul>
  <p class="sheet-error" role="alert" hidden></p>
  <button class="btn btn-primary" data-action="confirm-sell" ${p ? "" : "disabled"}>ยืนยันขาย</button>
  <button class="btn btn-text sheet-cancel" data-action="close-sheet">ยังไม่ขาย</button>`;
}

let sending = false; // กันกดซ้ำ: ส่งได้ทีละครั้ง
async function confirmSell(btn) {
  if (sending || !state.lot) return;
  sending = true;
  btn.disabled = true;
  btn.textContent = "กำลังส่ง…";
  const errEl = $(".sheet-error");
  if (errEl) errEl.hidden = true;
  try {
    const lot = await api(`/lots/${encodeURIComponent(state.lot.lot_id)}/sell`, { method: "POST" });
    closeSheet();
    if (currentView() !== "main") history.replaceState(null, "", location.pathname + location.search);
    setLot(lot);
    window.scrollTo(0, 0);
    schedulePoll();
  } catch (e) {
    if (e.status === 401 && handleAuthError()) return;
    if (e.status === 409 || e.status === 423) {
      // สถานะเปลี่ยนไปแล้ว / ข้อมูลเก่า → ปิด sheet ดึงล็อตใหม่ แล้วบอกเหตุผลจาก backend
      closeSheet();
      toast(e.message, 5000);
      state.lastJson = "";
      refresh();
    } else {
      btn.disabled = false;
      btn.textContent = "ยืนยันขาย";
      if (errEl) { errEl.textContent = `${e.message} ยังไม่ได้ขาย ลองกดอีกครั้ง`; errEl.hidden = false; }
    }
  } finally {
    sending = false;
  }
}

/* ================= ปุ่มเดโม (?demo=1) ================= */
// X-Demo-Key เป็นความลับ ไม่ใส่ใน repo: ใส่ครั้งแรกตอนกดปุ่ม (หรือเปิดด้วย ?demokey=…) แล้วจำไว้ในเครื่องนี้
const DEMO = params.get("demo") === "1";
const DEMO_KEY_STORE = "tgr49-demo-key";
function demoKey(ask) {
  let key = params.get("demokey");
  try {
    if (key) localStorage.setItem(DEMO_KEY_STORE, key);
    else key = localStorage.getItem(DEMO_KEY_STORE);
  } catch { /* เบราว์เซอร์ไม่ให้ใช้ storage */ }
  if (!key && ask && !MOCK) {
    key = (prompt("ใส่ X-Demo-Key (ขอจากธร)") || "").trim();
    try { if (key) localStorage.setItem(DEMO_KEY_STORE, key); } catch { /* ไม่เป็นไร */ }
  }
  return key || "";
}
const DEMO_SPEED = {
  fast: { moisture_tick_seconds: 2, market_round_seconds: 2 },
  normal: { moisture_tick_seconds: 30, market_round_seconds: 10 },
};
async function demoCall(btn, what) {
  if (sending) return;
  if (what === "reset" && !confirm("รีเซ็ตเดโม? ล็อตทั้งหมดของผู้ใช้นี้จะถูกลบ แล้วเริ่มล็อตใหม่")) return;
  const key = demoKey(true);
  if (!key && !MOCK) return toast("ยังไม่ได้ใส่ X-Demo-Key");
  sending = true;
  const label = btn.textContent;
  btn.disabled = true;
  btn.textContent = "…";
  try {
    const headers = { "X-Demo-Key": key };
    if (what === "reset") {
      const lot = await api("/demo/reset", { method: "POST", headers });
      closeSheet();
      if (currentView() !== "main") history.replaceState(null, "", location.pathname + location.search);
      state.lotId = lot.lot_id; // ล็อตเดิมถูกลบแล้ว ตามล็อตใหม่ไป
      state.lastJson = "";
      setLot(lot);
      schedulePoll();
      toast("รีเซ็ตแล้ว เริ่มล็อตใหม่");
    } else {
      const r = await api("/demo/speed", { method: "POST", headers, body: JSON.stringify(DEMO_SPEED[what]) });
      const s = MOCK ? DEMO_SPEED[what] : r;
      toast(`${what === "fast" ? "เร่งเวลาแล้ว" : "กลับเป็นปกติแล้ว"} · ความชื้นทุก ${s.moisture_tick_seconds} วิ · ตลาดทุก ${s.market_round_seconds} วิ`);
    }
  } catch (e) {
    if (e.status === 403) { try { localStorage.removeItem(DEMO_KEY_STORE); } catch { /* ไม่เป็นไร */ } }
    toast(e.message || "สั่งเดโมไม่สำเร็จ", 5000);
  } finally {
    sending = false;
    btn.disabled = false;
    btn.textContent = label;
  }
}
function mountDemoBar() {
  if (!DEMO) return;
  document.body.classList.add("demo");
  const bar = document.createElement("div");
  bar.className = "demo-bar";
  bar.setAttribute("aria-label", "ปุ่มเดโม");
  bar.innerHTML = `<span class="demo-tag">เดโม</span>
    <button data-action="demo" data-what="reset">รีเซ็ต</button>
    <button data-action="demo" data-what="fast">เร่งเวลา</button>
    <button data-action="demo" data-what="normal">ปกติ</button>`;
  document.body.appendChild(bar);
}

/* ================= ปุ่มต่าง ๆ ================= */
const ACTIONS = {
  demo: (el) => demoCall(el, el.dataset.what),
  retry: (el) => {
    el.disabled = true;
    el.textContent = "กำลังโหลด…";
    state.lastJson = "";
    refresh();
  },
  "close-sheet": (el, e) => { if (el.classList.contains("sheet-backdrop") && e.target !== el) return; closeSheet(); },
  "price-info": () => state.lot && openSheet(priceSheet(state.lot), "ราคานี้มาจากไหน"),
  inspection: () => goView("inspection"),
  back: () => goView("main"),
  sell: () => state.lot && openSheet(sellSheet(state.lot), "ยืนยันขาย"),
  "confirm-sell": (el) => confirmSell(el),
  "new-lot": (el) => startNewLot(el),
  inspect: (el) => requestInspect(el),
};
document.addEventListener("click", (e) => {
  const el = e.target.closest("[data-action]");
  if (!el || el.disabled) return;
  ACTIONS[el.dataset.action]?.(el, e);
});
document.addEventListener("visibilitychange", () => {
  if (document.hidden) clearTimeout(state.pollTimer);
  else refresh();
});

/* ================= เริ่ม ================= */
async function boot() {
  mountDemoBar();
  render(); // skeleton
  if (!MOCK) {
    try {
      if (!window.liff || !CFG.LIFF_ID) throw new Error("no-liff");
      await liff.init({ liffId: CFG.LIFF_ID });
      if (!liff.isLoggedIn()) { liff.login({ redirectUri: location.href }); return; }
      state.idToken = liff.getIDToken();
      state.liffReady = true;
    } catch (e) {
      // ยังไม่มี LIFF_ID หรือ init ไม่ผ่าน → ใช้ X-Dev-User ไปก่อน (ช่วงพัฒนา)
      console.warn("LIFF ไม่พร้อม ใช้โหมดพัฒนา:", e.message);
    }
  }
  refresh();
}
boot();
