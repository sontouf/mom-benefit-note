// 엄마혜택노트 방문자 카운터 — Cloudflare Workers + D1 (무료 플랜)
//   POST /hit  {path, sid}  → 페이지뷰 +1, 접속 표시   → {live, today, page_today}
//   POST /ping {path, sid}  → 접속 표시만 (60초마다)    → {live, today, page_today}
// '지금 보는 사람' = 최근 5분 안에 신호를 보낸 브라우저 탭 수. IP·쿠키를 저장하지 않는다.
const LIVE_WINDOW = 300; // 초

function cors(env, req) {
  const origin = req.headers.get("origin") || "";
  const allowed = (env.ALLOWED_ORIGINS || "").split(",").map((s) => s.trim()).filter(Boolean);
  const ok = allowed.includes(origin);
  return {
    "access-control-allow-origin": ok ? origin : allowed[0] || "*",
    "access-control-allow-methods": "POST, OPTIONS",
    "access-control-allow-headers": "content-type",
    "vary": "origin",
  };
}

function kstDay() {
  return new Date(Date.now() + 9 * 3600 * 1000).toISOString().slice(0, 10);
}

export default {
  async fetch(req, env) {
    const headers = cors(env, req);
    if (req.method === "OPTIONS") return new Response(null, { headers });
    const url = new URL(req.url);
    if (req.method !== "POST" || !["/hit", "/ping"].includes(url.pathname)) {
      return new Response("not found", { status: 404, headers });
    }
    let body;
    try { body = await req.json(); } catch { return new Response("bad json", { status: 400, headers }); }
    const sid = String(body.sid || "").slice(0, 64);
    const path = String(body.path || "/").slice(0, 200);
    if (!/^[a-z0-9]{8,64}$/.test(sid) || !path.startsWith("/")) {
      return new Response("bad input", { status: 400, headers });
    }
    const now = Math.floor(Date.now() / 1000);
    const day = kstDay();
    const stmts = [
      env.DB.prepare("INSERT INTO presence (sid, ts) VALUES (?1, ?2) ON CONFLICT(sid) DO UPDATE SET ts = ?2").bind(sid, now),
    ];
    if (url.pathname === "/hit") {
      stmts.push(env.DB.prepare(
        "INSERT INTO pageviews (day, path, n) VALUES (?1, ?2, 1) ON CONFLICT(day, path) DO UPDATE SET n = n + 1").bind(day, path));
      stmts.push(env.DB.prepare(
        "INSERT INTO pageviews (day, path, n) VALUES (?1, '*', 1) ON CONFLICT(day, path) DO UPDATE SET n = n + 1").bind(day));
    }
    if (Math.random() < 0.02) { // 가끔 오래된 접속 기록 정리
      stmts.push(env.DB.prepare("DELETE FROM presence WHERE ts < ?1").bind(now - 86400));
    }
    await env.DB.batch(stmts);
    const [live, today, page] = await env.DB.batch([
      env.DB.prepare("SELECT COUNT(*) AS c FROM presence WHERE ts > ?1").bind(now - LIVE_WINDOW),
      env.DB.prepare("SELECT n FROM pageviews WHERE day = ?1 AND path = '*'").bind(day),
      env.DB.prepare("SELECT n FROM pageviews WHERE day = ?1 AND path = ?2").bind(day, path),
    ]);
    return Response.json({
      live: live.results[0]?.c || 0,
      today: today.results[0]?.n || 0,
      page_today: page.results[0]?.n || 0,
    }, { headers });
  },
};
