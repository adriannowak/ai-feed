"""Shared Groq client utilities with retry logic for transient errors."""
import logging
import os
import time

from groq import (
    APIConnectionError,
    APITimeoutError,
    Groq,
    InternalServerError,
    RateLimitError,
)
from groq.types.chat import ChatCompletion

logger = logging.getLogger(__name__)

_client: Groq | None = None

_RETRYABLE = (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)
_MAX_RETRIES = 5
_BASE_DELAY = 2.0  # seconds


def get_client() -> Groq:
    """Return a lazily-initialised Groq singleton.

    Raises RuntimeError if GROQ_API_KEY is not set.
    """
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set in the environment. "
                "Set it or provide a mock for local runs."
            )
        _client = Groq(api_key=api_key)
    return _client


def chat_with_retry(**kwargs) -> ChatCompletion:
    """Call ``client.chat.completions.create`` with exponential-backoff retry.

    Retries on :class:`~groq.RateLimitError`, :class:`~groq.APIConnectionError`,
    :class:`~groq.APITimeoutError`, and :class:`~groq.InternalServerError` up to
    ``_MAX_RETRIES`` times before re-raising.
    """
    delay = _BASE_DELAY
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return get_client().chat.completions.create(**kwargs)
        except _RETRYABLE as exc:
            if attempt == _MAX_RETRIES:
                logger.error("Groq API failed after %d attempts: %s", attempt, exc)
                raise
            wait = delay * (2 ** (attempt - 1))
            logger.warning(
                "Groq API error (%s), retrying in %.1fs (attempt %d/%d)",
                type(exc).__name__,
                wait,
                attempt,
                _MAX_RETRIES,
            )
            time.sleep(wait)
