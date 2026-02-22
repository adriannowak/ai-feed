import json
from collections import Counter
from db import get_liked_items, get_disliked_items, get_tracked_embeddings


def build_preference_profile(user_id: int) -> dict:
    liked = get_liked_items(user_id, limit=30)
    disliked = get_disliked_items(user_id, limit=20)
    tracked_embeddings = get_tracked_embeddings(user_id)

    liked_titles = [i["title"] for i in liked if i.get("title")]
    disliked_titles = [i["title"] for i in disliked if i.get("title")]

    liked_topics = []
    for i in liked:
        if i.get("llm_topics"):
            try:
                liked_topics.extend(json.loads(i["llm_topics"]))
            except Exception:
                pass

    top_topics = [t for t, _ in Counter(liked_topics).most_common(15)]

    return {
        "liked_titles": liked_titles,
        "disliked_titles": disliked_titles,
        "top_topics": top_topics,
        "tracked_embeddings": tracked_embeddings,
        "has_history": len(liked) >= 5 or len(tracked_embeddings) > 0,
    }


def profile_to_text(profile: dict) -> str:
    lines = []
    if profile["top_topics"]:
        lines.append(f"Topics I like: {', '.join(profile['top_topics'])}")
    if profile["liked_titles"]:
        lines.append("Recent articles I liked:")
        for t in profile["liked_titles"][:10]:
            lines.append(f"  + {t}")
    if profile["disliked_titles"]:
        lines.append("Recent articles I did NOT like:")
        for t in profile["disliked_titles"][:10]:
            lines.append(f"  - {t}")
    return "\n".join(lines) if lines else "No preference history yet."

