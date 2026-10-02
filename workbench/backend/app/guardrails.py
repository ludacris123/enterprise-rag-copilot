import re

INJECTION = re.compile(r"ignore\s+(all\s+)?(previous|prior|system)\s+(instructions|prompts)|reveal\s+(the\s+)?(system\s+prompt|api\s+key|password)|you\s+are\s+now\s+(the\s+)?system|<\s*/?\s*system\s*>", re.I)
EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b")
PHONE = re.compile(r"(?<!\w)(?:\+\d{1,3}[ -]?)?(?:\d[ -]?){10,13}(?!\w)")
SECRET = re.compile(r"\b(?:sk-|gsk_)[A-Za-z0-9_-]{16,}\b")


def redact(text):
    text = SECRET.sub("[REDACTED_KEY]", text)
    text = EMAIL.sub("[REDACTED_EMAIL]", text)
    return PHONE.sub("[REDACTED_PHONE]", text)


def inspect_input(text):
    blocked = bool(INJECTION.search(text))
    clean = redact(text)
    return {"blocked": blocked, "redacted": clean != text, "text": clean,
            "reason": "Potential instruction override or secret extraction" if blocked else None}


def output_check(text, sources):
    clean = redact(text)
    references = [int(x) for x in re.findall(r"\[(\d+)\]", clean)]
    invalid = any(i < 1 or i > len(sources) for i in references)
    if invalid:
        return {"text": "I cannot provide a reliable answer because the generated citations were invalid.",
                "citation_valid": False, "redacted": clean != text, "refused": True}
    refused = clean.lower().startswith("i don't have enough evidence")
    # An answer from a provider must cite at least one retrieved chunk.
    if sources and not references and not refused:
        return {"text": "I cannot provide a reliable answer because the model did not cite its sources.",
                "citation_valid": False, "redacted": clean != text, "refused": True}
    return {"text": clean, "citation_valid": bool(references) and not invalid,
            "redacted": clean != text, "refused": refused}
