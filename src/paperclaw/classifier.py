from __future__ import annotations

import datetime
import json
import logging
import re

import anthropic

from paperclaw.schemas import ClassifiedDocument, DocumentType, RawDocument

logger = logging.getLogger(__name__)

_PATTERNS: list[tuple[str, DocumentType]] = [
    (r"stromrechnung|gasrechnung|bill", DocumentType.BILL),
    (r"rechnung|invoice", DocumentType.INVOICE),
    (r"kontoauszug|statement", DocumentType.BANK_STATEMENT),
    (r"vertrag|contract", DocumentType.CONTRACT),
    (r"steuer|tax|finanzamt", DocumentType.TAX),
    (r"versicherung|insurance", DocumentType.INSURANCE),
]

_CLASSIFY_USER = """\
Classify the following document. Return a JSON object with exactly these fields:
- doc_type: one of "invoice", "bill", "contract", "bank_statement",
  "tax", "insurance", "letter", "other"
- date: "YYYY-MM-DD" or null
- vendor: string or null
- amount: number or null
- currency: ISO 4217 3-letter code or null
- reference: string or null
- confidence: number between 0.0 and 1.0

Document text:
{text}

Return only valid JSON, no explanation."""


class LocalRulesClassifier:
    def classify(self, raw: RawDocument) -> ClassifiedDocument:
        if not raw.text.strip():
            return ClassifiedDocument(
                raw=raw, doc_type=DocumentType.OTHER, confidence=0.0
            )

        fname = raw.filename.lower()
        for pattern, doc_type in _PATTERNS:
            if re.search(pattern, fname, re.IGNORECASE):
                return ClassifiedDocument(raw=raw, doc_type=doc_type, confidence=0.85)

        body = raw.text.lower()
        for pattern, doc_type in _PATTERNS:
            if re.search(pattern, body, re.IGNORECASE):
                return ClassifiedDocument(raw=raw, doc_type=doc_type, confidence=0.60)

        return ClassifiedDocument(raw=raw, doc_type=DocumentType.OTHER, confidence=0.30)


def _extract_json(text: str) -> dict[str, object]:
    """Parse JSON from response, stripping markdown code fences if present."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        text = match.group(1)
    return json.loads(text)  # type: ignore[no-any-return]


class ClaudeClassifier:
    def __init__(self, api_key: str, model: str = "claude-haiku-4-5-20251001") -> None:
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def classify(self, raw: RawDocument) -> ClassifiedDocument:
        prompt = _CLASSIFY_USER.format(text=raw.text[:8000])
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        data = _extract_json(msg.content[0].text)  # type: ignore[union-attr]

        date: datetime.date | None = None
        raw_date = data.get("date")
        if raw_date:
            try:
                date = datetime.date.fromisoformat(str(raw_date))
            except ValueError:
                logger.warning(
                    "Claude returned unparseable date %r for %s",
                    raw_date,
                    raw.filename,
                )

        amount = data.get("amount")

        return ClassifiedDocument(
            raw=raw,
            doc_type=DocumentType(data.get("doc_type", "other")),
            date=date,
            vendor=str(data["vendor"]) if data.get("vendor") else None,
            amount=float(amount) if amount is not None else None,  # type: ignore[arg-type]
            currency=str(data["currency"]) if data.get("currency") else None,
            reference=str(data["reference"]) if data.get("reference") else None,
            confidence=float(data.get("confidence", 0.5)),  # type: ignore[arg-type]
        )
