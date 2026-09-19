"""Conservative deterministic metadata matching."""

import re
import unicodedata

from src.models import Metadata, MovieIdentity

AUTO_THRESHOLD = 0.90
CANDIDATE_THRESHOLD = 0.75
MIN_MARGIN = 0.10

_QUALITY_SUFFIX = re.compile(
    r"\s*\(\s*(?:臻彩|4k|8k|高清|超清|蓝光|蓝光版|抢先版|tc|ts|cam)\s*\)\s*$",
    re.IGNORECASE,
)
_YEAR = re.compile(r"(?:19|20)\d{2}")


def query_title(value: str) -> str:
    title = unicodedata.normalize("NFKC", value or "").strip()
    cleaned = _QUALITY_SUFFIX.sub("", title).strip()
    return cleaned or title


def normalize(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "").lower()
    return "".join(character for character in text if character.isalnum())


def score(source: MovieIdentity, candidate: Metadata) -> float:
    if hard_conflict(source, candidate):
        return 0.0
    points = similarity(query_title(source.title), candidate.title) * 0.45
    weight = 0.45
    if first_year(source.year) and first_year(candidate.year):
        points += float(first_year(source.year) == first_year(candidate.year)) * 0.20
        weight += 0.20
    for left, right, value in (
        (source.director, candidate.directors, 0.15),
        (source.actors, candidate.actors, 0.10),
        (source.area, candidate.area, 0.05),
        (source.type, candidate.type, 0.05),
    ):
        if normalize(left) and normalize(right):
            points += overlap(left, right) * value
            weight += value
    return clamp(points / weight)


def is_automatic(best: float, second: float) -> bool:
    return best >= AUTO_THRESHOLD and best - second >= MIN_MARGIN


def is_candidate(value: float) -> bool:
    return value >= CANDIDATE_THRESHOLD


def hard_conflict(source: MovieIdentity, candidate: Metadata) -> bool:
    source_year = first_year(source.year)
    candidate_year = first_year(candidate.year)
    return bool(
        source_year
        and candidate_year
        and abs(int(source_year) - int(candidate_year)) > 1
    )


def corroboration_count(source: MovieIdentity, candidate: Metadata) -> int:
    count = 0
    if first_year(source.year) and first_year(source.year) == first_year(candidate.year):
        count += 1
    for left, right in (
        (source.director, candidate.directors),
        (source.actors, candidate.actors),
        (source.area, candidate.area),
        (source.type, candidate.type),
    ):
        if normalize(left) and normalize(right) and overlap(left, right) > 0:
            count += 1
    return count


def similarity(left: str, right: str) -> float:
    a, b = normalize(left), normalize(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    distance = levenshtein(a, b)
    edit = 1.0 - distance / max(len(a), len(b))
    intersection = sum(1 for character in a if character in b)
    shared = intersection / max(len(a), len(b))
    return clamp(edit * 0.65 + shared * 0.35)


def overlap(left: str, right: str) -> float:
    a, b = normalize(left), normalize(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return 0.8 if a in b or b in a else 0.0


def first_year(value: str) -> str:
    match = _YEAR.search(value or "")
    return match.group() if match else ""


def levenshtein(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_character in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1] + int(left_character != right_character),
                )
            )
        previous = current
    return previous[-1]


def clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
