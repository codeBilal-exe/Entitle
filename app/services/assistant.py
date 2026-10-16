"""Citizen assistant. Groq reads a sentence. The rule engine decides matches."""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.engine.approval_gate import ApplicationState
from app.engine.rule_engine import RuleEngine
from app.models import Application, Profile, Program, Source, User
from app.services.explainer import short_reason
from app.services.groq_pool import get_groq_pool
from app.services.plain import attr_label, doc_label, value_label
from app.services.pulse import load_rules, profile_attrs
from app.services.questions import QuestionEngine

_engine = RuleEngine()
_questions = QuestionEngine(_engine)

EDUCATION = {
    "primary": ("primary school", "primary"),
    "secondary": (
        "secondary",
        "matric",
        "intermediate",
        "fsc",
        "fa ",
        "a-level",
        "a level",
        "high school",
    ),
    "tertiary": (
        "tertiary",
        "university",
        "bachelor",
        "degree",
        "undergraduate",
        "nust",
        "fast",
        "bsc",
        "bs ",
    ),
}

BOOL_CUES = {
    "low_income": (
        "low-income",
        "low income",
        "income is low",
        "poor household",
        "cannot afford",
        "struggle to pay",
    ),
    "disability": ("disability", "disabled", "person with a disability"),
    "unemployed": ("unemployed", "without a job", "no job", "jobless"),
    "needs_language_support": ("language support", "cannot read the form", "need help with language"),
}

PROVINCES = {
    "punjab": "Punjab",
    "sindh": "Sindh",
    "khyber pakhtunkhwa": "Khyber Pakhtunkhwa",
    "khyber": "Khyber Pakhtunkhwa",
    "kpk": "Khyber Pakhtunkhwa",
    "balochistan": "Balochistan",
    "islamabad": "Islamabad",
    "gilgit": "Gilgit-Baltistan",
    "kashmir": "Azad Kashmir",
}

APPLY_RE = re.compile(r"\b(apply|prepare|packet|application)\b", re.IGNORECASE)
AGE_RES = (
    re.compile(r"\b(\d{1,3})\s*years?\s*old\b", re.IGNORECASE),
    re.compile(r"\baged?\s*(\d{1,3})\b", re.IGNORECASE),
    re.compile(r"\bi(?:'m| am)\s*(\d{1,3})\b", re.IGNORECASE),
    re.compile(r"\bage(?:d)?\s*(?:is|:)?\s*(\d{1,3})\b", re.IGNORECASE),
)
HINT_STOP = frozenset(
    {
        "prepare",
        "packet",
        "apply",
        "application",
        "programme",
        "program",
        "scholarship",
        "scholarships",
        "this",
        "that",
        "with",
        "from",
        "have",
        "your",
    }
)


def _groq_json(system: str, user: str) -> dict[str, Any] | None:
    pool = get_groq_pool()
    if len(pool) == 0:
        return None
    content = pool.complete(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        model=get_settings().llm_model,
        temperature=0,
        response_format={"type": "json_object"},
        timeout=30.0,
    )
    if not content:
        return None
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _age_in_text(text: str) -> int | None:
    for pattern in AGE_RES:
        match = pattern.search(text)
        if not match:
            continue
        age = int(match.group(1))
        if 0 <= age <= 120:
            return age
    return None


def _education_in_text(text: str) -> str | None:
    lowered = text.lower()
    for level in ("tertiary", "secondary", "primary"):
        if any(cue in lowered for cue in EDUCATION[level]):
            return level
    return None


def _bool_in_text(text: str, attr: str) -> bool | None:
    lowered = text.lower()
    cues = BOOL_CUES[attr]
    if not any(cue in lowered for cue in cues):
        return None
    if re.search(r"\b(not|no|n't|never)\b.{0,24}(" + "|".join(re.escape(c) for c in cues) + ")", lowered):
        return False
    if any(cue in lowered for cue in cues):
        return True
    return None


def _province_in_text(text: str) -> str | None:
    lowered = text.lower()
    for cue, label in PROVINCES.items():
        if cue in lowered:
            return label
    return None


def extract_deterministic(sentence: str) -> dict[str, Any]:
    found: dict[str, Any] = {}
    age = _age_in_text(sentence)
    if age is not None:
        found["age"] = age
    education = _education_in_text(sentence)
    if education:
        found["education_level"] = education
    for attr in BOOL_CUES:
        value = _bool_in_text(sentence, attr)
        if value is not None:
            found[attr] = value
    province = _province_in_text(sentence)
    if province:
        found["province"] = province
    return found


def _corroborated(sentence: str, raw: dict[str, Any]) -> dict[str, Any]:
    """Keep a model field only when the sentence itself supports it."""
    found: dict[str, Any] = {}
    age = raw.get("age")
    if isinstance(age, str) and age.isdigit():
        age = int(age)
    if isinstance(age, float) and age.is_integer():
        age = int(age)
    if isinstance(age, int) and 0 <= age <= 120 and re.search(rf"\b{age}\b", sentence):
        found["age"] = age

    education = raw.get("education_level")
    if education in EDUCATION and _education_in_text(sentence) == education:
        found["education_level"] = education

    for attr in BOOL_CUES:
        value = raw.get(attr)
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            value = value.lower() == "true"
        if isinstance(value, bool) and _bool_in_text(sentence, attr) is value:
            found[attr] = value

    province = raw.get("province")
    if isinstance(province, str):
        label = PROVINCES.get(province.strip().lower())
        if label and label == _province_in_text(sentence):
            found["province"] = label
    return found


def wants_packet(sentence: str, model: dict[str, Any] | None = None) -> bool:
    if APPLY_RE.search(sentence):
        return True
    if not model:
        return False
    value = model.get("wants_packet")
    if isinstance(value, str):
        value = value.lower() == "true"
    return bool(value) and APPLY_RE.search(sentence) is not None


ALIASES = (
    ("need-based", "need-based"),
    ("need based", "need-based"),
    ("peef", "peef"),
    ("youth programme", "youth"),
    ("youth program", "youth"),
    ("kafaalat", "kafaalat"),
    ("bait-ul-mal", "bait"),
    ("sehat", "sehat"),
    ("navttc", "navttc"),
)


def hint_from_sentence(sentence: str, titles: list[str]) -> str:
    """A programme name the person actually wrote, not one the model picked."""
    lowered = sentence.lower()
    contained = [title for title in titles if title.lower() in lowered]
    if contained:
        return max(contained, key=len)
    cues = [hint for cue, hint in ALIASES if cue in lowered]
    if len(cues) == 1:
        return cues[0]
    return ""


def program_hint(sentence: str, model_hint: str = "") -> str:
    hint = (model_hint or "").strip()
    if hint:
        tokens = [
            token
            for token in re.findall(r"[a-z0-9]+", hint.lower())
            if len(token) > 3 and token not in HINT_STOP
        ]
        if tokens and any(token in sentence.lower() for token in tokens):
            return hint
    return ""


def summary_is_grounded(
    summary: str,
    cards: list[dict[str, Any]],
    sentence: str,
    catalogue_titles: list[str],
) -> bool:
    text = (summary or "").strip()
    if not text or len(text) > 700:
        return False
    shown = {card["title"].lower() for card in cards}
    lowered = text.lower()
    for title in catalogue_titles:
        name = title.lower()
        if name in shown or name not in lowered:
            continue
        return False
    allowed = set(re.findall(r"\d+", sentence))
    for card in cards:
        for key in ("quote", "deadline", "document", "next_step", "title"):
            allowed.update(re.findall(r"\d+", str(card.get(key) or "")))
    return all(number in allowed for number in re.findall(r"\d+", text))


def _quote_for(rules: dict[str, Any], evaluation) -> str:
    quotes: list[str] = []
    for item in evaluation.condition_results:
        quote = str(item.get("source_quote") or "")
        if item.get("outcome") is True and quote and quote not in quotes:
            quotes.append(quote)
    if not quotes:
        for condition in rules.get("conditions") or []:
            quote = str(condition.get("source_quote") or "")
            if quote and quote not in quotes:
                quotes.append(quote)
    return "; ".join(quotes)


def _checked(rules: dict[str, Any], source: Source | None, evaluation) -> str:
    if source is not None and source.status == "unreachable":
        return "unreachable"
    if not (rules.get("conditions") or []):
        return "unchecked"
    return evaluation.status.value


def match_cards(db: Session, attrs: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    programs = (
        db.query(Program)
        .filter(Program.status == "active")
        .order_by(Program.title)
        .all()
    )
    rulesets = []
    ranked: list[dict[str, Any]] = []
    for program in programs:
        rules = load_rules(db, program)
        if rules.get("conditions"):
            rulesets.append(rules)
        source = (
            db.query(Source).filter(Source.program_id == program.id).order_by(Source.id).first()
        )
        evaluation = _engine.evaluate(rules, attrs)
        status = _checked(rules, source, evaluation)
        if status not in {"eligible", "likely"}:
            continue
        docs = [doc_label(doc) for doc in (rules.get("required_docs") or [])]
        question = None
        if status == "likely":
            nxt = _questions.next_question([rules], attrs)
            question = nxt["label"] if nxt else "One more answer would settle this."
        ranked.append(
            {
                "program_id": program.id,
                "title": program.title,
                "status": status,
                "status_label": "Matches you" if status == "eligible" else "Needs an answer",
                "quote": _quote_for(rules, evaluation),
                "document": docs[0] if docs else "",
                "documents": docs,
                "deadline": rules.get("deadline") or "",
                "official_url": rules.get("official_url") or "",
                "next_step": (
                    "Prepare the packet. It is not sent until you approve it."
                    if status == "eligible"
                    else question or "Answer the open question."
                ),
                "why": short_reason(evaluation),
                "can_prepare": status == "eligible",
            }
        )
    rank = {"eligible": 0, "likely": 1}
    ranked.sort(key=lambda card: (rank.get(card["status"], 9), card["title"]))
    question = None
    nxt = _questions.next_question(rulesets, attrs) if rulesets else None
    if nxt:
        question = nxt["label"]
    return ranked[:3], question


def plain_summary(cards: list[dict[str, Any]]) -> str:
    if not cards:
        return (
            "No approved rule matches this profile yet. "
            "Add your age and education, or wait until a person approves a notice."
        )
    lines = []
    for card in cards:
        if card["status"] == "eligible":
            quote = f" The notice says “{card['quote']}”." if card["quote"] else ""
            lines.append(f"{card['title']} matches you.{quote}")
        else:
            lines.append(f"{card['title']} still needs an answer. {card['next_step']}")
    return " ".join(lines)


def write_summary(
    sentence: str,
    cards: list[dict[str, Any]],
    catalogue_titles: list[str],
) -> tuple[str, bool]:
    facts = [
        {
            "title": card["title"],
            "status": card["status_label"],
            "quote": card["quote"],
            "document": card["document"],
            "deadline": card["deadline"],
            "next_step": card["next_step"],
        }
        for card in cards
    ]
    model = _groq_json(
        "Write a short reply for a citizen. Use only the JSON facts. "
        "Do not add a programme, quote, date, amount, or document that is not in the facts. "
        'Return JSON {"summary": "..."} with at most 4 sentences. '
        "Say that a packet is not sent until the citizen approves it.",
        json.dumps({"sentence": sentence, "matches": facts}),
    )
    summary = ""
    if model and isinstance(model.get("summary"), str):
        summary = model["summary"].strip()
    if summary and summary_is_grounded(summary, cards, sentence, catalogue_titles):
        return summary, True
    return plain_summary(cards), False


def pick_card(hint: str, cards: list[dict[str, Any]]) -> dict[str, Any] | None:
    eligible = [card for card in cards if card["status"] == "eligible"]
    if hint:
        folded = hint.lower()
        tokens = [
            token
            for token in re.findall(r"[a-z0-9]+", folded)
            if len(token) > 3 and token not in HINT_STOP
        ]
        for card in eligible:
            title = card["title"].lower()
            if folded in title or title in folded:
                return card
            if tokens and all(token in title for token in tokens):
                return card
        return None
    if len(eligible) == 1:
        return eligible[0]
    return None


def saved_labels(fields: dict[str, Any]) -> list[str]:
    labels = []
    for key, value in fields.items():
        if key == "province":
            labels.append(f"Province {value}")
            continue
        labels.append(f"{attr_label(key)} {value_label(key, value)}")
    return labels


def merge_attrs(existing: dict[str, Any], found: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    merged.update(found)
    return merged


def save_profile(db: Session, user: User, attrs: dict[str, Any]) -> Profile:
    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    if profile is None:
        profile = Profile(
            user_id=user.id,
            attributes_json="{}",
            consent_notifications=False,
            consent_email="",
        )
        db.add(profile)
    profile.attributes_json = json.dumps(attrs)
    db.commit()
    db.refresh(profile)
    return profile


def create_packet(
    db: Session,
    user: User,
    program: Program,
    rules: dict[str, Any],
    attrs: dict[str, Any],
) -> Application:
    payload = {
        "program_id": program.id,
        "to": rules.get("official_url") or rules.get("apply_email") or "",
        "fields": {
            "full_name": user.display_name,
            "contact_email": user.email,
            "age": attrs.get("age"),
            "education_level": attrs.get("education_level") or "",
        },
        "attachments": rules.get("required_docs") or [],
    }
    idem = f"{user.id}:{program.id}"
    existing = db.query(Application).filter(Application.idempotency_key == idem).first()
    if existing:
        return existing
    application = Application(
        id=f"app-{user.id}-{program.id}",
        user_id=user.id,
        program_id=program.id,
        state=ApplicationState.READY.value,
        payload_json=json.dumps(payload),
        idempotency_key=idem,
    )
    db.add(application)
    db.commit()
    return application


def reply_for(db: Session, user: User, sentence: str) -> dict[str, Any]:
    """Read a sentence, store corroborated fields, and describe rule-engine matches."""
    text = (sentence or "").strip()
    if len(text) < 8:
        return {"error": "Write one sentence about your age, study, or income."}

    model = _groq_json(
        "You read one sentence and return JSON only. "
        "Keys: age (integer or null), education_level (primary, secondary, tertiary, or null), "
        "low_income (boolean or null), disability (boolean or null), unemployed (boolean or null), "
        "needs_language_support (boolean or null), "
        "province (Punjab, Sindh, Khyber Pakhtunkhwa, Balochistan, Islamabad, Gilgit-Baltistan, Azad Kashmir, or null), "
        "wants_packet (boolean), program_hint (short string or empty). "
        "Use null when the sentence does not say it. Do not guess. "
        "University, a bachelor's degree, or BS is tertiary. "
        "Matric, intermediate, FSc, or high school is secondary. "
        "wants_packet is true only when they ask to prepare or apply.",
        text,
    )
    found = extract_deterministic(text)
    used_model = model is not None
    if model:
        for key, value in _corroborated(text, model).items():
            found.setdefault(key, value)

    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    attrs = merge_attrs(profile_attrs(profile), found)
    if found:
        save_profile(db, user, attrs)

    if attrs.get("age") is None and not attrs.get("education_level"):
        return {
            "error": "Add your age or education in the sentence. Nothing was stored.",
            "saved": [],
        }

    cards, question = match_cards(db, attrs)
    titles = [row.title for row in db.query(Program).filter(Program.status == "active").all()]
    summary, summary_from_model = write_summary(text, cards, titles)
    hint = ""
    if model and isinstance(model.get("program_hint"), str):
        hint = program_hint(text, model["program_hint"])
    if not hint:
        hint = hint_from_sentence(text, titles)
    chosen = pick_card(hint, cards) if wants_packet(text, model) else None
    return {
        "error": None,
        "summary": summary,
        "cards": cards,
        "saved": saved_labels(found),
        "question": question,
        "used_model": used_model or summary_from_model,
        "program_id": chosen["program_id"] if chosen else "",
        "attrs": attrs,
    }
