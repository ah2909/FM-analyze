import re

DISCLAIMER = "Research synthesis, not financial advice."

_CONFIDENCE = {"type": "STRING", "enum": ["high", "med", "low"]}

_CITED_POINT = {
    "type": "OBJECT",
    "properties": {
        "point":      {"type": "STRING"},
        "source_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
        "confidence": _CONFIDENCE,
    },
    "required": ["point", "source_ids", "confidence"],
}

# §6 per-asset synthesis schema. `asset` and `data_coverage` are injected
# deterministically by the validation node, so the LLM does not produce them.
ASSET_OUTLOOK_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "summary":   {"type": "STRING", "description": "1-2 sentence neutral overview"},
        "bull_case": {"type": "ARRAY", "items": _CITED_POINT},
        "bear_case": {"type": "ARRAY", "items": _CITED_POINT},
        "key_risks": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "risk":       {"type": "STRING"},
                    "source_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
                "required": ["risk", "source_ids"],
            },
        },
        "catalysts_to_watch": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "event":      {"type": "STRING"},
                    "date":       {"type": "STRING", "description": "ISO date YYYY-MM-DD"},
                    "type":       {"type": "STRING",
                                   "enum": ["unlock", "roadmap", "macro", "governance", "other"]},
                    "source_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
                },
                "required": ["event", "date", "type", "source_ids"],
            },
        },
        "tokenomics_snapshot": {
            "type": "OBJECT",
            "properties": {
                "circulating_pct": {"type": "NUMBER"},
                "fdv_to_mc":       {"type": "NUMBER"},
                "emission_note":   {"type": "STRING"},
            },
            "required": ["emission_note"],
        },
    },
    "required": [
        "summary", "bull_case", "bear_case", "key_risks",
        "catalysts_to_watch", "tokenomics_snapshot",
    ],
}

# ─── Guardrails (§9) ──────────────────────────────────────────────────────────

_PRICE_PREDICTION_PATTERNS = [
    re.compile(r"\bprice target\b", re.I),
    re.compile(r"\bwill (?:reach|hit|rise to|fall to|drop to|surge to|moon)\b", re.I),
    re.compile(r"\b(?:reach|hit|target(?:ing)?)\s+\$?\d", re.I),
    re.compile(r"\bexpect[s]?\b.{0,25}\$\s?\d", re.I),
    re.compile(r"\$\s?\d[\d,.]*\s*(?:by|target|eoy|eom)\b", re.I),
    re.compile(r"\b\d+\s?x\b", re.I),
    re.compile(r"\bto the moon\b", re.I),
]

_ADVICE_PATTERNS = [
    re.compile(r"\b(?:you should|we recommend|i recommend|recommend(?:ing)?)\b", re.I),
    re.compile(r"\b(?:buy|sell|hold|accumulate|dump)\s+(?:now|this|the|your|more)\b", re.I),
]


def contains_price_prediction(text: str) -> bool:
    return any(p.search(text) for p in _PRICE_PREDICTION_PATTERNS)


def contains_advice(text: str) -> bool:
    return any(p.search(text) for p in _ADVICE_PATTERNS)
