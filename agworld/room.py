"""방 레이아웃 — 마이룸 가구/오브젝트 배치 데이터.

서버가 방 구성을 데이터로 소유하고 GET /room으로 내려준다. 클라이언트는 가구 카탈로그
(Three.js 빌더)로 조립. 이 데이터 주도 구조 위에 나중에 커스텀 스토어/마이룸 편집이 얹힌다.

좌표계: 방은 ROOM(8)×8, 중심 (0,0). x,z ∈ [-3.6, 3.6]. 에이전트는 반경 ~2.4 원에 서므로
가구는 벽/구석 위주로 둬서 중앙 무대를 비운다. ry는 Y축 회전(라디안 근사값, 도 단위로 적되 직렬화).
"""

from __future__ import annotations

# 카탈로그에 존재하는 아이템(클라이언트 빌더와 1:1). 알 수 없는 item은 클라이언트가 무시.
CATALOG = ("rug", "sofa", "table", "chair", "bookshelf", "plant", "lamp", "picture", "window")

# 기본 마이룸 레이아웃. {item, x, z, ry(도), scale?, color?(hex)}
DEFAULT_ROOM = [
    {"item": "rug", "x": 0.0, "z": 0.4, "scale": 2.6, "color": "#c98f5a"},
    {"item": "sofa", "x": 0.0, "z": -3.0, "ry": 0, "color": "#7a8a6f"},
    {"item": "bookshelf", "x": -3.3, "z": -2.4, "ry": 90, "color": "#8a6f4f"},
    {"item": "table", "x": 0.0, "z": 2.7, "color": "#9a7a55"},
    {"item": "plant", "x": 3.2, "z": -3.1},
    {"item": "plant", "x": -3.2, "z": 3.0, "scale": 0.85},
    {"item": "lamp", "x": 3.25, "z": 3.0},
    {"item": "picture", "x": 1.6, "z": -3.96, "ry": 0},
    {"item": "window", "x": -3.96, "z": 0.6, "ry": 0},
]


def room_dict(layout: list[dict] | None = None) -> dict:
    """GET /room 응답. 카탈로그에 있는 아이템만 통과시켜 직렬화."""
    items = layout if layout is not None else DEFAULT_ROOM
    valid = [dict(it) for it in items if it.get("item") in CATALOG]
    return {"room_size": 8, "items": valid}
