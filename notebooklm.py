import os
import json
import requests
from datetime import date
from groq import Groq
from config import DAILY_PACK_MIN_SCORE, DAILY_PACK_MAX_ITEMS
from db import get_today_top_items, save_daily_pack, get_all_users


def get_groq_client():
    """Lazily construct and return a Groq client using GROQ_API_KEY from env.

    Raises a RuntimeError with a helpful message if the env var is missing so
    imports don't fail at module import time.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set in the environment. Set it or provide a mock for local runs."
        )
    return Groq(api_key=api_key)


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

    groq_client = get_groq_client()
    resp = groq_client.chat.completions.create(
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

    print(f"[notebooklm] saved: {brief_path}, {sources_path}")
    return brief_path


def _create_notebooklm_notebook(today: str, items: list[dict], brief: str) -> str | None:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us")
    endpoint = os.environ.get("NOTEBOOKLM_API_ENDPOINT", "us-discoveryengine.googleapis.com")

    if not project:
        print("[notebooklm] No GOOGLE_CLOUD_PROJECT set — saving locally only")
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
    print(f"[notebooklm] created notebook: {nb_id}")

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


def create_daily_pack():
    today = date.today().isoformat()
    users = get_all_users()
    if not users:
        print(f"[notebooklm] no users registered")
        return

    for user in users:
        user_id = user["user_id"]
        items = get_today_top_items(user_id, DAILY_PACK_MIN_SCORE, DAILY_PACK_MAX_ITEMS)

        if not items:
            print(f"[notebooklm] no items for user={user_id} today ({today})")
            continue

        print(f"[notebooklm] building daily pack for user={user_id} on {today} ({len(items)} articles)")
        brief = _generate_brief(items)
        _save_daily_pack(today, items, brief)
        nb_id = _create_notebooklm_notebook(today, items, brief)

        save_daily_pack(user_id, today, [i["id"] for i in items], brief)

        print(f"[notebooklm] done for user={user_id}. NotebookLM id: {nb_id or 'n/a (saved locally)'}")
