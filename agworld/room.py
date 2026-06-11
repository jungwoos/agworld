"""방/장소 레이아웃 — 장소(place)별 씬 테마 + 오브젝트 배치 데이터.

서버가 구성을 데이터로 소유하고 GET /room?place=<id>로 내려준다(scene, room_size, items).
클라이언트는 씬 테마(indoor/outdoor)로 셸을 짓고, 가구 카탈로그(Three.js 빌더)로 오브젝트 조립.

장소:
- "jungs" / "jayy": 각자의 방. 실내(indoor), 8×8.
- "town": 야외(outdoor), 28×28 잔디 마을. 타운홀 + 분수 + 작은 집 2채(jungs/jayy).
  집 item은 place(탭 시 이동할 장소 id)와 label을 가진다 — 클라이언트가 탭 내비게이션에 사용.

좌표계: size×size, 중심 (0,0). 에이전트는 중앙 광장에 원형 배치. ry는 Y축 회전(도).
"""

from __future__ import annotations

# 실내 가구 + 야외 오브젝트. 알 수 없는 item은 클라이언트가 무시.
CATALOG = (
    "rug", "sofa", "table", "chair", "bookshelf", "plant", "lamp", "picture", "window",
    "townhall", "fountain", "tree", "lamppost", "bench", "house",
)

# Jungs' Room (실내, 8×8)
JUNGS_LAYOUT = [
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

# Jayy's Room (실내, 8×8) — 같은 뼈대, 다른 색/배치로 분위기 차이
JAYY_LAYOUT = [
    {"item": "rug", "x": 0.0, "z": 0.2, "scale": 2.6, "color": "#7a93b5"},
    {"item": "sofa", "x": 0.0, "z": -3.0, "ry": 0, "color": "#8a6f8a"},
    {"item": "bookshelf", "x": 3.3, "z": -2.4, "ry": -90, "color": "#6f5a45"},
    {"item": "table", "x": -0.4, "z": 2.6, "color": "#7a6a50"},
    {"item": "chair", "x": 1.2, "z": 2.6, "ry": -90, "color": "#6f5a45"},
    {"item": "plant", "x": -3.2, "z": -3.1, "scale": 1.1},
    {"item": "lamp", "x": -3.25, "z": 3.0},
    {"item": "picture", "x": -1.6, "z": -3.96, "ry": 0, "color": "#c8a05a"},
    {"item": "window", "x": -3.96, "z": -0.6, "ry": 0},
]

# Town (야외, 28×28 — 2배 확장) — 중앙 분수 광장, 뒤 타운홀, 앞쪽 양옆에 작은 집 2채
TOWN_LAYOUT = [
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

# place id -> (room_size, scene, layout)
LAYOUTS = {
    "jungs": (8, "indoor", JUNGS_LAYOUT),
    "jayy": (8, "indoor", JAYY_LAYOUT),
    "town": (28, "outdoor", TOWN_LAYOUT),
}


def room_dict(place: str = "jungs") -> dict:
    """GET /room?place= 응답. 카탈로그에 있는 아이템만 통과시켜 직렬화."""
    size, scene, layout = LAYOUTS.get(place, LAYOUTS["jungs"])
    valid = [dict(it) for it in layout if it.get("item") in CATALOG]
    return {"place": place, "room_size": size, "scene": scene, "items": valid}
