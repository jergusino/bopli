// Bopli waitlist API: POST /join {email, web} -> stores the email in D1.
const ALLOWED_ORIGINS = ["https://bopli.jergusino.com", "https://jergusino.github.io"];
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

const json = (body, status, headers) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });

export default {
  async fetch(req, env) {
    const origin = req.headers.get("Origin") || "";
    const allowed = ALLOWED_ORIGINS.includes(origin);
    const cors = {
      "Access-Control-Allow-Origin": allowed ? origin : ALLOWED_ORIGINS[0],
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Max-Age": "86400",
      Vary: "Origin",
    };

    const url = new URL(req.url);
    if (url.pathname !== "/join") return json({ ok: false, error: "not_found" }, 404, cors);
    if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    if (req.method !== "POST") return json({ ok: false, error: "method_not_allowed" }, 405, cors);
    if (!allowed) return json({ ok: false, error: "forbidden" }, 403, cors);

    const text = await req.text();
    if (text.length > 1024) return json({ ok: false, error: "too_large" }, 413, cors);
    let data;
    try { data = JSON.parse(text); } catch { return json({ ok: false, error: "bad_json" }, 400, cors); }

    if (data.web) return json({ ok: true }, 200, cors); // honeypot: pretend success
    const email = String(data.email || "").trim().toLowerCase();
    if (email.length > 254 || !EMAIL.test(email)) return json({ ok: false, error: "bad_email" }, 400, cors);

    try {
      // OR IGNORE: a repeat signup is a silent success, so the API never reveals who is on the list.
      await env.DB.prepare("INSERT OR IGNORE INTO signups (email) VALUES (?)").bind(email).run();
    } catch {
      return json({ ok: false, error: "server" }, 500, cors);
    }
    return json({ ok: true }, 200, cors);
  },
};
