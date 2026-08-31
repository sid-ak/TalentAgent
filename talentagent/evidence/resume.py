"""Turning a resume into evidence nodes without inventing any (Spec §3.4).

A resume is already the user's own assertion, so ingesting one is promotion rather than
generation: the text is theirs, and the only question is where one accomplishment ends and the
next begins. That is a segmentation problem with a stable output shape, which is what tier 1 is
for (Spec §9.2).

The model is held to copying. It may split a line, drop a section header, and join a bullet to its
wrapped continuation; it may not rewrite, summarise, or improve. Anything it returns that is not
present in the source is discarded before it reaches the graph, so the check is not a matter of the
prompt being obeyed.
"""

from __future__ import annotations

import re

from talentagent.models.client import ModelClient

EXTRACT_PROMPT = (
    "Split this resume into the discrete accomplishments it claims. "
    'Return JSON: {"accomplishments": [str]}. '
    "Copy each one from the resume word for word, joining a bullet to its wrapped continuation "
    "where a line break splits it. Do not rewrite, summarise, embellish, or merge two separate "
    "accomplishments into one. Skip section headers, contact details, dates on their own, school "
    "names, and anything that is not a thing the person did. If the resume claims nothing "
    "concrete, return an empty list."
)
"""Tier-1 instruction. Segmentation only: every returned string must already be in the source."""

MIN_LENGTH = 25
"""Shortest string kept. Below this it is a job title or a date, not an accomplishment."""

MAX_ACCOMPLISHMENTS = 30
"""Ceiling on what one resume contributes, so a long CV cannot flood the graph."""


def _normalise(text: str) -> str:
    """Collapse whitespace so a wrapped line and its source compare equal."""
    return re.sub(r"\s+", " ", text).strip().lower()


def _is_grounded(candidate: str, source: str) -> bool:
    """Report whether `candidate` actually appears in `source`, ignoring line wrapping.

    This is what makes the extraction safe rather than merely instructed. A model that
    paraphrases, however plausibly, produces a string that is not in the resume, and it is
    dropped here rather than being written to the graph as the user's own words (Spec §3.4).
    """
    return _normalise(candidate) in _normalise(source)


def extract_accomplishments(
    resume_text: str, model_client: ModelClient | None
) -> tuple[list[str], bool]:
    """Split `resume_text` into accomplishment strings that appear verbatim in it.

    Returns the accomplishments and whether the model produced them. Falls back to line splitting
    when no model is configured, which is a degradation the caller reports rather than hides.
    """
    if model_client is not None:
        try:
            resp = model_client.tier_one(
                prompt=EXTRACT_PROMPT,
                data={"resume_text": resume_text},
                schema_name="extract_accomplishments_v1",
            )
            kept = [
                line.strip()
                for line in resp.get("accomplishments", [])
                if isinstance(line, str)
                and len(line.strip()) >= MIN_LENGTH
                and _is_grounded(line, resume_text)
            ]
            if kept:
                return kept[:MAX_ACCOMPLISHMENTS], True
        except Exception:  # noqa: BLE001 - degradation is reported, not silent
            pass

    lines = [line.strip("-•*\t ") for line in resume_text.splitlines()]
    kept = [
        line for line in lines if len(line) >= MIN_LENGTH and not line.lower().startswith("http")
    ]
    return kept[:MAX_ACCOMPLISHMENTS], False
