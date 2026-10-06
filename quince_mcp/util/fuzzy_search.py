from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Callable, Sequence

try:
    from rapidfuzz import fuzz
except ImportError:
    class _Fuzz:
        @staticmethod
        def ratio(first: str, second: str) -> float:
            return SequenceMatcher(None, first, second).ratio() * 100

        @staticmethod
        def token_set_ratio(first: str, second: str) -> float:
            first_set = set(first.split())
            second_set = set(second.split())
            intersection = " ".join(sorted(first_set & second_set))
            first_only = " ".join(sorted(first_set - second_set))
            second_only = " ".join(sorted(second_set - first_set))
            return max(
                SequenceMatcher(None, intersection, f"{intersection} {first_only}".strip()).ratio() * 100,
                SequenceMatcher(None, intersection, f"{intersection} {second_only}".strip()).ratio() * 100,
            )

        @staticmethod
        def token_sort_ratio(first: str, second: str) -> float:
            return SequenceMatcher(None, " ".join(sorted(first.split())), " ".join(sorted(second.split()))).ratio() * 100

        @staticmethod
        def partial_ratio(first: str, second: str) -> float:
            shorter, longer = sorted((first, second), key=len)
            if not shorter:
                return 0.0
            if shorter in longer:
                return 100.0
            best = 0.0
            width = len(shorter)
            for index in range(max(1, len(longer) - width + 1)):
                best = max(best, SequenceMatcher(None, shorter, longer[index:index + width]).ratio() * 100)
            return best

    fuzz = _Fuzz()


@dataclass(frozen=True)
class FuzzyMatch:
    candidate: Any
    score: float
    exact: bool


def _normalize(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = value.replace("_", " ").replace("-", " ")
    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _tokens(value: str) -> list[str]:
    return [token for token in _normalize(value).split() if token]


def _token_overlap(query_tokens: list[str], candidate_tokens: list[str]) -> float:
    if not query_tokens or not candidate_tokens:
        return 0.0

    candidate_set = set(candidate_tokens)
    matched = sum(1 for token in query_tokens if token in candidate_set)
    return matched / len(set(query_tokens))


def _token_fuzzy_overlap(query_tokens: list[str], candidate_tokens: list[str]) -> float:
    if not query_tokens or not candidate_tokens:
        return 0.0

    scores = []

    for query_token in set(query_tokens):
        best = max(fuzz.ratio(query_token, candidate_token) for candidate_token in set(candidate_tokens))
        scores.append(best / 100)

    return sum(scores) / len(scores)


def _score(query: str, candidate: str) -> tuple[float, bool]:
    normalized_query = _normalize(query)
    normalized_candidate = _normalize(candidate)

    if not normalized_query or not normalized_candidate:
        return 0.0, False

    if normalized_query == normalized_candidate:
        return 100.0, True

    query_tokens = _tokens(normalized_query)
    candidate_tokens = _tokens(normalized_candidate)
    overlap = _token_overlap(query_tokens, candidate_tokens)
    fuzzy_overlap = _token_fuzzy_overlap(query_tokens, candidate_tokens)

    ratio = fuzz.ratio(normalized_query, normalized_candidate)
    token_set = fuzz.token_set_ratio(normalized_query, normalized_candidate)
    token_sort = fuzz.token_sort_ratio(normalized_query, normalized_candidate)
    partial = fuzz.partial_ratio(normalized_query, normalized_candidate)
    sequence = SequenceMatcher(None, normalized_query, normalized_candidate).ratio() * 100

    score = (
        ratio * 0.18
        + token_set * 0.28
        + token_sort * 0.14
        + partial * 0.12
        + sequence * 0.08
        + overlap * 100 * 0.12
        + fuzzy_overlap * 100 * 0.08
    )

    if query_tokens and overlap == 1.0:
        score = max(score, 96.0 if len(query_tokens) >= 2 else 88.0)

    if len(query_tokens) >= 2 and overlap >= 0.5 and fuzzy_overlap >= 0.88:
        score = max(score, 84.0 + min(12.0, fuzzy_overlap * 8.0))

    if normalized_candidate.startswith(normalized_query) or normalized_query.startswith(normalized_candidate):
        score = max(score, 93.0)

    if len(query_tokens) == 1 and len(candidate_tokens) > 1 and query_tokens[0] in candidate_tokens:
        score = min(score, 88.0)

    return min(score, 100.0), False


def smart_fuzzy_search(
    candidates: Sequence[Any],
    query: str,
    threshold: float = 80.0,
    key: Callable[[Any], str] | None = None,
    limit: int | None = None,
) -> list[FuzzyMatch]:
    if threshold < 0 or threshold > 100:
        raise ValueError("threshold must be between 0 and 100")

    if not isinstance(query, str) or not query.strip():
        return []

    get_text = key or (lambda candidate: str(candidate))
    matches: list[FuzzyMatch] = []

    for candidate in candidates:
        candidate_text = get_text(candidate)

        if not isinstance(candidate_text, str) or not candidate_text.strip():
            continue

        score, exact = _score(query, candidate_text)

        if score >= threshold:
            matches.append(
                FuzzyMatch(
                    candidate=candidate,
                    score=round(score, 2),
                    exact=exact,
                )
            )

    matches.sort(key=lambda match: (-match.score, str(get_text(match.candidate)).casefold()))

    if limit is not None:
        if limit < 1:
            return []
        matches = matches[:limit]

    return matches


def resolve_fuzzy_match(
    candidates: Sequence[Any],
    query: str,
    threshold: float = 80.0,
    key: Callable[[Any], str] | None = None,
    ambiguity_margin: float = 6.0,
) -> FuzzyMatch | None:
    matches = smart_fuzzy_search(
        candidates=candidates,
        query=query,
        threshold=threshold,
        key=key,
        limit=2,
    )

    if not matches:
        return None

    if len(matches) == 1:
        return matches[0]

    first = matches[0]
    second = matches[1]

    if first.exact:
        return first

    if first.score - second.score < ambiguity_margin:
        return None

    return first
