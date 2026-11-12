"""
Deterministic yes/no parser for confirmation flow, plus question templates.
No LLM involved — pure string matching.
"""
from __future__ import annotations

import re
import string

YES_WORDS = {
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay",
    "proceed", "confirm", "confirmed", "go ahead", "do it", "send it",
    "please do", "absolutely", "definitely", "correct", "affirmative",
}

NO_WORDS = {
    "no", "nope", "nah", "stop", "cancel", "don't", "dont", "do not",
    "wait", "hold on", "negative", "never", "abort",
}


def _normalize(text: str) -> str:
    """Lowercase, strip punctuation."""
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    return " ".join(text.split())


def parse_yes_no(answer: str) -> str:
    """
    Return 'yes', 'no', or 'ambiguous'.
    Checks for YES/NO multi-word phrases first, then single tokens.
    """
    if not answer or not answer.strip():
        return "no"  # empty → safe default

    norm = _normalize(answer)

    # Check multi-word phrases
    yes_found = any(phrase in norm for phrase in YES_WORDS if " " in phrase)
    no_found = any(phrase in norm for phrase in NO_WORDS if " " in phrase)

    # Check single tokens
    tokens = set(norm.split())
    yes_found = yes_found or bool(tokens & {w for w in YES_WORDS if " " not in w})
    no_found = no_found or bool(tokens & {w for w in NO_WORDS if " " not in w})

    if yes_found and not no_found:
        return "yes"
    if no_found and not yes_found:
        return "no"
    if not yes_found and not no_found:
        return "no"   # neither → safe default (no)
    return "ambiguous"


# ---------------------------------------------------------------------------
# Question templates (deterministic, no LLM)
# ---------------------------------------------------------------------------

# Verb table: name-fragment → natural phrasing
_VERB_TABLE = {
    "send": "send this",
    "submit": "submit this",
    "pay": "pay",
    "pay now": "pay now",
    "place order": "place this order",
    "purchase": "purchase this",
    "buy": "buy this",
    "buy now": "buy now",
    "confirm": "confirm",
    "confirm order": "confirm this order",
    "delete": "delete this",
    "remove": "remove this",
    "erase": "erase this",
    "unsubscribe": "unsubscribe",
    "post": "post this",
    "publish": "publish this",
    "share": "share this",
    "transfer": "transfer",
    "withdraw": "withdraw",
    "sign out": "sign out",
    "log out": "log out",
    "logout": "log out",
    "authorize": "authorize this",
    "allow": "allow this",
    "grant": "grant access",
    "accept": "accept",
    "agree": "agree",
    "apply": "apply",
    "checkout": "check out",
    "donate": "donate",
    "book": "book this",
    "reserve": "reserve this",
    "subscribe": "subscribe",
    "deactivate": "deactivate this",
    "close account": "close the account",
    "submit application": "submit this application",
}


def _natural_verb(name: str) -> str:
    """Map a button name to a natural verb phrase."""
    low = name.lower().strip()
    for key, phrase in _VERB_TABLE.items():
        if key in low:
            return phrase
    return f'click "{name}"'


def build_confirmation_question(name: str, host: str, action_tool: str) -> str:
    """
    Build a short confirmation question (≤160 chars).
    Sanitizes name (strips control chars, truncates to 40 chars).
    """
    # Sanitize name
    safe_name = re.sub(r"[\x00-\x1f\x7f]", "", name)[:40].strip()
    verb = _natural_verb(safe_name)
    q = f"Should I {verb}? The button says \"{safe_name}\" on {host}."
    if len(q) > 160:
        q = f"Should I {verb} on {host}?"
    return q[:160]


AMBIGUOUS_RETRY_QUESTION = "Sorry, I didn't catch that. Should I go ahead? Please say yes or no."
