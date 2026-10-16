"""Build a SAMPLE ONLY manual pack ZIP when sending fails."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any


def build_manual_pack(application_id: str, payload: dict[str, Any]) -> Path:
    out_dir = Path("data/manual_packs")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{application_id}.zip"

    checklist = [
        "RightPath manual pack (SAMPLE ONLY)",
        f"Application: {application_id}",
        f"Programme: {payload.get('program_id')}",
        f"Recipient: {payload.get('to')}",
        "",
        "Fields:",
    ]
    for key, value in (payload.get("fields") or {}).items():
        checklist.append(f"- {key}: {value}")
    checklist.extend(
        [
            "",
            "Documents to attach manually (SAMPLE ONLY — not real IDs):",
            *[f"- {name}" for name in (payload.get("attachments") or [])],
            "",
            "Your turn: complete CAPTCHA, identity checks, and any portal steps yourself.",
            "This pack is information only — not legal or medical advice.",
        ]
    )

    readme = (
        "SAMPLE ONLY files. Do not treat these as real government documents.\n"
        "Generated because automated send failed or was blocked.\n"
    )

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("CHECKLIST.txt", "\n".join(checklist))
        zf.writestr("README.txt", readme)
        zf.writestr("payload.json", json.dumps(payload, indent=2))
        for name in payload.get("attachments") or []:
            zf.writestr(
                f"samples/{name}.txt",
                f"SAMPLE ONLY placeholder for {name}. Not a real document.\n",
            )
    return path
