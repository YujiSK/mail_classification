"""Paragraph-level subtopic sentence insertion into ``body_text``, mirrored into ``raw_text``.

Never touches header, signature, quoted-reply, or subject: those live outside
``body_text`` in every Full record (``raw_text`` = header block + ``\\n\\n`` +
``body_text`` + ``\\n\\n`` + signature/quote block, per
docs/schemas/raw_data_schema.md and the Phase 2 generator). Inserting only
inside the ``body_text`` substring and splicing the result back into
``raw_text`` at the same offset keeps that invariant.
"""

from __future__ import annotations

from mail_classification.schemas import RawMailRecord

INSERTION_POSITIONS = ("early", "mid", "end")


def _insert_paragraph(body_text: str, sentence: str, position: str) -> str:
    if position not in INSERTION_POSITIONS:
        raise ValueError(
            f"unknown insertion position {position!r}; expected one of {INSERTION_POSITIONS}"
        )
    paragraphs = body_text.split("\n\n")
    if position == "early":
        index = 1
    elif position == "mid":
        index = max(1, len(paragraphs) // 2)
    else:  # end
        index = len(paragraphs)
    new_paragraphs = [*paragraphs[:index], sentence, *paragraphs[index:]]
    return "\n\n".join(new_paragraphs)


def apply_contamination(
    record: RawMailRecord, sentence_text: str, position: str
) -> tuple[str, str]:
    """Return (new_raw_text, new_body_text) with the subtopic sentence spliced in.

    Raises if ``body_text`` is not found verbatim inside ``raw_text`` -- that
    invariant is required to safely avoid touching header/signature content.
    """
    body_text = record.body_text
    offset = record.raw_text.find(body_text)
    if offset == -1:
        raise ValueError(
            f"body_text is not a substring of raw_text for record {record.id!r}; "
            "cannot safely insert without risking header/signature content"
        )
    new_body_text = _insert_paragraph(body_text, sentence_text, position)
    new_raw_text = (
        record.raw_text[:offset] + new_body_text + record.raw_text[offset + len(body_text) :]
    )
    return new_raw_text, new_body_text
