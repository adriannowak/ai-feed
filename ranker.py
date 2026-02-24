import json
import logging

import numpy as np
from groq import RateLimitError

from config import (
    COLD_START_KEYWORDS,
    EMBEDDING_SIMILARITY_THRESHOLD,
    LLM_SCORE_THRESHOLD,
)
from db import get_disliked_items, get_liked_items, save_user_score, update_item_summary
from embeddings import (
    avg_similarity_to_liked,
    cosine_similarity,
    embed_item,
    max_similarity_to_liked,
    min_similarity_to_disliked,
    store_embedding,
)
from groq_client import chat_with_retry
from user_profile import build_preference_profile, profile_to_text

logger = logging.getLogger(__name__)

JUDGE_MODEL = "llama-3.3-70b-versatile"


def _cold_start_matches(item: dict) -> bool:
    text = (item.get("title", "") + " " + item.get("text", "")).lower()
    return any(kw in text for kw in COLD_START_KEYWORDS)


def _topic_keyword_matches(item: dict, top_topics: list[str]) -> bool:
    """Return True if the item contains any of the user's top topic keywords.

    Used as a fallback when embedding similarity is below the threshold but
    the user has a known topic history — avoids silently dropping articles
    that are topically relevant but happen to be phrased differently from
    previously liked items.
    """
    if not top_topics:
        return False
    text = (item.get("title", "") + " " + item.get("text", "")).lower()
    return any(topic.lower() in text for topic in top_topics)


def _llm_judge(item: dict, profile_text: str) -> dict | None:
    """Ask the LLM to score and tag an article against a user preference profile.

    Returns a dict with ``score``, ``topics``, and ``reason`` keys on success.
    Returns ``None`` if the LLM response cannot be parsed (e.g. malformed JSON,
    missing fields, or an empty/truncated API response).
    """
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

    try:
        resp = chat_with_retry(
            model=JUDGE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)
    except (json.JSONDecodeError, AttributeError, IndexError, RateLimitError) as exc:
        logger.error("Failed to parse LLM response for item %s: %s", item.get("id"), exc)
        return None


def score_item(item: dict, user_id: int) -> dict | None:
    profile = build_preference_profile(user_id)
    liked = get_liked_items(user_id)
    disliked = get_disliked_items(user_id)

    emb = embed_item(item)
    store_embedding(item["id"], emb)

    if not profile["has_history"]:
        if not _cold_start_matches(item):
            return None
        profile_text = "No history yet. Focus on AI/ML research, LLM serving, inference optimization."
        result = _llm_judge(item, profile_text)
        if result is None or result["score"] < LLM_SCORE_THRESHOLD:
            return None
        save_user_score(user_id, item["id"], result["score"], result["topics"], result["reason"])
        update_item_summary(item["id"], result["reason"])
        return {**item, **result}

    sim_liked_max = max_similarity_to_liked(emb, liked)
    sim_liked_avg = avg_similarity_to_liked(emb, liked)

    # Boost similarity using tracked article embeddings
    tracked_embs = profile.get("tracked_embeddings", [])
    if tracked_embs:
        tracked_sims = [cosine_similarity(emb, te) for te in tracked_embs]
        tracked_max = max(tracked_sims)
        sim_liked_max = max(sim_liked_max, tracked_max)
        sim_liked_avg = max(sim_liked_avg, float(np.mean(sorted(tracked_sims, reverse=True)[:5])))

    sim_disliked = min_similarity_to_disliked(emb, disliked)

    # Blend max and avg: max catches single strong matches, avg rewards
    # consistent relevance across the whole liked history
    sim_liked = 0.7 * sim_liked_max + 0.3 * sim_liked_avg
    adj_score = sim_liked - 0.5 * sim_disliked

    logger.debug(
        "item %s — max=%.3f avg=%.3f blended=%.3f disliked=%.3f adj=%.3f — %s",
        item["id"], sim_liked_max, sim_liked_avg, sim_liked,
        sim_disliked, adj_score, item["title"][:60],
    )

    # Fallback: if embedding score is low but the item matches user's known
    # topics, still send it to the LLM — topic keywords are a cheap signal
    # that catches articles phrased differently from previously liked items
    topic_match = _topic_keyword_matches(item, profile.get("top_topics", []))

    # if adj_score < EMBEDDING_SIMILARITY_THRESHOLD and not topic_match:
    #     logger.info(
    #         "item %s skipped — adj=%.3f < %.3f, no topic keyword match: %s",
    #         item["id"], adj_score, EMBEDDING_SIMILARITY_THRESHOLD, item["title"][:60],
    #     )
    #     return None
    #
    # if adj_score < EMBEDDING_SIMILARITY_THRESHOLD and topic_match:
    #     logger.info(
    #         "item %s — low embedding (adj=%.3f) but topic keyword matched, sending to LLM: %s",
    #         item["id"], adj_score, item["title"][:60],
    #     )

    profile_text = profile_to_text(profile)
    result = _llm_judge(item, profile_text)
    if result is None or result["score"] < LLM_SCORE_THRESHOLD:
        return None
    save_user_score(user_id, item["id"], result["score"], result["topics"], result["reason"])
    update_item_summary(item["id"], result["reason"])
    return {**item, **result}
