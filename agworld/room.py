"""방/장소 레이아웃 — 장소(place)별 씬 테마 + 오브젝트 배치 데이터.

서버가 구성을 데이터로 소유하고 GET /room?place=<id>로 내려준다(scene, room_size, items).
클라이언트는 씬 테마(indoor/outdoor)로 셸을 짓고, 가구 카탈로그(Three.js 빌더)로 오브젝트 조립.

장소:
- "room" (우리 방): 실내(indoor), 8×8, 벽/바닥/실내 가구.
- "town" (우리 동네): 야외(outdoor), 14×14 잔디 광장. 타운홀(건물) + 분수대(랜드마크) +
  나무/가로등/벤치. 고정 이웃 10인이 광장에 모인다.

좌표계: size×size, 중심 (0,0). 에이전트는 중앙 광장에 원형 배치. ry는 Y축 회전(도).
"""

from __future__ import annotations

# 실내 가구 + 야외 오브젝트. 알 수 없는 item은 클라이언트가 무시.
CATALOG = (
    "rug", "sofa", "table", "chair", "bookshelf", "plant", "lamp", "picture", "window",
    "townhall", "fountain", "tree", "lamppost", "bench",
)

# 우리 방 (실내, 8×8)
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

# 우리 동네 (야외, 14×14) — 잔디 광장: 가운데 분수(랜드마크), 뒤에 타운홀, 둘레에 나무/벤치/가로등
TOWN_LAYOUT = [
    {"item": "townhall", "x": 0.0, "z": -5.6, "ry": 0},   # 광장 뒤 타운홀(정면이 광장을 향함)
    {"item": "fountain", "x": 0.0, "z": 0.0},             # 중앙 랜드마크 — 이웃들이 둘러 모임
    {"item": "tree", "x": -5.8, "z": -4.4},
    {"item": "tree", "x": 5.8, "z": -3.8, "scale": 1.1},
    {"item": "tree", "x": -6.0, "z": 4.6},
    {"item": "tree", "x": 5.8, "z": 5.2, "scale": 1.15},
    {"item": "bench", "x": -4.6, "z": 3.4, "ry": 125},
    {"item": "bench", "x": 4.6, "z": 3.4, "ry": -125},
    {"item": "bench", "x": 0.0, "z": 5.6, "ry": 180},
    {"item": "lamppost", "x": -3.4, "z": -3.4},
    {"item": "lamppost", "x": 3.4, "z": -3.4},
    {"item": "plant", "x": 2.4, "z": 5.0},
    {"item": "plant", "x": -2.4, "z": 5.0},
]

# place id -> (room_size, scene, layout)
LAYOUTS = {
    "room": (8, "indoor", ROOM_LAYOUT),
    "town": (14, "outdoor", TOWN_LAYOUT),
}


def room_dict(place: str = "room") -> dict:
    """GET /room?place= 응답. 카탈로그에 있는 아이템만 통과시켜 직렬화."""
    size, scene, layout = LAYOUTS.get(place, LAYOUTS["room"])
    valid = [dict(it) for it in layout if it.get("item") in CATALOG]
    return {"place": place, "room_size": size, "scene": scene, "items": valid}
