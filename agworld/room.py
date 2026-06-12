"""방/장소 레이아웃 — 씬 테마 + 오브젝트 배치 데이터와 검증.

- 방(room) 가구는 room_config.json의 각 방 "items"에 저장된다(웹 편집 대상).
  여기의 DEFAULT_ROOM_ITEMS는 새 방의 시드(기본 인테리어)다.
- Town은 하드코딩(편집 불가). 집(house) item은 place/label을 가져 탭 내비게이션에 쓰인다.

좌표계: size×size, 중심 (0,0). ry는 Y축 회전(도).
"""

from __future__ import annotations

# 클라이언트 빌더가 아는 모든 item. 알 수 없는 item은 거른다.
CATALOG = (
    "rug", "sofa", "table", "chair", "bookshelf", "plant", "lamp", "picture", "window",
    "townhall", "fountain", "tree", "lamppost", "bench", "house",
)

# 방 편집기에서 추가할 수 있는 실내 가구
INDOOR_CATALOG = (
    "rug", "sofa", "table", "chair", "bookshelf", "plant", "lamp", "picture", "window",
)

ROOM_SIZE = 8
TOWN_SIZE = 28
MAX_ITEMS = 40

# 새 방의 기본 인테리어(시드). 이후엔 config의 items가 진실.
DEFAULT_ROOM_ITEMS = {
    "jungs": [
        {"item": "rug", "x": 0.0, "z": 0.4, "scale": 2.6, "color": "#c98f5a"},
        {"item": "sofa", "x": 0.0, "z": -3.0, "ry": 0, "color": "#7a8a6f"},
        {"item": "bookshelf", "x": -3.3, "z": -2.4, "ry": 90, "color": "#8a6f4f"},
        {"item": "table", "x": 0.0, "z": 2.7, "color": "#9a7a55"},
        {"item": "plant", "x": 3.2, "z": -3.1},
        {"item": "plant", "x": -3.2, "z": 3.0, "scale": 0.85},
        {"item": "lamp", "x": 3.25, "z": 3.0},
        {"item": "picture", "x": 1.6, "z": -3.96, "ry": 0},
        {"item": "window", "x": -3.96, "z": 0.6, "ry": 0},
    ],
    "jayy": [
        {"item": "rug", "x": 0.0, "z": 0.2, "scale": 2.6, "color": "#7a93b5"},
        {"item": "sofa", "x": 0.0, "z": -3.0, "ry": 0, "color": "#8a6f8a"},
        {"item": "bookshelf", "x": 3.3, "z": -2.4, "ry": -90, "color": "#6f5a45"},
        {"item": "table", "x": -0.4, "z": 2.6, "color": "#7a6a50"},
        {"item": "chair", "x": 1.2, "z": 2.6, "ry": -90, "color": "#6f5a45"},
        {"item": "plant", "x": -3.2, "z": -3.1, "scale": 1.1},
        {"item": "lamp", "x": -3.25, "z": 3.0},
        {"item": "picture", "x": -1.6, "z": -3.96, "ry": 0, "color": "#c8a05a"},
        {"item": "window", "x": -3.96, "z": -0.6, "ry": 0},
    ],
}
DEFAULT_ROOM_FALLBACK = DEFAULT_ROOM_ITEMS["jungs"]

# Town (야외, 28×28) — 중앙 분수 광장, 뒤 타운홀, 앞쪽 양옆에 작은 집 2채
TOWN_ITEMS = [
    {"item": "townhall", "x": 0.0, "z": -11.2, "ry": 0, "scale": 1.4},
    {"item": "fountain", "x": 0.0, "z": 0.0},
    # 작은 집 2채 — 탭하면 그 방으로 이동 (door가 광장 쪽을 향하게 회전)
    {"item": "house", "x": -11.0, "z": 7.5, "ry": 124, "place": "jungs", "label": "Jungs' Room", "color": "#e9dcc4"},
    {"item": "house", "x": 11.0, "z": 7.5, "ry": -124, "place": "jayy", "label": "Jayy's Room", "color": "#d8c8b8"},
    {"item": "tree", "x": -11.6, "z": -8.8},
    {"item": "tree", "x": 11.6, "z": -7.6, "scale": 1.1},
    {"item": "tree", "x": -13.0, "z": 1.2},
    {"item": "tree", "x": 13.2, "z": 0.4, "scale": 1.15},
    {"item": "tree", "x": -5.4, "z": 12.4, "scale": 0.95},
    {"item": "tree", "x": 5.8, "z": 12.8, "scale": 1.05},
    {"item": "bench", "x": -5.6, "z": 9.0, "ry": 150},
    {"item": "bench", "x": 5.6, "z": 9.0, "ry": -150},
    {"item": "bench", "x": 0.0, "z": 11.2, "ry": 180},
    {"item": "lamppost", "x": -6.8, "z": -6.8},
    {"item": "lamppost", "x": 6.8, "z": -6.8},
    {"item": "lamppost", "x": -6.8, "z": 6.8},
    {"item": "lamppost", "x": 6.8, "z": 6.8},
    {"item": "plant", "x": 2.4, "z": 10.0},
    {"item": "plant", "x": -2.4, "z": 10.0},
]


def town_dict() -> dict:
    """GET /room?place=town 응답."""
    return {"place": "town", "room_size": TOWN_SIZE, "scene": "outdoor",
            "items": [dict(it) for it in TOWN_ITEMS]}


def room_dict_from_items(place: str, items: list[dict]) -> dict:
    """방(실내) 응답. 카탈로그에 있는 item만 통과."""
    valid = [dict(it) for it in items if it.get("item") in CATALOG]
    return {"place": place, "room_size": ROOM_SIZE, "scene": "indoor", "items": valid}


def sanitize_items(items: object) -> tuple[bool, str | None, list[dict]]:
    """편집기가 보낸 가구 목록을 검증·정제한다. (ok, error, cleaned) 반환.

    - INDOOR_CATALOG의 item만 허용
    - 좌표는 방 경계 안으로 클램프, 수치 필드는 숫자 강제
    - 허용 필드 외는 버림 (place/label 같은 내비게이션 필드 주입 방지)
    """
    if not isinstance(items, list):
        return False, "items must be a list", []
    if len(items) > MAX_ITEMS:
        return False, f"Too many items (max {MAX_ITEMS})", []

    half = ROOM_SIZE / 2
    cleaned = []
    for it in items:
        if not isinstance(it, dict):
            return False, "Each item must be an object", []
        kind = it.get("item")
        if kind not in INDOOR_CATALOG:
            return False, f"Unknown furniture '{kind}'", []
        out = {"item": kind}
        try:
            out["x"] = max(-half, min(half, float(it.get("x", 0))))
            out["z"] = max(-half, min(half, float(it.get("z", 0))))
            if "ry" in it:
                out["ry"] = float(it["ry"]) % 360
            if "scale" in it:
                out["scale"] = max(0.3, min(3.0, float(it["scale"])))
        except (TypeError, ValueError):
            return False, "x/z/ry/scale must be numbers", []
        color = it.get("color")
        if isinstance(color, str) and len(color) <= 16:
            out["color"] = color
        cleaned.append(out)
    return True, None, cleaned
