"""Turn official page text into a checkable rule pack.

The model only proposes. Every condition must carry a quote copied from the page,
and anything the rule engine cannot check is set aside for the reviewer to see.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlparse

from app.config import get_settings
from app.services.groq_pool import get_groq_pool

ATTRS: dict[str, dict[str, Any]] = {
    "age": {"ops": {"gte", "lte", "between"}, "kind": "number"},
    "education_level": {"ops": {"eq", "in"}, "kind": "education"},
    "low_income": {"ops": {"is_true"}, "kind": "bool"},
    "disability": {"ops": {"is_true"}, "kind": "bool"},
    "unemployed": {"ops": {"is_true"}, "kind": "bool"},
    "student": {"ops": {"is_true"}, "kind": "bool"},
    "country": {"ops": {"eq", "in"}, "kind": "country"},
}
EDUCATION_LEVELS = {"primary", "secondary", "tertiary"}
DOMAINS = {"education", "income", "health", "work", "housing"}

KEYWORDS = (
    "eligib", "who can", "you can get", "you can apply", "you may", "must", "aged",
    "years old", "age ", "income", "need-based", "financial need", "disab", "unemploy",
    "student", "enrol", "undergraduate", "university", "degree", "resident", "citizen",
    "national", "domicile", "household", "apply", "criteria", "requirement", "deadline",
)

TLD_COUNTRY = (
    (".gov.pk", "PK"), (".org.pk", "PK"), (".edu.pk", "PK"), (".pk", "PK"),
    (".gov.uk", "GB"), (".org.uk", "GB"), (".ac.uk", "GB"), (".uk", "GB"),
    (".gov.in", "IN"), (".nic.in", "IN"), (".gc.ca", "CA"), ("canada.ca", "CA"),
    (".gov.au", "AU"), (".gov.bd", "BD"), (".gov.ng", "NG"), (".go.ke", "KE"),
    (".gov.za", "ZA"), (".gov.ph", "PH"), (".gov", "US"),
)

COUNTRY_NAMES = {
    "PK": "Pakistan", "GB": "United Kingdom", "US": "United States", "IN": "India",
    "CA": "Canada", "AU": "Australia", "BD": "Bangladesh", "NG": "Nigeria", "KE": "Kenya",
    "ZA": "South Africa", "PH": "Philippines", "AE": "United Arab Emirates", "SA": "Saudi Arabia",
    "DE": "Germany", "FR": "France", "TR": "Turkey", "EG": "Egypt", "ID": "Indonesia",
    "MY": "Malaysia", "IE": "Ireland", "NZ": "New Zealand",
}


def country_from_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    for suffix, code in TLD_COUNTRY:
        if host.endswith(suffix):
            return code
    return ""


def focus_text(text: str, limit: int = 9000) -> str:
    """Keep the intro plus every sentence that talks about who qualifies."""
    text = text or ""
    if len(text) <= limit:
        return text
    sentences = re.split(r"(?<=[.!?])\s+", text)
    intro = text[:700]
    picked: list[str] = []
    size = len(intro)
    for sentence in sentences:
        lowered = sentence.lower()
        if not any(word in lowered for word in KEYWORDS):
            continue
        piece = sentence.strip()[:600]
        if size + len(piece) + 1 > limit:
            break
        picked.append(piece)
        size += len(piece) + 1
    return intro + "\n...\n" + "\n".join(picked)


def _clean_quote(quote: str) -> str:
    cleaned = (quote or "").replace("\u2019", "'").replace("\u2018", "'")
    cleaned = cleaned.replace("\u201c", '"').replace("\u201d", '"').replace("\u2013", "-")
    cleaned = re.sub(r"\s+", " ", cleaned).strip().strip('"').strip()
    return cleaned.rstrip(".,;:")


def anchor_quote(quote: str, page: str) -> str:
    """Return the exact page substring for a quote, or the quote unchanged if it is not there.

    Only spacing, curly quotes and trailing punctuation are forgiven. A reworded quote stays
    reworded, so the receipt check will refuse it.
    """
    if not quote:
        return ""
    if quote in page:
        return quote
    cleaned = _clean_quote(quote)
    if cleaned and cleaned in page:
        return cleaned
    if not cleaned:
        return quote
    pattern = r"\s+".join(re.escape(part) for part in cleaned.split(" "))
    pattern = pattern.replace("'", "['\u2019]")
    match = re.search(pattern, page, flags=re.IGNORECASE)
    if match:
        return match.group(0)
    return quote


def _as_number(value: Any) -> float | int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if float(value).is_integer() else value
    if isinstance(value, str) and re.fullmatch(r"\d+(\.\d+)?", value.strip()):
        number = float(value)
        return int(number) if number.is_integer() else number
    return None


def _valid_value(attr: str, op: str, value: Any) -> tuple[bool, Any]:
    kind = ATTRS[attr]["kind"]
    if op == "is_true":
        return True, None
    if kind == "number":
        if op == "between":
            if isinstance(value, (list, tuple)) and len(value) == 2:
                low, high = _as_number(value[0]), _as_number(value[1])
                if low is not None and high is not None and low <= high:
                    return True, [low, high]
            return False, value
        number = _as_number(value)
        return (number is not None), number
    if kind == "education":
        values = value if isinstance(value, list) else [value]
        values = [str(v).lower() for v in values if str(v).lower() in EDUCATION_LEVELS]
        if not values:
            return False, value
        return True, (values if op == "in" else values[0])
    if kind == "country":
        values = value if isinstance(value, list) else [value]
        values = [str(v).upper() for v in values if isinstance(v, str) and len(v.strip()) == 2]
        if not values:
            return False, value
        return True, (values if op == "in" else values[0])
    return False, value


def clean_title(title: str) -> str:
    """'Pension Credit: Eligibility - GOV.UK' becomes 'Pension Credit'."""
    text = re.split(r"\s+[-|–—]\s+", title.strip())[0]
    text = re.sub(r"\s*:\s*(eligibility|who can (get|apply)|overview|how to apply).*$", "", text, flags=re.I)
    text = re.sub(r"\s+(eligibility criteria|introduction|overview|home)$", "", text, flags=re.I)
    return text.strip() or title.strip()


def title_key(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", clean_title(title or "").lower())


def normalize_draft(raw: dict[str, Any], page: str, base: dict[str, Any]) -> dict[str, Any]:
    """Keep only conditions the rule engine can check. Anchor quotes to the page text."""
    draft = dict(base)
    for key in ("title", "provider", "summary"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            draft[key] = value.strip()[:240]
    draft["title"] = clean_title(str(draft.get("title") or ""))[:160]
    country = raw.get("country")
    if isinstance(country, str) and len(country.strip()) == 2:
        draft["country"] = country.strip().upper()
    domain = raw.get("domain")
    if isinstance(domain, str) and domain.lower() in DOMAINS:
        draft["domain"] = domain.lower()
    docs = raw.get("required_docs")
    if isinstance(docs, list):
        draft["required_docs"] = [str(d).strip()[:80] for d in docs if str(d).strip()][:6]
    deadline = raw.get("deadline")
    if isinstance(deadline, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", deadline.strip()):
        draft["deadline"] = deadline.strip()

    conditions: list[dict[str, Any]] = []
    unsupported: list[dict[str, str]] = []
    for item in raw.get("conditions") or []:
        if not isinstance(item, dict):
            continue
        attr = str(item.get("attr") or "")
        op = str(item.get("op") or "")
        quote = anchor_quote(str(item.get("source_quote") or ""), page)
        plain = str(item.get("plain") or "").strip()[:200]
        if attr not in ATTRS or op not in ATTRS[attr]["ops"]:
            unsupported.append({"plain": plain or f"{attr} {op}", "source_quote": quote})
            continue
        ok, value = _valid_value(attr, op, item.get("value"))
        if ok and attr == "age":
            ages = value if isinstance(value, list) else [value]
            ok = all(5 <= age <= 120 for age in ages)
        if not ok:
            unsupported.append({"plain": plain or f"{attr} {op}", "source_quote": quote})
            continue
        condition: dict[str, Any] = {
            "id": f"c{len(conditions) + 1}",
            "attr": attr,
            "op": op,
            "source_quote": quote,
            "plain": plain,
        }
        if op != "is_true":
            condition["value"] = value
        conditions.append(condition)
    draft["conditions"] = conditions[:8]
    draft["unsupported"] = unsupported[:6]
    return draft


SYSTEM_PROMPT = (
    "You are a careful eligibility analyst for public support programmes worldwide. "
    "You read the text of one official web page and write the eligibility rules as JSON. "
    "Return ONLY a JSON object with keys: title, provider, country, domain, summary, "
    "conditions, required_docs, deadline.\n"
    "- country: ISO 3166 alpha-2 code of the government or body that runs the programme.\n"
    "- domain: one of education, income, health, work, housing.\n"
    "- summary: one plain sentence a teenager understands. No numbers that are not on the page.\n"
    "- conditions: list of {attr, op, value, source_quote, plain}. Allowed attr and op:\n"
    "  age with gte, lte or between (value is a number or [low, high]);\n"
    "  education_level with in or eq (values primary, secondary, tertiary);\n"
    "  low_income, disability, unemployed, student with is_true (no value);\n"
    "  country with eq or in (ISO alpha-2 codes; use it when the page says applicants must live in or be citizens of a country).\n"
    "- Every condition must be something EVERY applicant has to meet. Leave out alternatives "
    "(\"if you are studying\", \"or if you have a disability\") and anything about how much money is paid.\n"
    "- source_quote: copy 3 to 25 words from the page EXACTLY, character for character, that state the condition. "
    "Never paraphrase. If you cannot quote it, leave the condition out.\n"
    "- plain: the condition in plain words.\n"
    "- required_docs: short names of documents the page asks for, or an empty list.\n"
    "- deadline: YYYY-MM-DD only if the page states a closing date, else an empty string.\n"
    "Never invent a rule, number, date or document."
)


def _model_json(user: str) -> dict[str, Any] | None:
    pool = get_groq_pool()
    if len(pool) == 0:
        return None
    content = pool.complete(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}],
        model=get_settings().llm_model,
        temperature=0,
        response_format={"type": "json_object"},
        timeout=60.0,
    )
    if not content:
        return None
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


AGE_BETWEEN = re.compile(
    r"aged?\s+(?:between\s+)?(\d{1,2})\s*(?:and|to|-)\s*(\d{1,2})(?:\s*years)?", re.IGNORECASE
)
AGE_MIN = re.compile(r"(?:aged\s+)?(\d{1,2})\s+(?:years old\s+)?or\s+(?:over|older|above)", re.IGNORECASE)
AGE_MAX = re.compile(r"(?:under|below|younger than)\s+(?:the age of\s+)?(\d{1,2})", re.IGNORECASE)
BOOL_PATTERNS = (
    ("low_income", re.compile(r"[^.]{0,40}\b(low[- ]income|financial need|need[- ]based|poor households?)\b[^.]{0,40}", re.IGNORECASE)),
    ("disability", re.compile(r"[^.]{0,40}\b(persons? with (?:a )?disabilit(?:y|ies)|disabled (?:people|persons|students))\b[^.]{0,30}", re.IGNORECASE)),
    ("unemployed", re.compile(r"[^.]{0,40}\b(unemployed|out of work|jobless)\b[^.]{0,30}", re.IGNORECASE)),
)


def draft_deterministic(page: str, base: dict[str, Any]) -> dict[str, Any]:
    """No model available: pick up only phrases that match exact patterns in the page."""
    raw: dict[str, Any] = {"conditions": []}
    match = AGE_BETWEEN.search(page)
    if match and int(match.group(1)) < int(match.group(2)):
        raw["conditions"].append(
            {"attr": "age", "op": "between", "value": [int(match.group(1)), int(match.group(2))],
             "source_quote": match.group(0).strip(), "plain": f"Age {match.group(1)} to {match.group(2)}"}
        )
    else:
        low = AGE_MIN.search(page)
        if low:
            raw["conditions"].append(
                {"attr": "age", "op": "gte", "value": int(low.group(1)),
                 "source_quote": low.group(0).strip(), "plain": f"Age {low.group(1)} or older"}
            )
        high = AGE_MAX.search(page)
        if high:
            raw["conditions"].append(
                {"attr": "age", "op": "lte", "value": int(high.group(1)) - 1,
                 "source_quote": high.group(0).strip(), "plain": f"Under {high.group(1)}"}
            )
    for attr, pattern in BOOL_PATTERNS:
        found = pattern.search(page)
        if found:
            raw["conditions"].append(
                {"attr": attr, "op": "is_true", "source_quote": found.group(0).strip(),
                 "plain": attr.replace("_", " ").capitalize()}
            )
    return normalize_draft(raw, page, base)


def draft_rules(
    page: str,
    *,
    url: str,
    page_title: str = "",
    live_rules: dict[str, Any] | None = None,
    prefer_llm: bool = True,
) -> tuple[dict[str, Any], str]:
    """Return (draft, method). method is "ai" or "pattern"."""
    live = live_rules or {}
    base: dict[str, Any] = {
        "id": live.get("id", ""),
        "version": int(live.get("version", 0)) + 1,
        "title": live.get("title") or page_title or (urlparse(url).hostname or "Programme"),
        "provider": live.get("provider") or (urlparse(url).hostname or ""),
        "summary": live.get("summary", ""),
        "country": live.get("country") or country_from_url(url),
        "domain": live.get("domain") or "income",
        "official_url": live.get("official_url") or url,
        "source_url": url,
        "required_docs": live.get("required_docs") or [],
        "deadline": live.get("deadline", ""),
        "conditions": [],
    }
    if prefer_llm:
        context = ""
        if live.get("conditions"):
            context = (
                "These rules are live today. Keep a rule only if the page still supports it, "
                "and update it if the page changed:\n" + json.dumps(live.get("conditions"), indent=1) + "\n\n"
            )
        user = (
            f"Page URL: {url}\nPage title: {page_title}\n\n{context}"
            f"Page text:\n{focus_text(page)}\n\nReturn the JSON object."
        )
        raw = _model_json(user)
        if raw is not None:
            return normalize_draft(raw, page, base), "ai"
    return draft_deterministic(page, base), "pattern"
