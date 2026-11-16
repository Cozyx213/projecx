"""Text similarity between project proposals.

Pure Python and independent of Django: every function takes plain dictionaries
of proposal sections, so the scoring can be tested without a database.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal

# Section name -> (label, weight). Heavier sections say more about the idea.
SECTIONS = {
    "title": ("Title", 2.0),
    "description": ("Short description", 2.0),
    "problem_statement": ("Problem statement", 3.0),
    "proposed_solution": ("Proposed solution", 3.0),
    "target_users": ("Target users", 1.5),
    "features": ("Key features", 2.0),
    "objectives": ("Objectives", 1.0),
    "scope": ("Scope and limitations", 1.0),
    "category": ("Category", 0.5),
}
MIN_SCORE = Decimal("10")
HIGH_SCORE = Decimal("70")
MODERATE_SCORE = Decimal("40")

STOP_WORDS = frozenset(
    """a about above after again all also am an and any are as at be because been
    before being below between both but by can could did do does doing down during
    each few for from further had has have having he her here hers him his how i if
    in into is it its just like make many may me more most must my no nor not now of
    off on once only or other our out over own same she should so some such than
    that the their them then there these they this those through to too under until
    up use used using very want was we were what when where which while who why
    will with would you your project system app application""".split()
)
_WORD = re.compile(r"[a-z0-9]+")


def _stem(word):
    """Reduce a word to a rough root so plurals and verb forms match."""
    if word.endswith(("sses", "ches", "shes", "xes")):
        return word[:-2]
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    for suffix in ("ing", "ed"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    if word.endswith("s") and len(word) > 3 and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def _words(text):
    return [
        word for word in _WORD.findall((text or "").lower())
        if len(word) > 2 and word not in STOP_WORDS
    ]


def tokenize(text):
    """Lower-cased, stemmed content words of a text."""
    return [_stem(word) for word in _words(text)]


def cosine(first, second):
    """Cosine similarity of two term-count mappings, from 0.0 to 1.0."""
    if not first or not second:
        return 0.0
    dot = sum(count * second[term] for term, count in first.items() if term in second)
    if not dot:
        return 0.0
    norm = math.sqrt(sum(c * c for c in first.values())) * math.sqrt(
        sum(c * c for c in second.values())
    )
    return min(dot / norm, 1.0)


@dataclass
class Comparison:
    score: Decimal
    shared_terms: list = field(default_factory=list)
    section_scores: dict = field(default_factory=dict)

    @property
    def strongest_section(self):
        # A shared category alone says little, so it never counts as the reason.
        scores = {k: v for k, v in self.section_scores.items() if k != "category" and v > 0}
        return max(scores, key=scores.get) if scores else None


def compare(proposal, other):
    """Compare two proposals given as {section name: text}."""
    counts, other_counts = {}, {}
    for name in SECTIONS:
        counts[name] = Counter(tokenize(proposal.get(name)))
        other_counts[name] = Counter(tokenize(other.get(name)))

    section_scores = {
        name: cosine(counts[name], other_counts[name])
        for name in SECTIONS
        if counts[name] and other_counts[name]
    }
    whole = cosine(sum(counts.values(), Counter()), sum(other_counts.values(), Counter()))
    if section_scores:
        weight = sum(SECTIONS[name][1] for name in section_scores)
        by_section = sum(SECTIONS[name][1] * value for name, value in section_scores.items()) / weight
        overall = (whole + by_section) / 2
    else:
        overall = whole

    total, other_total = sum(counts.values(), Counter()), sum(other_counts.values(), Counter())
    shared = sorted(
        set(total) & set(other_total),
        key=lambda term: (-min(total[term], other_total[term]), term),
    )
    # Show readers a real word from the proposal rather than its stem.
    readable = {}
    for name in SECTIONS:
        for word in _words(proposal.get(name)):
            stem = _stem(word)
            if stem not in readable or len(word) < len(readable[stem]):
                readable[stem] = word
    return Comparison(
        score=Decimal(str(overall * 100)).quantize(Decimal("0.01")),
        shared_terms=[readable[term] for term in shared[:8]],
        section_scores=section_scores,
    )


def explain(comparison):
    """One or two sentences describing why two proposals matched."""
    parts = []
    strongest = comparison.strongest_section
    if strongest:
        percent = round(comparison.section_scores[strongest] * 100)
        parts.append(f"Strongest overlap is in the {SECTIONS[strongest][0].lower()} ({percent}%).")
    if comparison.shared_terms:
        parts.append("Shared terms: " + ", ".join(comparison.shared_terms) + ".")
    return " ".join(parts) or "The proposals share general wording only."


def recommend(proposal, matches):
    """Suggestions for a proposal.

    ``matches`` is a list of (title, Comparison) pairs, highest score first.
    """
    suggestions = []
    if not matches:
        suggestions.append(
            "No similar projects were found. Your idea looks distinct among the "
            "projects available for comparison."
        )
    else:
        title, top = matches[0]
        strongest = top.strongest_section
        where = f" in the {SECTIONS[strongest][0].lower()}" if strongest else ""
        if top.score >= HIGH_SCORE:
            suggestions.append(
                f"This proposal is very close to “{title}” ({top.score:.0f}%). Consider a "
                "different core solution or a narrower group of target users."
            )
        elif top.score >= MODERATE_SCORE:
            suggestions.append(
                f"This proposal overlaps with “{title}” ({top.score:.0f}%){where}. State "
                "clearly what your project does differently."
            )
        else:
            suggestions.append(
                f"The closest project is “{title}” ({top.score:.0f}%). The overlap is low, "
                "so your idea is reasonably distinct."
            )
        common = Counter(term for _, item in matches for term in item.shared_terms)
        repeated = [term for term, count in common.most_common(5) if count > 1]
        if repeated:
            suggestions.append(
                "Several similar projects use the terms " + ", ".join(repeated)
                + ". Add details specific to your own setting to stand apart."
            )
    missing = [
        label for name, (label, _) in SECTIONS.items()
        if name != "category" and not (proposal.get(name) or "").strip()
    ]
    if missing:
        suggestions.append(
            "Fill in " + ", ".join(label.lower() for label in missing)
            + " so the check can compare more of your proposal."
        )
    return suggestions
