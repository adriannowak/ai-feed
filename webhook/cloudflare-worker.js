/**
 * Cloudflare Worker — Telegram webhook receiver + GitHub dispatch relay
 *
 * Environment variables to set in Cloudflare dashboard:
 *   TELEGRAM_BOT_TOKEN  — your bot token
 *   GH_PAT              — GitHub Personal Access Token (repo scope)
 *   GITHUB_REPO         — e.g. "adriannowak/ai-feed"
 *   ALLOWED_USER_IDS    — comma-separated Telegram user IDs that may use the bot
 *                         e.g. "123456789,987654321"  (leave empty to deny everyone)
 *
 * After deploying, register this worker as your Telegram webhook (one-time):
 *   curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
 *     -H "Content-Type: application/json" \
 *     -d '{"url": "https://YOUR_WORKER.YOUR_NAME.workers.dev"}'
 *
 * Architecture — two update types are handled:
 *
 *  1. callback_query (👍/👎 buttons on article notifications)
 *     → Dispatches a "feedback" repository_dispatch event to GitHub Actions
 *     → Handled by .github/workflows/feedback.yml → run_feedback.py
 *
 *  2. message with a bot command (/start, /add, /track, /feeds)
 *     → Immediately ACKs the user with "⏳ Processing…"
 *     → Dispatches a "bot_command" repository_dispatch event to GitHub Actions
 *     → Handled by .github/workflows/bot_command.yml → run_command.py
 *     → run_command.py performs the DB operation and sends the real reply
 *
 * NOTE: You cannot use this webhook mode and run bot.py (polling mode)
 * simultaneously — Telegram only allows one active update receiver at a time.
 * Use bot.py when you have a persistent server; use this worker for a fully
 * serverless setup backed by GitHub Actions.
 */

async function dispatchToGitHub(env, event_type, client_payload) {
  return fetch(
    `https://api.github.com/repos/${env.GITHUB_REPO}/dispatches`,
    {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${env.GH_PAT}`,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "ai-feed-bot",
      },
      body: JSON.stringify({ event_type, client_payload }),
    }
  );
}

/**
 * Parse the ALLOWED_USER_IDS env var into a Set of numeric IDs.
 * Returns an empty Set if the variable is not set or empty.
 */
function getAllowedIds(env) {
  const raw = env.ALLOWED_USER_IDS || "";
  const ids = new Set();
  for (const part of raw.split(",")) {
    const n = Number(part.trim());
    if (Number.isInteger(n) && n > 0) ids.add(n);
  }
  return ids;
}

async function sendMessage(env, chat_id, text) {
  console.log("Sending message to chat_id", chat_id, ":", text);
  let url = `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`
  return fetch(
    url,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id, text }),
    }
  );
}

export default {
  async fetch(request, env) {

    // health check
    if (request.method !== "POST") {
      return new Response("AI Feed webhook OK", { status: 200 });
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return new Response("Bad JSON", { status: 400 });
    }
    console.log("Received update:", JSON.stringify(body));

    // ── 1. Inline button callbacks (👍 / 👎) ────────────────────────────────
    const cb = body?.callback_query;
    if (cb) {
      const user_id = cb.from.id;
      const allowedIds = getAllowedIds(env);

      if (!allowedIds.has(user_id)) {
        await fetch(
          `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              callback_query_id: cb.id,
              text: "⛔ Access denied.",
              show_alert: true,
            }),
          }
        );
        return new Response("OK", { status: 200 });
      }

      // Immediately answer to remove the loading spinner
      await fetch(
        `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/answerCallbackQuery`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            callback_query_id: cb.id,
            text: cb.data.startsWith("like") ? "👍 Liked!" : "👎 Disliked!",
          }),
        }
      );

      const [action, item_id] = cb.data.split(":");
      if (item_id) {
        const signal = action === "like" ? 1 : -1;
        await dispatchToGitHub(env, "feedback", { item_id, signal, user_id });
      }

      return new Response("OK", { status: 200 });
    }

    // ── 2. Text commands (/start, /add, /track, /feeds) ─────────────────────
    const msg = body?.message;
    if (msg?.text?.startsWith("/")) {
      const user_id = msg.from.id;
      const chat_id = msg.chat.id;
      const username = msg.from.username || "";
      const allowedIds = getAllowedIds(env);

      if (!allowedIds.has(user_id)) {
        await sendMessage(
          env,
          chat_id,
          "⛔ Sorry, this bot is invite-only. Contact the owner to request access."
        );
        return new Response("OK", { status: 200 });
      }

      // Parse "/command args…" — strip bot mention (e.g. /start@mybot)
      const full_text = msg.text.trim();
      const [raw_command, ...rest] = full_text.split(/\s+/);
      const command = raw_command.split("@")[0].replace("/", "").toLowerCase();
      const args = rest.join(" ");
      if (!["start", "add", "track", "feeds", "poll"].includes(command)) {
        await sendMessage(env, chat_id, "❓ Unknown command. Available: /start, /add, /track, /feeds, /pool");
        return new Response("OK", { status: 200 });
      }
      if (command === "poll") {
        await sendMessage(env, chat_id, "⏳ Polling for new articles…");
        await dispatchToGitHub(env, "poll", {});
        return new Response("OK", { status: 200 });
      }

      // ACK the user immediately so Telegram doesn't show the message as pending
      (async () => {
            response = await sendMessage(env, chat_id, "Processing... ⏳");
            console.log("Sent ACK message, response status:", response);
      })();
      // Dispatch to GitHub Actions — run_command.py will send the real reply
      await dispatchToGitHub(env, "bot_command", {
        user_id,
        chat_id,
        username,
        command,
        args,
      });

      return new Response("OK", { status: 200 });
    }

    return new Response("OK", { status: 200 });
  },
};



