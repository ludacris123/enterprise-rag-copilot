import re
from dataclasses import dataclass

@dataclass
class GuardrailDecision:
    allowed: bool
    value: str
    reasons: list[str]

INJECTION = [
    re.compile(r"ignore (all |the )?(previous|system) instructions", re.I),
    re.compile(r"(reveal|print|show).{0,20}(system prompt|developer message)", re.I),
    re.compile(r"(bypass|disable).{0,20}(guardrail|security|policy)", re.I),
]
PII = {
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "phone": re.compile(r"(?<!\d)(?:\+91[- ]?)?[6-9]\d{9}(?!\d)"),
    "card": re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
}

def inspect_input(text: str, max_chars: int) -> GuardrailDecision:
    reasons = []
    if len(text) > max_chars:
        reasons.append("input_too_long")
    if any(pattern.search(text) for pattern in INJECTION):
        reasons.append("prompt_injection")
    return GuardrailDecision(not reasons, text, reasons)

def redact_pii(text: str) -> GuardrailDecision:
    reasons, value = [], text
    for label, pattern in PII.items():
        updated = pattern.sub(f"[REDACTED_{label.upper()}]", value)
        if updated != value:
            reasons.append(f"redacted_{label}")
        value = updated
    return GuardrailDecision(True, value, reasons)

def validate_citations(answer: str, excerpts: list[str]) -> bool:
    if not excerpts:
        return False
    # Production hook: replace with NLI/LLM claim-level entailment grader.
    answer_tokens = set(re.findall(r"\w+", answer.lower()))
    context_tokens = set(re.findall(r"\w+", " ".join(excerpts).lower()))
    return len(answer_tokens & context_tokens) >= min(5, max(1, len(answer_tokens) // 5))
