"""영속성 — 슬립 시 에이전트 상태를 JSON 스냅샷으로 저장, 깨어날 때 복원.

틱 리플레이 없음(슬립 온 디스커넥트라 자는 동안 아무 일도 안 일어남). 스냅샷은 관계/기억만
보존해서, 깨어날 때 어제 싸운 걸 기억하게 한다. 스냅샷이 없으면(최초 실행) None을 반환하고
호출자가 기본 페르소나로 시작한다.
"""

from __future__ import annotations

import json
import os
import tempfile

from .models import Agent


def save_snapshot(agents: list[Agent], path: str, t: int = 0) -> None:
    """원자적 저장(임시파일 → rename)으로 중간 손상 방지."""
    data = {"version": 1, "t": t, "agents": [a.to_dict() for a in agents]}
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def load_snapshot(path: str) -> tuple[list[Agent], int] | None:
    """(agents, t) 반환. 파일 없음/손상이면 None → 호출자가 기본값으로 시작."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        agents = [Agent.from_dict(d) for d in data.get("agents", [])]
        return agents, int(data.get("t", 0))
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        # 손상된 스냅샷 → 깨끗이 포기하고 기본 페르소나로.
        return None
