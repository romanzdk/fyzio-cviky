import json
import logging
from dataclasses import dataclass, field

import httpx
from django.conf import settings

from cviky.choices import AREAS, POSITIONS

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
TIMEOUT = httpx.Timeout(20.0, connect=5.0)

AREA_KEYS = [key for key, _ in AREAS]
POSITION_KEYS = [key for key, _ in POSITIONS]

SYSTEM_PROMPT = (
    "Jsi fyzioterapeutický asistent. Z mluveného popisu cviku vytvoř strukturovaný záznam v češtině.\n"
    "Pole area musí být jedno z: " + ", ".join(AREA_KEYS) + " (nebo prázdný řetězec).\n"
    "Pole position musí být jedno z: " + ", ".join(POSITION_KEYS) + " (nebo prázdný řetězec).\n"
    "Pole tags vyplň 3 až 8 klíčovými slovy malými písmeny, včetně synonym "
    "(např. krk → krční páteř, šíje).\n"
    "Pole steps obsahuj jeden krok na řádek. reps například \"10× na každou stranu\", může být prázdné."
)


@dataclass
class ExerciseDraft:
    title: str = ""
    area: str = ""
    position: str = ""
    tags: list[str] = field(default_factory=list)
    steps: str = ""
    cautions: str = ""
    reps: str = ""


def _response_schema() -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "exercise",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "area": {"type": "string", "enum": [""] + AREA_KEYS},
                    "position": {"type": "string", "enum": [""] + POSITION_KEYS},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "steps": {"type": "string"},
                    "cautions": {"type": "string"},
                    "reps": {"type": "string"},
                },
                "required": ["title", "area", "position", "tags", "steps", "cautions", "reps"],
                "additionalProperties": False,
            },
        },
    }


def _normalize_tags(tags) -> list[str]:
    if isinstance(tags, str):
        tags = tags.split(",")
    result: list[str] = []
    for tag in tags or []:
        normalized = str(tag).strip().lower()
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _to_draft(data: dict) -> ExerciseDraft:
    area = data.get("area", "")
    position = data.get("position", "")
    return ExerciseDraft(
        title=str(data.get("title", "") or ""),
        area=area if area in AREA_KEYS else "",
        position=position if position in POSITION_KEYS else "",
        tags=_normalize_tags(data.get("tags")),
        steps=str(data.get("steps", "") or ""),
        cautions=str(data.get("cautions", "") or ""),
        reps=str(data.get("reps", "") or ""),
    )


def structure_exercise(text: str) -> ExerciseDraft:
    api_key = getattr(settings, "OPENROUTER_API_KEY", "")
    model = getattr(settings, "OPENROUTER_MODEL", "")
    if not api_key or not model:
        return ExerciseDraft()

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "provider": {"zdr": True, "data_collection": "deny"},
        "response_format": _response_schema(),
    }
    try:
        response = httpx.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return _to_draft(json.loads(content))
    except Exception:
        logger.exception("Exercise structuring via OpenRouter failed")
        return ExerciseDraft()
