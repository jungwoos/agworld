"""3D 웹뷰 HTTP 서버 — 라우팅만 담당하는 얇은 레이어.

클라이언트(HTML/CSS/JS)는 agworld/static/app/ 정적 파일로 분리돼 있고,
도메인 로직은 webstate.py(순수 함수)에 있다. 여기엔 HTTP/스레드만.

라우트:
    GET  /                  → static/app/index.html
    GET  /static/<path>     → 정적 파일 (vendor는 장기 캐시, 앱 파일은 no-cache)
    GET  /places            → 장소 목록(탭용)
    GET  /state?place=X     → X 장소 World 상태(JSON). 폴링=관전 중
    GET  /room?place=X      → X 장소 가구 레이아웃 (방은 config, town은 하드코딩)
    POST /whisper?place=X   → 내 에이전트에게 귓속말 (me+key 필요)
    POST /room/items?room=X → 방 가구 저장 (방 주인의 me+key 필요)

정체성: ?me=<agent_id>&key=<secret>. 키가 맞으면 그 에이전트가 '내 에이전트',
아니면 관전 모드. 슬립 온 디스커넥트는 장소별로 독립(보고 있는 장소만 틱 진행).
World는 스레드 안전이 아니라 모든 접근을 Lock으로 감싼다.
"""

from __future__ import annotations

import hmac
import json
import mimetypes
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import store
from .places import build_places, places_meta
from .room_config import get_agent_secrets
from .webstate import get_room_data, submit_whisper, update_room_items, world_state_dict

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
INDEX_FILE = os.path.join(STATIC_DIR, "app", "index.html")


def _query(path: str) -> dict:
    return parse_qs(urlparse(path).query)


def _place_param(path: str, places: dict) -> str:
    """쿼리에서 place 추출, 유효하지 않으면 첫 장소로 폴백."""
    pid = (_query(path).get("place", [None])[0])
    return pid if pid in places else next(iter(places))


def _viewer_param(path: str) -> str | None:
    """쿼리의 me+key를 입장 키와 대조해 보는 사람의 에이전트 id 반환. 불일치 시 None(관전)."""
    q = _query(path)
    me = (q.get("me", [None])[0] or "").strip()
    key = (q.get("key", [None])[0] or "").strip()
    if not me or not key:
        return None
    secret = get_agent_secrets().get(me)
    if secret and hmac.compare_digest(key, secret):
        return me
    return None


def make_handler(places: dict, lock: threading.Lock, shared: dict):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _json(self, obj, code=200):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                return json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                return {}

        def _serve_file(self, full_path: str, cache: str):
            if not os.path.isfile(full_path):
                self._json({"error": "not found"}, 404)
                return
            ctype, _ = mimetypes.guess_type(full_path)
            if full_path.endswith(".js"):
                ctype = "text/javascript"
            with open(full_path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.end_headers()
            self.wfile.write(body)

        def _serve_static(self, rel_path: str):
            # 디렉터리 탈출 방지
            full = os.path.normpath(os.path.join(STATIC_DIR, rel_path))
            if not full.startswith(os.path.normpath(STATIC_DIR) + os.sep):
                self._json({"error": "forbidden"}, 403)
                return
            # vendor(three.js)는 불변 — 장기 캐시. 앱 파일은 배포마다 갱신 — no-cache.
            cache = "public, max-age=31536000, immutable" if rel_path.startswith("vendor/") else "no-cache"
            self._serve_file(full, cache)

        def do_GET(self):
            route = urlparse(self.path).path
            if route == "/" or route.startswith("/index"):
                self._serve_file(INDEX_FILE, "no-cache")
            elif route.startswith("/static/"):
                self._serve_static(route[len("/static/"):])
            elif route == "/places":
                self._json(places_meta(places))
            elif route == "/state":
                pid = _place_param(self.path, places)
                shared["last_poll"][pid] = time.monotonic()
                viewer = _viewer_param(self.path)
                with lock:
                    self._json(world_state_dict(places[pid]["world"], viewer_id=viewer))
            elif route == "/room":
                self._json(get_room_data(_place_param(self.path, places)))
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            route = urlparse(self.path).path
            if route == "/whisper":
                pid = _place_param(self.path, places)
                shared["last_poll"][pid] = time.monotonic()
                viewer = _viewer_param(self.path)
                payload = self._read_body()
                with lock:
                    result = submit_whisper(places[pid]["world"], str(payload.get("text", "")), viewer_id=viewer)
                self._json(result)
            elif route == "/room/items":
                room_id = (_query(self.path).get("room", [None])[0]) or ""
                viewer = _viewer_param(self.path)
                payload = self._read_body()
                self._json(update_room_items(room_id, payload.get("items"), viewer_id=viewer))
            else:
                self._json({"error": "not found"}, 404)

    return Handler


def start_ticker(places: dict, lock: threading.Lock, shared: dict,
                 interval: float, idle_timeout: float, stop: threading.Event):
    """interval마다 각 장소를 틱. 최근 idle_timeout 내 폴링이 있는(관전 중) 장소만 진행."""
    def loop():
        while not stop.is_set():
            stop.wait(interval)
            if stop.is_set():
                break
            now = time.monotonic()
            with lock:
                for pid, p in places.items():
                    watching = (now - shared["last_poll"].get(pid, 0)) <= idle_timeout
                    p["world"].set_watching(watching)
                    p["world"].step()
    th = threading.Thread(target=loop, daemon=True)
    th.start()
    return th


def serve(places: dict | None = None, host: str = "127.0.0.1", port: int = 8765,
          interval: float = 10.0, idle_timeout: float | None = None) -> None:
    """블로킹 서버 실행. Ctrl-C로 종료."""
    if places is None:
        places = build_places()
    if idle_timeout is None:
        idle_timeout = max(interval * 2, 5.0)
    lock = threading.Lock()
    shared = {"last_poll": {pid: time.monotonic() for pid in places}}
    stop = threading.Event()

    try:
        httpd = ThreadingHTTPServer((host, port), make_handler(places, lock, shared))
    except OSError as e:
        print(f"❌ Failed to bind port {port}: {e}", flush=True)
        print(f"   → Try another port: python3 -m agworld --web --port {port + 1}", flush=True)
        return

    start_ticker(places, lock, shared, interval, idle_timeout, stop)
    url = f"http://{host}:{port}/"
    print(f"✅ AG-World 3D web view running → open in browser: {url}", flush=True)
    print(f"   Places: {', '.join(p['title'] for p in places.values())} · tick {interval:.0f}s · Ctrl-C to quit", flush=True)
    print(f"💾 Room storage: {'Upstash (persists across deploys)' if store.configured() else 'local file (ephemeral on Render)'}", flush=True)
    # 에이전트별 입장 링크(키 없이 접속하면 관전 모드)
    names = {a.id: a.name for p in places.values() for a in p["world"].agents}
    print("🔑 Invite links (each person opens their own):", flush=True)
    for aid, secret in get_agent_secrets().items():
        print(f"   {names.get(aid, aid)} → {url}?me={aid}&key={secret}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down — the world goes to sleep 💤", flush=True)
    finally:
        stop.set()
        httpd.shutdown()
