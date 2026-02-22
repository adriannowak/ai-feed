import json
import numpy as np
from sentence_transformers import SentenceTransformer
from db import get_conn

_model = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed_text(text: str) -> list[float]:
    model = _get_model()
    return model.encode(text[:512], normalize_embeddings=True).tolist()


def embed_item(item: dict) -> list[float]:
    combined = f"{item['title']}\n\n{item.get('text', '')[:400]}"
    return embed_text(combined)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    a, b = np.array(a), np.array(b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def store_embedding(item_id: str, embedding: list[float]):
    conn = get_conn()
    conn.execute(
        "UPDATE items SET embedding=? WHERE id=?",
        (json.dumps(embedding), item_id)
    )
    conn.commit()
    conn.close()


def max_similarity_to_liked(
    candidate_emb: list[float],
    liked_items: list[dict],
) -> float:
    if not liked_items:
        return 0.0
    scores = []
    for item in liked_items:
        if not item.get("embedding"):
            continue
        liked_emb = json.loads(item["embedding"])
        scores.append(cosine_similarity(candidate_emb, liked_emb))
    return max(scores) if scores else 0.0


def min_similarity_to_disliked(
    candidate_emb: list[float],
    disliked_items: list[dict],
) -> float:
    if not disliked_items:
        return 0.0
    scores = []
    for item in disliked_items:
        if not item.get("embedding"):
            continue
        disliked_emb = json.loads(item["embedding"])
        scores.append(cosine_similarity(candidate_emb, disliked_emb))
    return max(scores) if scores else 0.0
