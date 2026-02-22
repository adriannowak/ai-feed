import logging
import os
import requests
from datetime import date
from config import DAILY_PACK_MIN_SCORE, DAILY_PACK_MAX_ITEMS
from db import get_today_top_items, save_daily_pack, get_all_users, get_conn
from groq_client import chat_with_retry
from notifier import notify_summary

logger = logging.getLogger(__name__)


def _generate_brief(items: list[dict]) -> str:
    items_text = "\n\n".join(
        f"Title: {i['title']}\nSource: {i.get('source','')}\nURL: {i['url']}\n"
        f"Topics: {i.get('llm_topics','')}\nSummary: {i.get('summary') or i.get('text','')[:500]}"
        for i in items
    )
    prompt = f"""You are preparing a daily AI research digest.

Articles for today:
{items_text}

Write a concise daily brief in Markdown:
1. **Key themes today** (3-5 bullets)
2. **Article summaries** (1-2 sentences each, include the URL)
3. **Suggested questions to explore** in NotebookLM (5 questions)

Be concise and technical."""

    resp = chat_with_retry(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return resp.choices[0].message.content


def _save_daily_pack(today: str, items: list[dict], brief: str) -> str:
    os.makedirs("daily_packs", exist_ok=True)

    brief_path = f"daily_packs/{today}_brief.md"
    with open(brief_path, "w") as f:
        f.write(f"# AI Digest — {today}\n\n")
        f.write(brief)

    sources_path = f"daily_packs/{today}_sources.csv"
    with open(sources_path, "w") as f:
        f.write("title,url\n")
        for i in items:
            title = i["title"].replace('"', "'")
            f.write(f'"{title}",{i["url"]}\n')

    logger.info("saved: %s, %s", brief_path, sources_path)
    return brief_path


def _create_notebooklm_notebook(today: str, items: list[dict], brief: str) -> str | None:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us")
    endpoint = os.environ.get("NOTEBOOKLM_API_ENDPOINT", "us-discoveryengine.googleapis.com")

    if not project:
        logger.info("No GOOGLE_CLOUD_PROJECT set — saving locally only")
        return None

    import subprocess
    token = subprocess.check_output(
        ["gcloud", "auth", "print-access-token"]
    ).decode().strip()

    base_url = f"https://{endpoint}/v1alpha/projects/{project}/locations/{location}"

    resp = requests.post(
        f"{base_url}/notebooks",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"title": f"AI Digest {today}"},
    )
    resp.raise_for_status()
    nb_id = resp.json()["notebookId"]
    logger.info("created notebook: %s", nb_id)

    for item in items:
        requests.post(
            f"{base_url}/notebooks/{nb_id}/sources",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"webUrl": item["url"]},
        )

    requests.post(
        f"{base_url}/notebooks/{nb_id}/sources",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"textContent": {"title": f"Brief {today}", "content": brief}},
    )

    return nb_id


def _already_created(user_id: int, today: str) -> bool:
    conn = get_conn()
    row = conn.execute(
        "SELECT 1 FROM daily_packs WHERE user_id=? AND date=?", (user_id, today)
    ).fetchone()
    conn.close()
    return row is not None


def create_daily_pack():
    today = date.today().isoformat()
    users = get_all_users()
    if not users:
        logger.info("no users registered")
        return

    for user in users:
        user_id = user["user_id"]

        if _already_created(user_id, today):
            logger.info("daily pack already created for user=%s today (%s)", user_id, today)
            continue

        items = get_today_top_items(user_id, DAILY_PACK_MIN_SCORE, DAILY_PACK_MAX_ITEMS)

        if not items:
            logger.info("no items for user=%s today (%s)", user_id, today)
            continue

        logger.info("building daily pack for user=%s on %s (%d articles)", user_id, today, len(items))
        brief = _generate_brief(items)
        brief_file = _save_daily_pack(today, items, brief)
        nb_id = _create_notebooklm_notebook(today, items, brief)

        save_daily_pack(user_id, today, [i["id"] for i in items], brief)

        with open(brief_file) as f:
            logger.info("sending summary notification to user=%s", user_id)
            notify_summary(user_id, f.read())

        logger.info("done for user=%s. NotebookLM id: %s", user_id, nb_id or "n/a (saved locally)")
