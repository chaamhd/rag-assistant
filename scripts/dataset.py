from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml

CATEGORIES = frozenset(
    {"howto", "detail", "reformulated", "french", "adjacent", "out_of_scope"}
)
REQUIRED_FIELDS = ("id", "category", "question", "should_refuse")
LIST_FIELDS = ("expected_sources", "expected_terms", "absent_terms")


class DatasetError(Exception):
    """Le fichier de questions est invalide."""


@dataclass(frozen=True)
class Question:
    id: str
    category: str
    question: str
    should_refuse: bool
    expected_sources: list[str] = field(default_factory=list)
    expected_terms: list[str] = field(default_factory=list)
    absent_terms: list[str] = field(default_factory=list)
    notes: str = ""


def _check_item(item: dict, label: str) -> list[str]:
    errors = []
    missing = [name for name in REQUIRED_FIELDS if name not in item]
    unknown = sorted(set(item) - {f.name for f in fields(Question)})
    if missing:
        errors.append(f"{label} : champs manquants {missing}")
    if unknown:
        errors.append(f"{label} : champs inconnus {unknown}")
    if missing or unknown:
        return errors

    if item["category"] not in CATEGORIES:
        errors.append(f"{label} : catégorie inconnue « {item['category']} »")
    if not isinstance(item["should_refuse"], bool):
        errors.append(f"{label} : should_refuse doit valoir true ou false")
    if not isinstance(item["question"], str) or not item["question"].strip():
        errors.append(f"{label} : la question est vide")
    for name in LIST_FIELDS:
        value = item.get(name, [])
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            errors.append(f"{label} : {name} doit être une liste de textes")
    if errors:
        return errors

    if item["should_refuse"]:
        if item.get("expected_sources") or item.get("expected_terms"):
            errors.append(
                f"{label} : une question à refuser n'a ni source ni terme attendus"
            )
        if not item.get("absent_terms"):
            errors.append(f"{label} : absent_terms est obligatoire pour un refus")
    else:
        if not item.get("expected_sources"):
            errors.append(f"{label} : expected_sources est obligatoire")
        if not item.get("expected_terms"):
            errors.append(f"{label} : expected_terms est obligatoire")
    return errors


def load_dataset(path: Path) -> list[Question]:
    """Charge et valide le fichier. Toutes les erreurs sont listées d'un coup."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise DatasetError("Le fichier doit contenir une liste de questions.")

    errors: list[str] = []
    questions: list[Question] = []
    seen: set[str] = set()
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            errors.append(f"entrée {index} : un dictionnaire est attendu")
            continue
        label = str(item.get("id", f"entrée {index}"))
        item_errors = _check_item(item, label)
        if label in seen:
            item_errors.append(f"{label} : identifiant en double")
        seen.add(label)
        if item_errors:
            errors.extend(item_errors)
        else:
            questions.append(Question(**item))

    if errors:
        raise DatasetError("\n".join(errors))
    return questions