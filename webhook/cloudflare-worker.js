/**
 * Cloudflare Worker — Telegram webhook receiver + GitHub dispatch relay
 *
 * Environment variables to set in Cloudflare dashboard:
 *   TELEGRAM_BOT_TOKEN  — your bot token
 *   GH_PAT              — GitHub Personal Access Token (repo scope)
 *   GITHUB_REPO         — e.g. "adriannowak/ai-feed"
 *
 * After deploying, register this worker as your Telegram webhook (one-time):
 *   curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
 *     -H "Content-Type: application/json" \
 *     -d '{"url": "https://YOUR_WORKER.YOUR_NAME.workers.dev"}'
 */

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

    // only handle callback_query (inline button presses)
    const cb = body?.callback_query;
    if (!cb) {
      return new Response("OK", { status: 200 });
    }

    // answer callback immediately — removes loading spinner on button
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

    // parse callback_data: "like:ITEM_ID" or "dislike:ITEM_ID"
    const [action, item_id] = cb.data.split(":");
    if (!item_id) {
      return new Response("OK", { status: 200 });
    }
    const signal = action === "like" ? 1 : -1;
    const user_id = cb.from.id;

    // fire GitHub repository_dispatch → triggers feedback.yml workflow
    await fetch(
      `https://api.github.com/repos/${env.GITHUB_REPO}/dispatches`,
      {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${env.GH_PAT}`,
          "Accept": "application/vnd.github+json",
          "Content-Type": "application/json",
          "User-Agent": "ai-feed-bot",
        },
        body: JSON.stringify({
          event_type: "feedback",
          client_payload: { item_id, signal, user_id },
        }),
      }
    );

    return new Response("OK", { status: 200 });
  },
};
