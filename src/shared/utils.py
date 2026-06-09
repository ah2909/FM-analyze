import json
import re

from json_repair import repair_json


def parse_json_response(text: str) -> dict:
    """Parse JSON from a Gemini response, handling markdown fences and stray characters."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    repaired = repair_json(cleaned)
    result = json.loads(repaired)
    if not isinstance(result, dict):
        raise ValueError(f"Cannot parse JSON from Gemini response. First 300 chars: {text[:300]!r}")
    return result
