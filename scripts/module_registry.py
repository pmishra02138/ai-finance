#!/usr/bin/env python3
"""
Structured module registry for AI Personal Finance Advisor.

Single source of truth loader reading `specs/{baseline,foundation,growth,horizons,synthesis}.json`
for stage layout, UI form schemas, descriptions, engine mode (deterministic vs. hybrid_monte_carlo),
and domain threshold constants.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Set

REPO_ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = REPO_ROOT / "specs"
STAGE_ORDER = ("baseline", "foundation", "growth", "horizons", "synthesis")


@lru_cache(maxsize=1)
def _load_stage_specs() -> List[Dict[str, Any]]:
    stages: List[Dict[str, Any]] = []
    for stage_id in STAGE_ORDER:
        spec_path = SPECS_DIR / f"{stage_id}.json"
        if not spec_path.is_file():
            raise FileNotFoundError(f"Missing required stage spec: {spec_path}")
        with spec_path.open("r", encoding="utf-8") as fh:
            stages.append(json.load(fh))
    return stages


@lru_cache(maxsize=1)
def _module_index() -> Dict[str, Dict[str, Any]]:
    idx: Dict[str, Dict[str, Any]] = {}
    for stage in _load_stage_specs():
        for mod in stage.get("modules", []):
            idx[mod["name"]] = {
                **mod,
                "stage_id": stage["id"],
                "stage_title": stage["title"],
            }
    return idx


def get_module_spec(module_name: str) -> Dict[str, Any]:
    """Return the full structured spec dict (including constants & fields) for a module."""
    return dict(_module_index().get(module_name, {}))


def get_module_constants(module_name: str) -> Dict[str, Any]:
    """Return the domain threshold constants defined in specs/ for a module."""
    return dict(_module_index().get(module_name, {}).get("constants") or {})


def get_modules_catalog() -> Dict[str, Any]:
    """Return the 5 stages and all 14 module specs from specs/*.json."""
    stages_out: List[Dict[str, Any]] = []
    flat_modules: List[Dict[str, Any]] = []

    for stage in _load_stage_specs():
        enriched: List[Dict[str, Any]] = []
        for mod in stage.get("modules", []):
            entry = {
                "name": mod["name"],
                "label": mod["label"],
                "stage_id": stage["id"],
                "stage_title": stage["title"],
                "engine": mod.get("engine", "deterministic"),
                "syncs_to_plan": mod.get("syncs_to_plan", True),
                "description": mod.get("description", ""),
                "form_note": mod.get("form_note", ""),
                "fields": mod.get("fields", []),
            }
            enriched.append(entry)
            flat_modules.append(entry)
        stages_out.append(
            {
                "id": stage["id"],
                "title": stage["title"],
                "subtitle": stage.get("subtitle", ""),
                "modules": enriched,
            }
        )

    return {"stages": stages_out, "modules": flat_modules, "total_modules": len(flat_modules)}


VALID_MODULE_NAMES: Set[str] = set(_module_index().keys())
