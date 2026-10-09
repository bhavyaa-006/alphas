"""Deterministic alpha metadata used by the model-free submission path."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


FALLBACK_CATEGORY = "PRICE_MOMENTUM"


@dataclass
class Metadata:
    name: str
    category: str
    description: str
    tags: list
    source: str


def fields_in_expression(expr: str, field_glossary: dict) -> list:
    return [field for field in field_glossary if re.search(rf"\b{re.escape(field)}\b", expr)]


def template_metadata(expr: str, field_glossary: dict, pack_name: str) -> Metadata:
    """Build factual offline metadata from the pack glossary and expression."""
    fields = fields_in_expression(expr, field_glossary)
    field_text = "; ".join(f"{field} ({field_glossary[field]})" for field in fields) or "the pack's data fields"
    short = hashlib.md5(expr.encode()).hexdigest()[:6]
    description = (
        f"Idea: Cross-sectional signal built from the {pack_name} dataset, aiming to rank stocks by "
        "the information those fields carry, using time-series and/or cross-sectional transformations "
        "to keep the signal stable.\n"
        f"Rationale for data used: {field_text}.\n"
        f"Rationale for operators used: The expression `{expr}` standardises or ranks the raw fields so "
        "they are comparable, and applies the listed operators to capture changes, spreads, or agreement "
        "between them while limiting outliers."
    )
    return Metadata(
        name=f"{pack_name}_{short}"[:40], category=FALLBACK_CATEGORY,
        description=description, tags=[pack_name, "auto"], source="template",
    )
