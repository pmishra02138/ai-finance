"""Financial plans and module runs persistence."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .schema import _connect, _utc_now

def list_plans(user_id: int, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, title, health_score, grade, created_at, updated_at
            FROM financial_plans
            WHERE user_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_plan(user_id: int, plan_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, user_id, title, health_score, grade, payload_json, created_at, updated_at
            FROM financial_plans
            WHERE id = ? AND user_id = ?
            """,
            (plan_id, user_id),
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["payload"] = json.loads(d.pop("payload_json"))
        return d


def create_plan(
    user_id: int,
    title: str,
    health_score: float,
    grade: str,
    payload: Dict[str, Any],
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    now = _utc_now()
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO financial_plans
                (user_id, title, health_score, grade, payload_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, title, float(health_score), grade, json.dumps(payload), now, now),
        )
        plan_id = cur.lastrowid
        conn.commit()
    return {
        "id": plan_id,
        "title": title,
        "health_score": float(health_score),
        "grade": grade,
        "payload": payload,
        "created_at": now,
        "updated_at": now,
    }


def update_plan(
    user_id: int,
    plan_id: int,
    title: str,
    health_score: float,
    grade: str,
    payload: Dict[str, Any],
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    now = _utc_now()
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            UPDATE financial_plans
            SET title = ?, health_score = ?, grade = ?, payload_json = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (title, float(health_score), grade, json.dumps(payload), now, plan_id, user_id),
        )
        conn.commit()
        if cur.rowcount == 0:
            return None
    return get_plan(user_id, plan_id, db_path=db_path)


def delete_plan(user_id: int, plan_id: int, db_path: Optional[str] = None) -> bool:
    with _connect(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM financial_plans WHERE id = ? AND user_id = ?",
            (plan_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0


def reset_plan(
    user_id: int,
    plan_id: int,
    health_score: float,
    grade: str,
    payload: Dict[str, Any],
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    now = _utc_now()
    with _connect(db_path) as conn:
        cur = conn.execute(
            """
            UPDATE financial_plans
            SET health_score = ?, grade = ?, payload_json = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (float(health_score), grade, json.dumps(payload), now, plan_id, user_id),
        )
        if cur.rowcount == 0:
            return None
        conn.execute(
            "DELETE FROM module_runs WHERE plan_id = ? AND user_id = ?",
            (plan_id, user_id),
        )
        conn.commit()
    return get_plan(user_id, plan_id, db_path=db_path)



def upsert_module_run(
    user_id: int,
    plan_id: int,
    module_name: str,
    inputs: Dict[str, Any],
    outputs: Dict[str, Any],
    score: Optional[float] = None,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    now = _utc_now()
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO module_runs (plan_id, user_id, module_name, inputs_json, outputs_json, score, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(plan_id, module_name) DO UPDATE SET
                inputs_json = excluded.inputs_json,
                outputs_json = excluded.outputs_json,
                score = excluded.score,
                updated_at = excluded.updated_at
            """,
            (plan_id, user_id, module_name, json.dumps(inputs), json.dumps(outputs), score, now),
        )
        conn.commit()
    return {
        "plan_id": plan_id,
        "module_name": module_name,
        "inputs": inputs,
        "outputs": outputs,
        "score": score,
        "updated_at": now,
    }


def list_module_runs(user_id: int, plan_id: int, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, plan_id, module_name, inputs_json, outputs_json, score, updated_at
            FROM module_runs
            WHERE user_id = ? AND plan_id = ?
            ORDER BY updated_at DESC
            """,
            (user_id, plan_id),
        ).fetchall()
        result: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            d["inputs"] = json.loads(d.pop("inputs_json"))
            d["outputs"] = json.loads(d.pop("outputs_json"))
            result.append(d)
        return result


def get_module_run(
    user_id: int,
    plan_id: int,
    module_name: str,
    db_path: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, plan_id, module_name, inputs_json, outputs_json, score, updated_at
            FROM module_runs
            WHERE user_id = ? AND plan_id = ? AND module_name = ?
            """,
            (user_id, plan_id, module_name),
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["inputs"] = json.loads(d.pop("inputs_json"))
        d["outputs"] = json.loads(d.pop("outputs_json"))
        return d
