"""방 레이아웃 — 장소(place)별 가구/오브젝트 배치 데이터.

서버가 방 구성을 데이터로 소유하고 GET /room?place=<id>로 내려준다. 클라이언트는 가구
카탈로그(Three.js 빌더)로 조립. 이 데이터 주도 구조 위에 커스텀 스토어/마이룸 편집이 얹힌다.

장소:
- "room" (우리 방): 작은 방(8×8), 에이전트 소수.
- "town" (우리 동네): 큰 공간(12×12), 고정 이웃 10인. 가구도 더 많고 넓게 배치.

좌표계: 방 size×size, 중심 (0,0). 에이전트는 반경에 원형 배치되므로 가구는 가장자리/구석 위주.
ry는 Y축 회전(도 단위). 알 수 없는 item은 클라이언트가 무시.
"""

from __future__ import annotations

CATALOG = ("rug", "sofa", "table", "chair", "bookshelf", "plant", "lamp", "picture", "window")

# 마이룸/우리 방 (8×8)
ROOM_LAYOUT = [
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

# 우리 동네 (12×12) — 광장 느낌: 가운데 넓은 러그, 벤치(소파) 여러 개, 나무(화분) 다수
TOWN_LAYOUT = [
    {"item": "rug", "x": 0.0, "z": 0.0, "scale": 3.4, "color": "#b98a52"},
    {"item": "sofa", "x": -4.6, "z": -2.0, "ry": 90, "color": "#6f8a7a"},
    {"item": "sofa", "x": 4.6, "z": 2.0, "ry": -90, "color": "#8a7a6f"},
    {"item": "table", "x": 0.0, "z": 4.4, "color": "#9a7a55"},
    {"item": "bookshelf", "x": -5.4, "z": -4.6, "ry": 45, "color": "#7a5f45"},
    {"item": "plant", "x": 5.2, "z": -5.0, "scale": 1.3},
    {"item": "plant", "x": -5.2, "z": 5.0, "scale": 1.3},
    {"item": "plant", "x": 5.4, "z": 5.4, "scale": 1.1},
    {"item": "plant", "x": 2.5, "z": -5.2},
    {"item": "lamp", "x": -2.6, "z": 5.4},
    {"item": "lamp", "x": 3.0, "z": -2.6},
    {"item": "picture", "x": 0.0, "z": -5.96, "ry": 0},
    {"item": "window", "x": -5.96, "z": 1.2, "ry": 0},
    {"item": "window", "x": -5.96, "z": -2.4, "ry": 0},
]

# place id -> (room_size, layout)
LAYOUTS = {
    "room": (8, ROOM_LAYOUT),
    "town": (12, TOWN_LAYOUT),
}


def room_dict(place: str = "room") -> dict:
    """GET /room?place= 응답. 카탈로그에 있는 아이템만 통과시켜 직렬화."""
    size, layout = LAYOUTS.get(place, LAYOUTS["room"])
    valid = [dict(it) for it in layout if it.get("item") in CATALOG]
    return {"place": place, "room_size": size, "items": valid}
