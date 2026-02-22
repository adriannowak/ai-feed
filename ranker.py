import json
import os
from groq import Groq
from config import (
    EMBEDDING_SIMILARITY_THRESHOLD,
    LLM_SCORE_THRESHOLD,
    COLD_START_KEYWORDS,
)
from embeddings import embed_item, store_embedding, max_similarity_to_liked, min_similarity_to_disliked
from profile import build_preference_profile, profile_to_text
from db import get_liked_items, get_disliked_items, update_item_score

groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
JUDGE_MODEL = "llama-3.3-70b-versatile"


def _cold_start_matches(item: dict) -> bool:
    text = (item.get("title", "") + " " + item.get("text", "")).lower()
    return any(kw in text for kw in COLD_START_KEYWORDS)


def _llm_judge(item: dict, profile_text: str) -> dict:
    excerpt = item.get("text", "")[:1500]
    prompt = f"""You are a personalized article recommender.

User preference profile:
{profile_text}

Candidate article:
Title: {item['title']}
Source: {item.get('source', '')}
Excerpt: {excerpt}

Task:
1. Score relevance 0-100 (100 = perfect match for user's interests)
2. Extract up to 5 topic tags
3. One-sentence reason

Respond ONLY with valid JSON:
{{
  "score": <int 0-100>,
  "topics": ["tag1", "tag2"],
  "reason": "..."
}}"""

    resp = groq_client.chat.completions.create(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def score_item(item: dict) -> dict | None:
    profile = build_preference_profile()
    liked = get_liked_items()
    disliked = get_disliked_items()

    emb = embed_item(item)
    store_embedding(item["id"], emb)

    if not profile["has_history"]:
        if not _cold_start_matches(item):
            return None
        profile_text = "No history yet. Focus on AI/ML research, LLM serving, inference optimization."
        result = _llm_judge(item, profile_text)
        update_item_score(item["id"], result["score"], result["topics"], result["reason"])
        return {**item, **result} if result["score"] >= LLM_SCORE_THRESHOLD else None

    sim_liked = max_similarity_to_liked(emb, liked)
    sim_disliked = min_similarity_to_disliked(emb, disliked)
    adj_score = sim_liked - 0.5 * sim_disliked

    if adj_score < EMBEDDING_SIMILARITY_THRESHOLD:
        return None

    profile_text = profile_to_text(profile)
    result = _llm_judge(item, profile_text)
    update_item_score(item["id"], result["score"], result["topics"], result["reason"])

    if result["score"] >= LLM_SCORE_THRESHOLD:
        return {**item, **result}
    return None
