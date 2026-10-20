from collections.abc import Iterator
from functools import lru_cache

import openai
from openai import OpenAI

from app.config import settings


class LLMError(Exception):
    """Le modèle de langage est injoignable ou a renvoyé une erreur."""


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    return OpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key.get_secret_value(),
        timeout=120.0, 
        max_retries=2,
    )


def stream_answer(messages: list[dict], temperature: float = 0.1) -> Iterator[str]:
    """Renvoie la réponse du modèle morceau par morceau."""
    try:
        stream = _client().chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        for event in stream:
            if event.choices and event.choices[0].delta.content:
                yield event.choices[0].delta.content
    except openai.OpenAIError as exc:
        raise LLMError(str(exc)) from exc


def generate(messages: list[dict], temperature: float = 0.1) -> str:
    return "".join(stream_answer(messages, temperature))