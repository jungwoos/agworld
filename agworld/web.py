"""웹뷰 서버 — stdlib http.server만으로 3D(Three.js) 관전 화면을 브라우저에 띄운다.

여러 장소(places)를 지원: "우리 방"(소수)과 "우리 동네"(고정 이웃 10인). 클라이언트가 탭으로
전환하면 ?place=<id>로 해당 World의 상태/방/귓속말을 다룬다.

    GET /places           → 장소 목록(탭용)
    GET /state?place=X    → X 장소 World 상태(JSON). 폴링=관전 중
    GET /room?place=X     → X 장소 가구 레이아웃
    POST /whisper?place=X → X 장소 내 에이전트에게 귓속말

백엔드 의존성 0(stdlib). 3D는 브라우저가 CDN Three.js로 처리. 슬립 온 디스커넥트는 장소별로
독립(보고 있는 장소만 틱 진행). World는 스레드 안전이 아니라 모든 접근을 Lock으로 감싼다.
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

from .places import build_places, places_meta
from .room import room_dict
from .room_config import get_agent_secrets
from .webstate import get_room_config, submit_whisper, update_room_config, world_state_dict

# 로컬 벤더 파일(three.module.js 등) 경로 — CDN 의존 제거
VENDOR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "vendor")


def _place_param(path: str, places: dict) -> str:
    """쿼리에서 place 추출, 유효하지 않으면 첫 장소로 폴백."""
    q = parse_qs(urlparse(path).query)
    pid = (q.get("place", [None])[0])
    return pid if pid in places else next(iter(places))


def _viewer_param(path: str) -> str | None:
    """쿼리의 me+key를 입장 키와 대조해 보는 사람의 에이전트 id 반환. 불일치 시 None(관전)."""
    q = parse_qs(urlparse(path).query)
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

        def _serve_static(self, base_dir, rel_path):
            # 디렉터리 탈출 방지
            full = os.path.normpath(os.path.join(base_dir, rel_path))
            if not full.startswith(os.path.normpath(base_dir) + os.sep):
                self._json({"error": "forbidden"}, 403)
                return
            if not os.path.isfile(full):
                self._json({"error": "not found"}, 404)
                return
            ctype, _ = mimetypes.guess_type(full)
            if full.endswith(".js"):
                ctype = "text/javascript"
            with open(full, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", ctype or "application/octet-stream")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "public, max-age=31536000")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            route = urlparse(self.path).path
            if route.startswith("/vendor/"):
                self._serve_static(VENDOR_DIR, route[len("/vendor/"):])
            elif route == "/" or route.startswith("/index"):
                body = PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif route == "/places":
                self._json(places_meta(places))
            elif route == "/state":
                pid = _place_param(self.path, places)
                shared["last_poll"][pid] = time.monotonic()
                viewer = _viewer_param(self.path)
                with lock:
                    self._json(world_state_dict(places[pid]["world"], viewer_id=viewer))
            elif route == "/room":
                self._json(room_dict(_place_param(self.path, places)))
            elif route == "/room/config":
                q = parse_qs(urlparse(self.path).query)
                self._json(get_room_config((q.get("room", [None])[0])))
            else:
                self._json({"error": "not found"}, 404)

        def do_POST(self):
            route = urlparse(self.path).path
            if route == "/whisper":
                pid = _place_param(self.path, places)
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    payload = json.loads(raw.decode("utf-8") or "{}")
                except json.JSONDecodeError:
                    payload = {}
                shared["last_poll"][pid] = time.monotonic()
                viewer = _viewer_param(self.path)
                with lock:
                    result = submit_whisper(places[pid]["world"], str(payload.get("text", "")), viewer_id=viewer)
                self._json(result)
            elif route == "/room/config":
                q = parse_qs(urlparse(self.path).query)
                room_id = (q.get("room", [None])[0]) or ""
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    payload = json.loads(raw.decode("utf-8") or "{}")
                except json.JSONDecodeError:
                    payload = {}
                result = update_room_config(room_id, payload)
                self._json(result)
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


PAGE = r"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AG-World 3D</title>
<style>
  * { box-sizing:border-box; margin:0; padding:0; }
  body { font-family:-apple-system,"Apple SD Gothic Neo",sans-serif; background:#ece6da; color:#2a2620; padding:20px; }
  .frame { max-width:1060px; margin:0 auto; }
  .topbar { display:flex; justify-content:space-between; align-items:center; margin-bottom:10px; }
  .tabs { display:flex; gap:6px; }
  .tab { font-size:13px; padding:6px 14px; border-radius:10px; border:1px solid #cdc0a2; background:#f5eedd; color:#6a6150; cursor:pointer; }
  .tab.active { background:#e0742f; color:#fff; border-color:#e0742f; font-weight:700; }
  .status { font-size:12px; color:#8a8170; }
  .layout { display:grid; grid-template-columns:1fr 300px; gap:16px; }
  @media(max-width:780px){ .layout{ grid-template-columns:1fr; } }
  .stage { position:relative; background:linear-gradient(180deg,#f5eedd,#e2d3b6); border:1px solid #cdc0a2; border-radius:16px; height:480px; overflow:hidden; }
  #scene { width:100%; height:100%; display:block; }
  #loading { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; color:#9a8f76; font-size:13px; text-align:center; padding:20px; }
  .rail { background:#fffdf7; border:1px solid #e2d9c2; border-radius:16px; padding:14px; display:flex; flex-direction:column; height:480px; }
  .rail h3 { font-size:12px; color:#8a8170; margin-bottom:10px; font-weight:700; }
  .feed { flex:1; overflow:auto; display:flex; flex-direction:column; gap:7px; }
  .line { font-size:13px; line-height:1.45; }
  .line .sp { font-weight:700; }
  .line.me .sp { color:#c4621f; }
  .tk { font-size:10px; color:#bcb29a; margin-top:4px; }
  .moment { background:#fbeede; border-left:3px solid #e0742f; padding:5px 8px; border-radius:6px; }
  .whisper { margin-top:16px; display:flex; align-items:center; gap:10px; background:#2a2620; border-radius:13px; padding:10px 14px; }
  .whisper .lab { font-size:12px; color:#e0b07f; white-space:nowrap; }
  .whisper input { flex:1; background:transparent; border:none; outline:none; color:#f4f1ea; font-size:13px; }
  .whisper input::placeholder { color:#7a7060; }
  .whisper button { font-size:12px; color:#2a2620; background:#e0742f; border:none; border-radius:8px; padding:7px 13px; font-weight:600; cursor:pointer; }
  .hint { font-size:10px; color:#9a8f76; margin-top:6px; text-align:center; }
</style>
<script type="importmap">
{ "imports": {
  "three": "/vendor/three.module.js",
  "three/addons/": "/vendor/addons/"
}}
</script>
</head>
<body>
<div class="frame">
  <div class="topbar">
    <div class="tabs" id="tabs"></div>
    <button id="roomEditBtn" style="font-size:12px; padding:5px 11px; border-radius:8px; border:1px solid #c9b78a; background:#f8f1df; color:#5c5240; cursor:pointer;">⚙️ Edit Room</button>
    <div class="status" id="status">Connecting...</div>
  </div>
  <div class="layout">
    <div class="stage"><canvas id="scene"></canvas><div id="loading">Loading 3D scene...</div></div>
    <div class="rail">
      <h3>💬 Conversation</h3>
      <div class="feed" id="feed"></div>
    </div>
  </div>
  <div class="whisper">
    <span class="lab" id="wLab">🤫 Whisper to <span id="whomLabel">your agent</span></span>
    <input id="wInput" placeholder="e.g. Tell Jayy to go easy on Dan" autocomplete="off">
    <button id="wSend">Whisper</button>
  </div>
  <div class="hint" id="hint">A whisper is a hint, not a command — your agent digests it in its own way</div>
</div>

<!-- Room Edit Modal -->
<div id="roomModal" style="display:none; position:fixed; inset:0; background:rgba(0,0,0,0.5); z-index:1000; align-items:center; justify-content:center;">
  <div style="background:#fffdf7; border-radius:16px; width:90%; max-width:520px; padding:20px; max-height:80vh; overflow:auto; box-shadow:0 10px 30px rgba(0,0,0,0.2);">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
      <h3 style="margin:0; font-size:16px; color:#2a2620;" id="modalTitle">⚙️ Edit Room</h3>
      <button id="closeModalBtn" style="background:none; border:none; font-size:22px; cursor:pointer; color:#8a8170;">×</button>
    </div>
    
    <div id="roomAgentsList" style="display:flex; flex-direction:column; gap:10px;"></div>
    
    <div style="margin-top:18px; display:flex; gap:8px;">
      <button id="addAgentBtn" style="flex:1; padding:9px; background:#e0742f; color:white; border:none; border-radius:8px; font-weight:600; cursor:pointer;">+ Add Agent</button>
      <button id="saveRoomBtn" style="flex:1; padding:9px; background:#2a2620; color:white; border:none; border-radius:8px; font-weight:600; cursor:pointer;">Save</button>
    </div>
    <div id="roomSaveMsg" style="margin-top:8px; font-size:12px; color:#8a8170; text-align:center;"></div>
  </div>
</div>

<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// 입장 키: URL의 ?me=&key=를 localStorage에 기억 → 이후엔 주소만 쳐도 유지. 키 없으면 관전 모드.
const _q = new URLSearchParams(location.search);
if(_q.get('me') && _q.get('key')){ localStorage.setItem('agw_me', _q.get('me')); localStorage.setItem('agw_key', _q.get('key')); }
const ME = localStorage.getItem('agw_me') || '', MEKEY = localStorage.getItem('agw_key') || '';
const AUTH = ME ? ('&me='+encodeURIComponent(ME)+'&key='+encodeURIComponent(MEKEY)) : '';

const PALETTE = [0x6fa8a0,0xb08a6f,0xe0a36f,0x8f9bd0,0xc08fb0,0xa0b07a,0xd0a060,0x70b0c0,0xc09070,0x90c090];
const HAIRS = [0x2b2118,0x4a3526,0x1a1a1a,0x6b4a2f,0x5c3a1e,0x8a6a3a,0x3a2a1a,0x705038,0x4a4a4a,0x2a1c14];
const ACCENT = 0xe0742f;

const cv = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf2e9d6);
function setShadow(obj, cast, recv){ obj.traverse(m=>{ if(m.isMesh){ m.castShadow=cast; m.receiveShadow=recv; } }); }

let roomSize = 8, radius = 2.4, camera;
function makeCamera(){
  const r = cv.getBoundingClientRect(), aspect = r.width/Math.max(1,r.height), F = roomSize*0.78;
  camera = new THREE.OrthographicCamera(-F*aspect, F*aspect, F, -F, 0.1, 200);
  const d = roomSize*1.1;
  camera.position.set(d, d*0.9, d); camera.lookAt(0, 1, 0);
}
makeCamera();
const controls = new OrbitControls(camera, renderer.domElement);
controls.enablePan = false; controls.minPolarAngle = 0.3; controls.maxPolarAngle = 1.35; controls.target.set(0,1,0);

// 자연광: 하늘광(HemisphereLight) + 태양(그림자 캐스팅 DirectionalLight)
const hemi = new THREE.HemisphereLight(0xbfe3f2, 0x8a9a6a, 0.6); scene.add(hemi);
const sun = new THREE.DirectionalLight(0xfff1d8, 1.7); sun.castShadow = true;
sun.shadow.mapSize.set(1024, 1024); sun.shadow.bias = -0.0005; sun.shadow.normalBias = 0.02;
scene.add(sun); scene.add(sun.target);
function tuneSun(size, sceneType){
  sun.position.set(size*0.85, size*1.6, size*0.7); sun.target.position.set(0, 0, 0);
  const c = sun.shadow.camera; c.left=-size; c.right=size; c.top=size; c.bottom=-size; c.near=1; c.far=size*5; c.updateProjectionMatrix();
  if(sceneType === 'outdoor'){ hemi.color.set(0xbfe3f2); hemi.groundColor.set(0x7d9a5a); hemi.intensity=0.7; sun.color.set(0xfff1d8); sun.intensity=1.9; }
  else { hemi.color.set(0xf3e8d2); hemi.groundColor.set(0xb0a080); hemi.intensity=0.85; sun.color.set(0xffe9c8); sun.intensity=1.15; }
}

// ===== 씬 셸 — 장소 크기/테마에 맞춰 재생성 (indoor=방, outdoor=잔디 광장) =====
let shellGroup = new THREE.Group(); scene.add(shellGroup);
function buildShell(size, sceneType){
  scene.remove(shellGroup); shellGroup = new THREE.Group(); scene.add(shellGroup);
  tuneSun(size, sceneType);
  if(sceneType === 'outdoor'){
    scene.background = new THREE.Color(0xbfe3f2);                       // 하늘
    const grass = new THREE.Mesh(new THREE.BoxGeometry(size*1.9,0.3,size*1.9), new THREE.MeshStandardMaterial({color:0x86b96a}));
    grass.position.y = -0.15; shellGroup.add(grass);                   // 잔디밭(넓게)
    const plazaR = Math.min(size*0.42, 6.2);                            // 광장은 절대 크기 유지(마을이 커져도 안 비대해짐)
    const plaza = new THREE.Mesh(new THREE.CircleGeometry(plazaR,48), new THREE.MeshStandardMaterial({color:0xd8cdb4}));
    plaza.rotation.x = -Math.PI/2; plaza.position.y = 0.02; shellGroup.add(plaza);   // 포장된 광장
    const edge = new THREE.Mesh(new THREE.RingGeometry(plazaR,plazaR+0.55,48), new THREE.MeshStandardMaterial({color:0xb6a886,side:THREE.DoubleSide}));
    edge.rotation.x = -Math.PI/2; edge.position.y = 0.025; shellGroup.add(edge);     // 광장 테두리
    const path = new THREE.Mesh(new THREE.BoxGeometry(1.6,0.05,size*0.55), new THREE.MeshStandardMaterial({color:0xd2c7ad}));
    path.position.set(0,0.02,-size*0.32); shellGroup.add(path);        // 타운홀로 가는 길
  } else {
    scene.background = new THREE.Color(0xf2e9d6);                       // 실내 크림
    const floor = new THREE.Mesh(new THREE.BoxGeometry(size,0.3,size), new THREE.MeshStandardMaterial({color:0xd9c8a2}));
    floor.position.y = -0.15; shellGroup.add(floor);
    const grid = new THREE.GridHelper(size,size,0xb09a6a,0xcbbb95); grid.position.y = 0.011; shellGroup.add(grid);
    const mkWall = (w,h,x,z,ry,c)=>{ const m=new THREE.Mesh(new THREE.PlaneGeometry(w,h),
      new THREE.MeshStandardMaterial({color:c,side:THREE.DoubleSide})); m.position.set(x,h/2,z); m.rotation.y=ry; shellGroup.add(m); };
    mkWall(size,4,0,-size/2,0,0xe7dabf); mkWall(size,4,-size/2,0,Math.PI/2,0xdccba3);
  }
  setShadow(shellGroup, false, true);   // 바닥/잔디/광장/벽은 그림자를 '받음'
}

// ===== 가구 카탈로그 =====
function fmat(c){ return new THREE.MeshStandardMaterial({ color:new THREE.Color(c), roughness:0.85 }); }
function fbox(w,h,d,c){ return new THREE.Mesh(new THREE.BoxGeometry(w,h,d), fmat(c)); }
function fcyl(rt,rb,h,c){ return new THREE.Mesh(new THREE.CylinderGeometry(rt,rb,h,16), fmat(c)); }
const FURNITURE = {
  rug(o){ const g=new THREE.Group(); const r=fbox(2,0.04,1.4,o.color||'#c98f5a'); r.position.y=0.02; g.add(r); return g; },
  sofa(o){ const c=o.color||'#7a8a6f', g=new THREE.Group(); const b=fbox(2,0.4,0.9,c); b.position.y=0.3; g.add(b);
    const bk=fbox(2,0.6,0.2,c); bk.position.set(0,0.7,-0.35); g.add(bk);
    [-1,1].forEach(x=>{ const a=fbox(0.2,0.55,0.9,c); a.position.set(x,0.5,0); g.add(a); }); return g; },
  table(o){ const c=o.color||'#9a7a55', g=new THREE.Group(); const t=fbox(1.2,0.12,0.8,c); t.position.y=0.7; g.add(t);
    [[-0.5,-0.3],[0.5,-0.3],[-0.5,0.3],[0.5,0.3]].forEach(([x,z])=>{ const l=fbox(0.1,0.7,0.1,c); l.position.set(x,0.35,z); g.add(l); }); return g; },
  chair(o){ const c=o.color||'#8a6f4f', g=new THREE.Group(); const s=fbox(0.5,0.1,0.5,c); s.position.y=0.45; g.add(s);
    const b=fbox(0.5,0.5,0.1,c); b.position.set(0,0.7,-0.2); g.add(b);
    [[-0.2,-0.2],[0.2,-0.2],[-0.2,0.2],[0.2,0.2]].forEach(([x,z])=>{ const l=fbox(0.08,0.45,0.08,c); l.position.set(x,0.22,z); g.add(l); }); return g; },
  bookshelf(o){ const c=o.color||'#8a6f4f', g=new THREE.Group(); const fr=fbox(1.4,2,0.4,c); fr.position.y=1; g.add(fr);
    const cols=['#c0573f','#3f6cc0','#d8a93f','#5aa05a','#b06fb0'];
    for(let s=0;s<3;s++) for(let k=0;k<5;k++){ const bk=fbox(0.12,0.5,0.3,cols[(s*5+k)%cols.length]); bk.position.set(-0.5+k*0.25,0.55+s*0.6,0.06); g.add(bk); } return g; },
  plant(o){ const g=new THREE.Group(); const p=fcyl(0.22,0.28,0.4,'#b5764a'); p.position.y=0.2; g.add(p);
    const f1=new THREE.Mesh(new THREE.SphereGeometry(0.35,12,10), fmat('#5a8a4a')); f1.position.y=0.7; g.add(f1);
    const f2=new THREE.Mesh(new THREE.SphereGeometry(0.25,12,10), fmat('#6fa05a')); f2.position.set(0.18,0.92,0.05); g.add(f2); return g; },
  lamp(o){ const g=new THREE.Group(); const base=fcyl(0.18,0.22,0.08,'#444'); base.position.y=0.04; g.add(base);
    const pole=fcyl(0.04,0.04,1.4,'#666'); pole.position.y=0.74; g.add(pole);
    const sh=new THREE.Mesh(new THREE.ConeGeometry(0.32,0.4,16,1,true), new THREE.MeshStandardMaterial({color:0xf5e6b0,emissive:0xffe9a0,emissiveIntensity:0.6,side:THREE.DoubleSide}));
    sh.position.y=1.5; g.add(sh); const lp=new THREE.PointLight(0xffe9b0,0.5,7); lp.position.y=1.4; g.add(lp); return g; },
  picture(o){ const g=new THREE.Group(); g.add(fbox(1,0.7,0.06,'#5a4a35')); g.add(fbox(0.85,0.55,0.07,o.color||'#9ab0c8')); g.position.y=2.2; return g; },
  window(o){ const g=new THREE.Group(); g.add(fbox(0.1,1.4,1.6,'#6a5a45')); g.add(fbox(0.05,1.2,1.4,'#add3e6')); g.position.y=2.0; return g; },
  // ── 야외 오브젝트 ──
  townhall(o){ const g=new THREE.Group();
    const base=fbox(4.2,2.6,2.2,'#e9e0cf'); base.position.y=1.3; g.add(base);
    const roof=fbox(4.8,0.4,2.6,'#9a5a45'); roof.position.y=2.7; g.add(roof);
    const ped=new THREE.Mesh(new THREE.CylinderGeometry(0.001,1.5,1.0,4), fmat('#a5634c')); // 삼각 페디먼트(피라미드)
    ped.rotation.y=Math.PI/4; ped.scale.set(2.0,1,1.3); ped.position.y=3.2; g.add(ped);
    [-1.6,-0.55,0.55,1.6].forEach(x=>{ const c=fcyl(0.16,0.16,2.2,'#f3ece0'); c.position.set(x,1.2,1.15); g.add(c); }); // 기둥
    const door=fbox(0.9,1.5,0.12,'#6a4a30'); door.position.set(0,0.75,1.18); g.add(door);
    const clock=new THREE.Mesh(new THREE.CircleGeometry(0.34,24), new THREE.MeshStandardMaterial({color:0xf5f0e0})); clock.position.set(0,3.0,1.34); g.add(clock);
    const sign=sprite('🏛 Town Hall',30,'#5a4a35'); sign.scale.set(2.6,1.0,1); sign.position.set(0,4.3,0); g.add(sign);
    return g; },
  fountain(o){ const g=new THREE.Group();
    const basin=fcyl(1.2,1.3,0.4,'#b9b2a2'); basin.position.y=0.2; g.add(basin);
    const water=new THREE.Mesh(new THREE.CylinderGeometry(1.05,1.05,0.12,24), new THREE.MeshStandardMaterial({color:0x6fb6d8,transparent:true,opacity:0.85})); water.position.y=0.42; g.add(water);
    const pillar=fcyl(0.18,0.22,0.9,'#cfc7b6'); pillar.position.y=0.85; g.add(pillar);
    const top=fcyl(0.5,0.45,0.18,'#b9b2a2'); top.position.y=1.32; g.add(top);
    const tw=new THREE.Mesh(new THREE.CylinderGeometry(0.4,0.4,0.08,20), new THREE.MeshStandardMaterial({color:0x7cc0e0,transparent:true,opacity:0.85})); tw.position.y=1.42; g.add(tw);
    const spout=new THREE.Mesh(new THREE.SphereGeometry(0.12,12,10), new THREE.MeshStandardMaterial({color:0x9ad6ee,transparent:true,opacity:0.8})); spout.position.y=1.62; g.add(spout);
    return g; },
  tree(o){ const g=new THREE.Group(); const tr=fcyl(0.16,0.22,1.2,'#7a5235'); tr.position.y=0.6; g.add(tr);
    const f1=new THREE.Mesh(new THREE.SphereGeometry(0.8,14,12), fmat('#4f8a46')); f1.position.y=1.6; g.add(f1);
    const f2=new THREE.Mesh(new THREE.SphereGeometry(0.55,14,12), fmat('#5fa055')); f2.position.set(0.5,1.4,0.2); g.add(f2);
    const f3=new THREE.Mesh(new THREE.SphereGeometry(0.5,14,12), fmat('#5a9a4e')); f3.position.set(-0.45,1.45,-0.1); g.add(f3); return g; },
  lamppost(o){ const g=new THREE.Group(); const pole=fcyl(0.07,0.09,2.4,'#3a3a3a'); pole.position.y=1.2; g.add(pole);
    const head=new THREE.Mesh(new THREE.SphereGeometry(0.18,14,12), new THREE.MeshStandardMaterial({color:0xfff2c0,emissive:0xffe9a0,emissiveIntensity:0.8})); head.position.y=2.45; g.add(head);
    const lp=new THREE.PointLight(0xffe9b0,0.45,8); lp.position.y=2.45; g.add(lp); return g; },
  bench(o){ const c=o.color||'#8a6f4f', g=new THREE.Group(); const seat=fbox(1.4,0.1,0.45,c); seat.position.y=0.45; g.add(seat);
    const back=fbox(1.4,0.4,0.1,c); back.position.set(0,0.7,-0.18); g.add(back);
    [-0.6,0.6].forEach(x=>{ const l=fbox(0.1,0.45,0.45,'#5a4a35'); l.position.set(x,0.22,0); g.add(l); }); return g; },
  // 작은 집 — 탭하면 그 방으로 이동(o.place). 문이 +z를 향함.
  house(o){ const g=new THREE.Group(); const wall=o.color||'#e9dcc4';
    const base=fbox(3.0,2.0,2.6,wall); base.position.y=1.0; g.add(base);
    const roof=new THREE.Mesh(new THREE.CylinderGeometry(0.001,2.35,1.2,4), fmat('#a5634c'));
    roof.rotation.y=Math.PI/4; roof.scale.set(1.05,1,0.9); roof.position.y=2.6; g.add(roof);
    const door=fbox(0.7,1.2,0.1,'#6a4a30'); door.position.set(0.5,0.6,1.32); g.add(door);
    const knob=new THREE.Mesh(new THREE.SphereGeometry(0.05,8,8), fmat('#d8b25a')); knob.position.set(0.74,0.62,1.4); g.add(knob);
    const win=fbox(0.8,0.7,0.08,'#add3e6'); win.position.set(-0.75,1.2,1.32); g.add(win);
    const frame=fbox(0.92,0.82,0.06,'#7a6048'); frame.position.set(-0.75,1.2,1.3); g.add(frame);
    if(o.label){ const sign=sprite('🏠 '+o.label,24,'#5a4a35'); sign.scale.set(3.0,1.2,1); sign.position.y=3.9; g.add(sign); }
    return g; },
};
let furnitureGroup = new THREE.Group(); scene.add(furnitureGroup);
let houses = [];   // 탭 내비게이션 대상: {group, place, label, x, z}
function buildFurniture(items){
  scene.remove(furnitureGroup); furnitureGroup = new THREE.Group(); scene.add(furnitureGroup);
  houses = [];
  (items||[]).forEach(it=>{ const b=FURNITURE[it.item]; if(!b) return; const g=b(it);
    g.position.x+=(it.x||0); g.position.z+=(it.z||0); if(it.ry) g.rotation.y=it.ry*Math.PI/180; if(it.scale) g.scale.multiplyScalar(it.scale); furnitureGroup.add(g);
    if(it.item==='house' && it.place){ g.userData.place=it.place; houses.push({group:g, place:it.place, label:it.label||it.place, x:it.x||0, z:it.z||0}); } });
  setShadow(furnitureGroup, true, true);   // 가구/타운홀/나무는 그림자를 '드리움'
}

// ===== 스프라이트(이모지/이름) =====
function sprite(text, px, color){
  const c=document.createElement('canvas'); c.width=c.height=128; const g=c.getContext('2d');
  g.font=px+'px -apple-system,"Apple Color Emoji","Apple SD Gothic Neo",sans-serif'; g.textAlign='center'; g.textBaseline='middle';
  if(color) g.fillStyle=color; g.fillText(text,64,70);
  const tex=new THREE.CanvasTexture(c); return new THREE.Sprite(new THREE.SpriteMaterial({map:tex,transparent:true}));
}

// ===== 아바타 =====
let avatars = {};
function clearAvatars(){ for(const id in avatars){ scene.remove(avatars[id].group); } avatars = {}; }
function placeCell(i, n){ if(n===1) return [0,0]; const a=-Math.PI/2 + i*(2*Math.PI/n); return [radius*Math.cos(a), radius*Math.sin(a)]; }
// 팔/다리: 윗부분(어깨/엉덩이)을 피벗으로 회전하게 — 피벗 그룹 + 아래로 내린 박스
function limbPivot(px,py,pz, w,h,d, color, offy){
  const pivot=new THREE.Group(); pivot.position.set(px,py,pz);
  const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d), new THREE.MeshStandardMaterial({color})); m.position.y=offy; m.castShadow=true;
  pivot.add(m); return pivot;
}
function makeAvatar(a, i, n, idx){
  const group=new THREE.Group(); const [x,z]=placeCell(i,n); group.position.set(x,0,z);
  const shirt=PALETTE[idx%PALETTE.length], skin=0xe8c39a, pants=0x3f4a6a;
  const bodyGroup=new THREE.Group(); group.add(bodyGroup);  // 통째로 살짝 bob
  // 마인크래프트풍 블록 휴머노이드 (발 y=0 기준)
  const legL=limbPivot(-0.13,0.7,0, 0.2,0.7,0.22, pants, -0.35);
  const legR=limbPivot( 0.13,0.7,0, 0.2,0.7,0.22, pants, -0.35);
  const armL=limbPivot(-0.34,1.3,0, 0.16,0.6,0.2, shirt, -0.3);
  const armR=limbPivot( 0.34,1.3,0, 0.16,0.6,0.2, shirt, -0.3);
  const torso=new THREE.Mesh(new THREE.BoxGeometry(0.5,0.6,0.28), new THREE.MeshStandardMaterial({color:shirt})); torso.position.y=1.0; torso.castShadow=true;
  const head=new THREE.Mesh(new THREE.BoxGeometry(0.5,0.5,0.5), new THREE.MeshStandardMaterial({color:skin})); head.position.y=1.55; head.castShadow=true;
  // 머리카락(에이전트별 색) + 눈
  const hairCol=HAIRS[idx%HAIRS.length], hairMat=new THREE.MeshStandardMaterial({color:hairCol});
  const hairTop=new THREE.Mesh(new THREE.BoxGeometry(0.54,0.16,0.54),hairMat); hairTop.position.y=1.74; hairTop.castShadow=true;
  const hairBack=new THREE.Mesh(new THREE.BoxGeometry(0.54,0.34,0.12),hairMat); hairBack.position.set(0,1.55,-0.23); hairBack.castShadow=true;
  const eyeMat=new THREE.MeshStandardMaterial({color:0x2a2622});
  const eyeL=new THREE.Mesh(new THREE.BoxGeometry(0.09,0.12,0.04),eyeMat); eyeL.position.set(-0.1,1.58,0.255);
  const eyeR=new THREE.Mesh(new THREE.BoxGeometry(0.09,0.12,0.04),eyeMat); eyeR.position.set(0.1,1.58,0.255);
  bodyGroup.add(legL,legR,armL,armR,torso,head,hairTop,hairBack,eyeL,eyeR);
  const emo=sprite(a.emoji,92); emo.scale.set(0.9,0.9,0.9); emo.position.y=2.25; group.add(emo);  // 머리 위 감정
  const nm=sprite(a.name+(a.is_mine?' ★':''),30,a.is_mine?'#c4621f':'#5a5444'); nm.scale.set(1.6,0.8,1); nm.position.y=-0.05; group.add(nm);
  if(a.is_mine){ const ring=new THREE.Mesh(new THREE.TorusGeometry(0.55,0.05,8,32), new THREE.MeshStandardMaterial({color:ACCENT}));
    ring.rotation.x=Math.PI/2; ring.position.y=0.02; group.add(ring); }
  const pulse=new THREE.Mesh(new THREE.RingGeometry(0.5,0.62,32), new THREE.MeshBasicMaterial({color:ACCENT,transparent:true,opacity:0,side:THREE.DoubleSide}));
  pulse.rotation.x=-Math.PI/2; pulse.position.y=0.03; group.add(pulse);
  scene.add(group);
  emo.material.opacity=0; emo.visible=false;   // 평소 숨김, 감정 바뀔 때만 팝
  avatars[a.id]={group,body:bodyGroup,emo,pulse,emoji:a.emoji,speaking:a.speaking,phase:Math.random()*6.28,limbs:{legL,legR,armL,armR},swing:0,emoShownAt:elapsed};
}
function updateAvatar(a){ const av=avatars[a.id];
  if(av.emoji!==a.emoji){ av.emo.material.map.dispose(); av.emo.material=sprite(a.emoji,92).material; av.emoji=a.emoji; av.emoShownAt=elapsed; } // 감정 바뀜 → 다시 팝
  av.speaking=a.speaking; }
// 감정 이모지 표시 곡선: 0~3초 풀, 3~4초 페이드, 이후 숨김
const EMO_FULL=3.0, EMO_FADE=1.0;
function emoOpacity(shownAt){ if(shownAt===undefined) return 0; const age=elapsed-shownAt;
  return age<EMO_FULL ? 1 : (age<EMO_FULL+EMO_FADE ? 1-(age-EMO_FULL)/EMO_FADE : 0); }

let STATE=null, currentPlace=null, currentScene='indoor', ready=false;
function syncScene(){ if(!STATE) return; const n=STATE.agents.length;
  STATE.agents.forEach((a,i)=>{ if(avatars[a.id]) updateAvatar(a); else makeAvatar(a,i,n,i); }); }

// 랜덤 배회: 방/광장 안 한 점을 목표로 천천히 걷고, 도착하면 새 목표. 중앙(분수 등)은 회피.
const WANDER_SPEED = 0.7;
function newTarget(){
  const maxR = Math.min(roomSize*0.38, 7.5), keep = (currentScene==='outdoor' ? 1.9 : 0.6);
  let x, z, r;
  do { x=(Math.random()*2-1)*maxR; z=(Math.random()*2-1)*maxR; r=Math.hypot(x,z); } while(r<keep || r>maxR);
  return { x, z };
}

// ===== 집 탭 내비게이션: 경로 하이라이트 + 경로 따라 걷기 =====
const PATH_SPEED = 1.8;
let pathGroup = null;
function clearPath(){ if(pathGroup){ scene.remove(pathGroup); pathGroup=null; } }
function buildPathDots(wps){
  clearPath(); pathGroup = new THREE.Group();
  for(let s=0; s<wps.length-1; s++){
    const a=wps[s], b=wps[s+1], d=Math.hypot(b.x-a.x, b.z-a.z), n=Math.max(2, Math.round(d/0.7));
    for(let k=0; k<=n; k++){ const t=k/n;
      const dot=new THREE.Mesh(new THREE.CircleGeometry(0.14,12),
        new THREE.MeshBasicMaterial({color:ACCENT, transparent:true, opacity:0.85}));
      dot.rotation.x=-Math.PI/2; dot.position.set(a.x+(b.x-a.x)*t, 0.05, a.z+(b.z-a.z)*t);
      dot.userData.ph=t*4;   // 펄스 위상(흐르는 느낌)
      pathGroup.add(dot); }
  }
  scene.add(pathGroup);
}
// start→target 직선이 분수(중앙 r≈2.6)를 지나면 우회 경유점을 끼운다
function routeAround(start, target){
  const wps=[start];
  const dx=target.x-start.x, dz=target.z-start.z, len=Math.hypot(dx,dz);
  if(len>0.01){
    // 선분-원점 최소거리
    const t=Math.max(0, Math.min(1, -(start.x*dx+start.z*dz)/(len*len)));
    const cx=start.x+dx*t, cz=start.z+dz*t;
    if(Math.hypot(cx,cz)<2.6){
      const ma=Math.atan2((start.z+target.z)/2, (start.x+target.x)/2);
      wps.push({x:Math.cos(ma)*3.6, z:Math.sin(ma)*3.6});
    }
  }
  wps.push(target);
  return wps;
}
function navigateToHouse(h){
  // 집 정면(광장 쪽)으로 2.6만큼 떨어진 접근점
  const dl=Math.hypot(h.x,h.z)||1, door={x:h.x-h.x/dl*2.6, z:h.z-h.z/dl*2.6};
  const mover=avatars[ME];
  const start = mover ? {x:mover.group.position.x, z:mover.group.position.z} : {x:0, z:2.4};
  const wps = routeAround(start, door);
  buildPathDots(wps);
  if(mover){
    mover.path=wps.slice(1);   // 첫 점은 현재 위치
    mover.onArrive=()=>{ clearPath(); switchPlace(h.place); };
  } else {
    setTimeout(()=>{ clearPath(); switchPlace(h.place); }, 1400);
  }
}
// 탭 감지: 드래그(OrbitControls)와 구분 — 이동 6px 미만 + 400ms 미만일 때만
const ray=new THREE.Raycaster(), ndc=new THREE.Vector2();
let downX=0, downY=0, downT=0;
cv.addEventListener('pointerdown', e=>{ downX=e.clientX; downY=e.clientY; downT=performance.now(); });
cv.addEventListener('pointerup', e=>{
  if(Math.hypot(e.clientX-downX, e.clientY-downY)>6 || performance.now()-downT>400) return;
  if(!houses.length) return;
  const r=cv.getBoundingClientRect();
  ndc.x=((e.clientX-r.left)/r.width)*2-1; ndc.y=-((e.clientY-r.top)/r.height)*2+1;
  ray.setFromCamera(ndc, camera);
  const hits=ray.intersectObjects(houses.map(h=>h.group), true);
  if(!hits.length) return;
  let obj=hits[0].object; while(obj && !obj.userData.place) obj=obj.parent;
  if(!obj) return;
  const h=houses.find(x=>x.place===obj.userData.place);
  if(h) navigateToHouse(h);
});

const clock=new THREE.Clock(); let elapsed=0;
function animate(){ requestAnimationFrame(animate);
  const dt=Math.min(clock.getDelta(),0.05); elapsed+=dt; const watching=STATE?STATE.watching:true;
  if(pathGroup){ pathGroup.children.forEach(d=>{ d.material.opacity=0.45+0.4*Math.sin(elapsed*5-d.userData.ph); }); }
  for(const id in avatars){ const av=avatars[id], g=av.group;
    // idle ↔ walk 상태머신: 목표까지 걷고 → 도착하면 2~6초 멈춰 쉼 → 새 목표
    let walking=false;
    if(av.path && av.path.length){   // 경로 추종(집 탭 내비게이션) — 배회/발화보다 우선
      const t=av.path[0], dx=t.x-g.position.x, dz=t.z-g.position.z, d=Math.hypot(dx,dz);
      if(d<0.16){ av.path.shift();
        if(!av.path.length){ av.path=null; av.mode='idle'; av.until=elapsed+2; if(av.onArrive){ const f=av.onArrive; av.onArrive=null; f(); } } }
      else { const step=Math.min(PATH_SPEED*dt,d); g.position.x+=dx/d*step; g.position.z+=dz/d*step; walking=true;
        let diff=Math.atan2(dx,dz)-g.rotation.y; diff=Math.atan2(Math.sin(diff),Math.cos(diff)); g.rotation.y+=diff*Math.min(1,dt*8); }
    }
    else if(watching && !av.speaking){   // 말할 차례면 멈춰서 말함, 자면 정지
      if(av.mode===undefined){ av.mode='idle'; av.until=elapsed + 0.3 + Math.random()*2.5; }  // 시작 스태거
      if(av.mode==='idle'){
        if(elapsed>=av.until){ const t=newTarget(); av.tx=t.x; av.tz=t.z; av.mode='walk'; }
      } else {
        const dx=av.tx-g.position.x, dz=av.tz-g.position.z, d=Math.hypot(dx,dz);
        if(d<0.12){ av.mode='idle'; av.until=elapsed + 2 + Math.random()*4; }   // 도착 → 2~6초 쉼
        else { const step=Math.min(WANDER_SPEED*dt,d); g.position.x+=dx/d*step; g.position.z+=dz/d*step; walking=true;
          // 진행 방향으로 회전(+z가 정면). 최단 경로로 부드럽게.
          let diff=Math.atan2(dx,dz)-g.rotation.y; diff=Math.atan2(Math.sin(diff),Math.cos(diff)); g.rotation.y+=diff*Math.min(1,dt*6); }
      }
    }
    if(av.speaking && watching){ const ph=(elapsed%1.2)/1.2; av.pulse.scale.setScalar(1+ph*1.8); av.pulse.material.opacity=0.5*(1-ph); }
    else { av.pulse.material.opacity=0; }
    const amp = walking?0.06:0.02;   // 걸을 때만 발걸음 bob, 쉴 땐 잔잔하게
    av.body.position.y = watching ? Math.sin(elapsed*(walking?6:1.5)+(av.phase||0))*amp : 0;
    // 팔다리 스윙(걸을 때만, 멈추면 0으로 부드럽게)
    const targetSwing = walking ? Math.sin(elapsed*8 + (av.phase||0))*0.5 : 0;
    av.swing += (targetSwing - av.swing) * Math.min(1, dt*10);
    if(av.limbs){ av.limbs.legL.rotation.x=av.swing; av.limbs.legR.rotation.x=-av.swing; av.limbs.armL.rotation.x=-av.swing; av.limbs.armR.rotation.x=av.swing; }
    // 감정 이모지: 바뀐 뒤 3초 보이고 페이드아웃
    const eop = emoOpacity(av.emoShownAt); av.emo.material.opacity=eop; av.emo.visible = eop>0.01;
  }
  renderer.toneMappingExposure = watching?1:0.7; controls.update(); renderer.render(scene,camera); }
function resize(){ const r=cv.getBoundingClientRect(); renderer.setSize(r.width,r.height,false); makeCamera(); controls.object=camera; }
window.addEventListener('resize', resize);

function esc(s){ const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }

async function loadRoom(place){
  let data; try { data=await (await fetch('/room?place='+place)).json(); } catch(e){ return; }
  roomSize = data.room_size || 8; radius = roomSize*0.28; currentScene = data.scene || 'indoor';
  makeCamera(); controls.object=camera;
  buildShell(roomSize, currentScene); buildFurniture(data.items);
}

// 보는 사람 UI: 내 에이전트면 속삭임 활성, 아니면 관전 모드로 잠금
let _lastViewer = '__init__';
function applyViewerUI(my){
  const cur = my ? my.id : null;
  if(cur === _lastViewer) return; _lastViewer = cur;
  const lab=document.getElementById('wLab'), wIn=document.getElementById('wInput'), wBtn=document.getElementById('wSend');
  if(my){
    lab.innerHTML='🤫 Whisper to <span id="whomLabel">'+esc(my.name)+'</span>';
    wIn.disabled=false; wBtn.disabled=false;
  } else {
    lab.textContent='👀 Spectator mode';
    wIn.disabled=true; wIn.placeholder='Open your agent invite link (?me=…&key=…) to whisper';
    wBtn.disabled=true;
  }
}

async function poll(){
  if(!currentPlace) return;
  let s; try { s=await (await fetch('/state?place='+currentPlace+AUTH)).json(); }
  catch(e){ document.getElementById('status').textContent='Disconnected'; return; }
  STATE=s;
  if(!ready){ ready=true; document.getElementById('loading').style.display='none'; }
  document.getElementById('status').textContent=(s.watching?'Watching':'Sleeping 💤')+` · tick ${s.t} · $${s.cost}`;
  applyViewerUI(s.my_agent);
  syncScene();
  const feed=document.getElementById('feed'); let html='', lastT=null;
  if(s.feed.length===0) html='<div class="tk">(quiet so far...)</div>';
  s.feed.forEach(f=>{ if(f.t!==lastT){ html+=`<div class="tk">— tick ${f.t}${f.decisive?' ⚡':''} —</div>`; lastT=f.t; }
    html+=`<div class="line${f.is_mine?' me':''}${f.decisive?' moment':''}"><span class="sp">${esc(f.name)}:</span> ${esc(f.text)} ${f.emoji}</div>`; });
  feed.innerHTML=html; feed.scrollTop=feed.scrollHeight;
}

async function switchPlace(pid){
  if(pid===currentPlace) return;
  currentPlace=pid; STATE=null;
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active', t.dataset.place===pid));
  // Edit Room은 방에서만 (town은 하드코딩 장소)
  document.getElementById('roomEditBtn').style.display = (pid==='town') ? 'none' : '';
  clearPath(); clearAvatars();
  await loadRoom(pid);
  poll();
}

async function buildTabs(){
  let list; try { list=await (await fetch('/places')).json(); } catch(e){ list=[{id:'jungs',title:"Jungs' Room"}]; }
  const tabs=document.getElementById('tabs');
  tabs.innerHTML='';
  list.forEach(p=>{ const b=document.createElement('div'); b.className='tab'; b.dataset.place=p.id;
    b.textContent=p.title+(p.agents?` (${p.agents})`:''); b.onclick=()=>switchPlace(p.id); tabs.appendChild(b); });
  await switchPlace(list[0].id);
}

async function sendWhisper(){
  const inp=document.getElementById('wInput'), text=inp.value.trim(); if(!text||!currentPlace) return; inp.value='';
  try { const r=await (await fetch('/whisper?place='+currentPlace+AUTH,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text})})).json();
    document.getElementById('hint').textContent=(r.ok?'🤫 ':'⏳ ')+r.message; } catch(e){ document.getElementById('hint').textContent='Failed to send'; }
}
document.getElementById('wSend').onclick=sendWhisper;
document.getElementById('wInput').addEventListener('keydown',e=>{ if(e.key==='Enter') sendWhisper(); });


// === Room Edit Mode (개선된 UX) ===
let currentRoomConfig = null;
let hasUnsavedChanges = false;

function markUnsaved() {
  hasUnsavedChanges = true;
  const btn = document.getElementById('saveRoomBtn');
  if (btn) btn.disabled = false;
}

function openRoomModal() {
  if (currentPlace === 'town') return;
  const modal = document.getElementById('roomModal');
  modal.style.display = 'flex';
  hasUnsavedChanges = false;
  loadRoomConfigForEdit();
}

function closeRoomModal() {
  if (hasUnsavedChanges) {
    if (!confirm('You have unsaved changes. Close anyway?')) {
      return;
    }
  }
  const modal = document.getElementById('roomModal');
  modal.style.display = 'none';
  hasUnsavedChanges = false;
}

async function loadRoomConfigForEdit() {
  try {
    const res = await fetch('/room/config?room=' + encodeURIComponent(currentPlace));
    currentRoomConfig = await res.json();
    document.getElementById('modalTitle').textContent = '⚙️ Edit ' + (currentRoomConfig.title || 'Room');
    renderRoomAgents();

    const btn = document.getElementById('saveRoomBtn');
    if (btn) btn.disabled = true;
  } catch(e) {
    document.getElementById('roomSaveMsg').textContent = 'Failed to load settings.';
  }
}

function renderRoomAgents() {
  const container = document.getElementById('roomAgentsList');
  container.innerHTML = '';
  if (!currentRoomConfig || !currentRoomConfig.agents) return;

  const agents = currentRoomConfig.agents || [];
  
  agents.forEach((agent, idx) => {
    const card = document.createElement('div');
    card.style.cssText = `
      background: white; 
      border: 1px solid #d4c9a8; 
      border-radius: 12px; 
      padding: 14px 16px; 
      margin-bottom: 10px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
      transition: all 0.2s ease;
    `;
    card.onmouseenter = () => card.style.boxShadow = '0 4px 12px rgba(0,0,0,0.08)';
    card.onmouseleave = () => card.style.boxShadow = '0 1px 3px rgba(0,0,0,0.05)';
    
    card.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px;">
        <div style="flex:1; min-width:0;">
          <div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">
            <strong style="font-size:15px;">${agent.name}</strong>
            <span style="font-size:11px; color:#8a8170; background:#f5eedd; padding:1px 6px; border-radius:4px;">${agent.id}</span>
            ${agent.is_mine ? '<span style="font-size:10px; background:#e0742f; color:white; padding:1px 6px; border-radius:4px;">OWNER</span>' : ''}
          </div>
          <div style="font-size:12.5px; color:#5c5240; line-height:1.4; white-space:pre-wrap;">${agent.persona_prompt}</div>
        </div>
        <div style="display:flex; flex-direction:column; gap:6px; flex-shrink:0;">
          <button data-idx="${idx}" class="editAgentBtn" style="font-size:12px; padding:5px 10px; border-radius:6px; border:1px solid #c9b78a; background:#f8f1df; cursor:pointer;">Edit</button>
          <button data-idx="${idx}" class="delAgentBtn" style="font-size:12px; padding:5px 10px; border-radius:6px; border:1px solid #c9b78a; background:#f8f1df; cursor:pointer;">Delete</button>
        </div>
      </div>
    `;
    container.appendChild(card);
  });

  // 이벤트 바인딩
  container.querySelectorAll('.editAgentBtn').forEach(btn => {
    btn.onclick = () => editAgent(parseInt(btn.dataset.idx));
  });
  container.querySelectorAll('.delAgentBtn').forEach(btn => {
    btn.onclick = () => deleteAgent(parseInt(btn.dataset.idx));
  });
}

function editAgent(idx) {
  const agent = currentRoomConfig.agents[idx];

  const newName = prompt('Name:', agent.name);
  if (newName === null) return;

  const newPersona = prompt('Persona (personality description):', agent.persona_prompt);
  if (newPersona === null) return;

  const isMine = confirm('Make this agent the room owner?');

  agent.name = newName;
  agent.persona_prompt = newPersona;

  if (isMine) {
    currentRoomConfig.agents.forEach(a => a.is_mine = false);
    agent.is_mine = true;
  }

  markUnsaved();
  renderRoomAgents();
}

function deleteAgent(idx) {
  if (!confirm('Delete this agent?')) return;
  currentRoomConfig.agents.splice(idx, 1);
  markUnsaved();
  renderRoomAgents();
}

function addAgent() {
  const id = prompt('Agent ID (lowercase letters):');
  if (!id) return;

  const name = prompt('Name:');
  if (!name) return;

  const persona = prompt('Persona (personality description):', 'A new character.');
  if (persona === null) return;

  currentRoomConfig.agents.push({
    id: id,
    name: name,
    persona_prompt: persona,
    is_mine: false,
    canned_lines: []
  });

  markUnsaved();
  renderRoomAgents();
}

async function saveRoomConfig() {
  const msg = document.getElementById('roomSaveMsg');
  msg.textContent = 'Saving...';

  try {
    const res = await fetch('/room/config?room=' + encodeURIComponent(currentPlace), {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(currentRoomConfig)
    });
    const result = await res.json();

    if (result.ok) {
      msg.textContent = 'Saved!';
      hasUnsavedChanges = false;
      const btn = document.getElementById('saveRoomBtn');
      if (btn) btn.disabled = true;
      setTimeout(closeRoomModal, 1000);
    } else {
      msg.textContent = result.message || 'Save failed';
    }
  } catch(e) {
    msg.textContent = 'Server error';
  }
}

// 이벤트 연결 (요소가 없어도 전체 초기화가 죽지 않게 null-safe)
for (const [id, fn] of [['roomEditBtn', openRoomModal], ['closeModalBtn', closeRoomModal], ['addAgentBtn', addAgent], ['saveRoomBtn', saveRoomConfig]]) {
  const el = document.getElementById(id);
  if (el) el.onclick = fn;
}

resize(); animate(); buildTabs(); setInterval(poll, 1000);
</script>
</body></html>"""
