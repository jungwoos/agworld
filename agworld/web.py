"""웹뷰 서버 — stdlib http.server만으로 3D(Three.js) 관전 화면을 브라우저에 띄운다.

    ┌── 브라우저 ─────────────────┐         ┌── WorldServer (이 파일) ──┐
    │  Three.js 3D 씬 + JS        │  GET /   │  PAGE(HTML) 서빙           │
    │  1초마다 폴링 ──────────────┼─ /state ─▶  world_state_dict() (JSON)│
    │  귓속말 입력 ───────────────┼─/whisper─▶  submit_whisper()         │
    └─────────────────────────────┘   POST   │  ticker 스레드: interval  │
                                              │   마다 world.step()        │
                                              └────────────────────────────┘

백엔드는 의존성 0(stdlib만). 3D 렌더링은 브라우저가 CDN에서 Three.js를 불러와 처리한다
(빌드 스텝 없음, 볼 때 인터넷 필요). 카메라는 아이소메트릭(Orthographic), OrbitControls로 회전 가능.

슬립 온 디스커넥트: 브라우저 폴링이 idle_timeout 동안 없으면 watching=False → step() no-op.
World는 스레드 안전이 아니라 모든 접근을 Lock으로 감싼다.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .room import room_dict
from .sim import World
from .webstate import submit_whisper, world_state_dict


def make_handler(world: World, lock: threading.Lock, shared: dict):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # 콘솔 스팸 억제
            pass

        def _send_json(self, obj, code=200):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/" or self.path.startswith("/index"):
                body = PAGE.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path.startswith("/state"):
                shared["last_poll"] = time.monotonic()  # 폴링 = 관전 중
                with lock:
                    self._send_json(world_state_dict(world))
            elif self.path.startswith("/room"):
                self._send_json(room_dict())  # 마이룸 가구 레이아웃(정적, 1회 로드)
            else:
                self._send_json({"error": "not found"}, 404)

        def do_POST(self):
            if self.path.startswith("/whisper"):
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b"{}"
                try:
                    payload = json.loads(raw.decode("utf-8") or "{}")
                except json.JSONDecodeError:
                    payload = {}
                shared["last_poll"] = time.monotonic()
                with lock:
                    result = submit_whisper(world, str(payload.get("text", "")))
                self._send_json(result)
            else:
                self._send_json({"error": "not found"}, 404)

    return Handler


def start_ticker(world: World, lock: threading.Lock, shared: dict,
                 interval: float, idle_timeout: float, stop: threading.Event):
    """interval마다 한 틱. 단, 최근 idle_timeout 내 폴링이 있어야(관전 중) 진행."""
    def loop():
        while not stop.is_set():
            stop.wait(interval)
            if stop.is_set():
                break
            now = time.monotonic()
            watching = (now - shared["last_poll"]) <= idle_timeout
            with lock:
                world.set_watching(watching)
                world.step()  # 자는 중이면 내부에서 no-op
    th = threading.Thread(target=loop, daemon=True)
    th.start()
    return th


def serve(world: World, host: str = "127.0.0.1", port: int = 8765,
          interval: float = 10.0, idle_timeout: float | None = None) -> None:
    """블로킹 서버 실행. Ctrl-C로 종료."""
    if idle_timeout is None:
        idle_timeout = max(interval * 2, 5.0)
    lock = threading.Lock()
    shared = {"last_poll": time.monotonic()}
    stop = threading.Event()

    # 먼저 바인딩(여기서 실패하면 포트 충돌). 성공 후에야 ticker 시작.
    try:
        httpd = ThreadingHTTPServer((host, port), make_handler(world, lock, shared))
    except OSError as e:
        print(f"❌ 포트 {port} 바인딩 실패: {e}", flush=True)
        print(f"   → 다른 포트로: python3 -m agworld --web --port {port + 1}", flush=True)
        return

    start_ticker(world, lock, shared, interval, idle_timeout, stop)
    url = f"http://{host}:{port}/"
    # flush=True 필수 — 안 하면 stdout 버퍼링으로 URL이 안 보여 '멈춘 것처럼' 느껴짐.
    print(f"✅ AG-World 3D 웹뷰 실행 중 → 브라우저에서 열기: {url}", flush=True)
    print(f"   (틱 {interval:.0f}초 · 마우스 드래그로 방 회전 · Ctrl-C 종료)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n종료 — 세계가 잠듭니다 💤", flush=True)
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
  .title { font-size:12px; color:#8a8170; letter-spacing:.6px; margin-bottom:10px; display:flex; justify-content:space-between; }
  .layout { display:grid; grid-template-columns:1fr 300px; gap:16px; }
  @media(max-width:780px){ .layout{ grid-template-columns:1fr; } }
  .stage { position:relative; background:linear-gradient(180deg,#f5eedd,#e2d3b6); border:1px solid #cdc0a2; border-radius:16px; height:470px; overflow:hidden; }
  #scene { width:100%; height:100%; display:block; }
  #loading { position:absolute; inset:0; display:flex; align-items:center; justify-content:center; color:#9a8f76; font-size:13px; text-align:center; padding:20px; }
  .rail { background:#fffdf7; border:1px solid #e2d9c2; border-radius:16px; padding:14px; display:flex; flex-direction:column; height:470px; }
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
  "three": "https://unpkg.com/three@0.160.0/build/three.module.js",
  "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"
}}
</script>
</head>
<body>
<div class="frame">
  <div class="title"><span>AG-WORLD · 3D 관전 (Three.js · 드래그로 회전)</span><span id="status">연결 중...</span></div>
  <div class="layout">
    <div class="stage"><canvas id="scene"></canvas><div id="loading">3D 씬 로딩 중... (Three.js CDN — 인터넷 필요)</div></div>
    <div class="rail">
      <h3>💬 대화 (말은 여기서 읽음)</h3>
      <div class="feed" id="feed"></div>
    </div>
  </div>
  <div class="whisper">
    <span class="lab">🤫 <span id="whomLabel">내 에이전트</span>에게 속삭이기</span>
    <input id="wInput" placeholder="예: 루리한테 너무 몰아세우지 말라고 해줘" autocomplete="off">
    <button id="wSend">속삭임</button>
  </div>
  <div class="hint" id="hint">속삭임은 명령이 아니라 힌트 — 내 에이전트가 제 성격대로 소화합니다</div>
</div>

<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const PALETTE = [0x6fa8a0,0xb08a6f,0xe0a36f,0x8f9bd0,0xc08fb0,0xa0b07a];
const ACCENT = 0xe0742f;
const ROOM = 8;        // 바닥 한 변(월드 단위)
const RADIUS = 2.4;    // 아바타 배치 반경

const cv = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf2e9d6);

// 아이소메트릭: 직교 카메라를 45도/위에서.
let camera;
function makeCamera(){
  const r = cv.getBoundingClientRect(), aspect = r.width/Math.max(1,r.height), F = 5.5;
  camera = new THREE.OrthographicCamera(-F*aspect, F*aspect, F, -F, 0.1, 100);
  camera.position.set(9, 8, 9);
  camera.lookAt(0, 1, 0);
}
makeCamera();

const controls = new OrbitControls(camera, renderer.domElement);
controls.enablePan = false;
controls.minPolarAngle = 0.3; controls.maxPolarAngle = 1.35;
controls.target.set(0, 1, 0);

// 조명
scene.add(new THREE.AmbientLight(0xffffff, 0.75));
const dir = new THREE.DirectionalLight(0xfff2dd, 0.9);
dir.position.set(6, 12, 4); scene.add(dir);

// 방: 바닥 + 뒷벽 2면
const floor = new THREE.Mesh(
  new THREE.BoxGeometry(ROOM, 0.3, ROOM),
  new THREE.MeshStandardMaterial({ color: 0xd9c8a2 })
);
floor.position.y = -0.15; scene.add(floor);
const grid = new THREE.GridHelper(ROOM, ROOM, 0xb09a6a, 0xcbbb95);  // 타일 라인
grid.position.y = 0.011; scene.add(grid);
function wall(w, h, x, z, ry, color){
  const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h),
    new THREE.MeshStandardMaterial({ color, side: THREE.DoubleSide }));
  m.position.set(x, h/2, z); m.rotation.y = ry; scene.add(m);
}
wall(ROOM, 4, 0, -ROOM/2, 0, 0xe7dabf);          // 뒷벽
wall(ROOM, 4, -ROOM/2, 0, Math.PI/2, 0xdccba3);   // 옆벽

// ===== 가구 카탈로그 (마이룸) — Three.js 프리미티브로 조립 =====
// 카탈로그 패턴: name -> 빌더(Group 반환). 나중에 스토어가 새 아이템을 여기 추가하면 끝.
function fmat(c){ return new THREE.MeshStandardMaterial({ color: new THREE.Color(c), roughness:0.85 }); }
function fbox(w,h,d,c){ return new THREE.Mesh(new THREE.BoxGeometry(w,h,d), fmat(c)); }
function fcyl(rt,rb,h,c){ return new THREE.Mesh(new THREE.CylinderGeometry(rt,rb,h,16), fmat(c)); }
const FURNITURE = {
  rug(o){ const g=new THREE.Group(); const r=fbox(2.0,0.04,1.4,o.color||'#c98f5a'); r.position.y=0.02; g.add(r); return g; },
  sofa(o){ const c=o.color||'#7a8a6f', g=new THREE.Group();
    const b=fbox(2.0,0.4,0.9,c); b.position.y=0.3; g.add(b);
    const bk=fbox(2.0,0.6,0.2,c); bk.position.set(0,0.7,-0.35); g.add(bk);
    [-1.0,1.0].forEach(x=>{ const a=fbox(0.2,0.55,0.9,c); a.position.set(x,0.5,0); g.add(a); }); return g; },
  table(o){ const c=o.color||'#9a7a55', g=new THREE.Group();
    const t=fbox(1.2,0.12,0.8,c); t.position.y=0.7; g.add(t);
    [[-0.5,-0.3],[0.5,-0.3],[-0.5,0.3],[0.5,0.3]].forEach(([x,z])=>{ const l=fbox(0.1,0.7,0.1,c); l.position.set(x,0.35,z); g.add(l); }); return g; },
  chair(o){ const c=o.color||'#8a6f4f', g=new THREE.Group();
    const s=fbox(0.5,0.1,0.5,c); s.position.y=0.45; g.add(s);
    const b=fbox(0.5,0.5,0.1,c); b.position.set(0,0.7,-0.2); g.add(b);
    [[-0.2,-0.2],[0.2,-0.2],[-0.2,0.2],[0.2,0.2]].forEach(([x,z])=>{ const l=fbox(0.08,0.45,0.08,c); l.position.set(x,0.22,z); g.add(l); }); return g; },
  bookshelf(o){ const c=o.color||'#8a6f4f', g=new THREE.Group();
    const fr=fbox(1.4,2.0,0.4,c); fr.position.y=1.0; g.add(fr);
    const cols=['#c0573f','#3f6cc0','#d8a93f','#5aa05a','#b06fb0'];
    for(let s=0;s<3;s++) for(let k=0;k<5;k++){ const bk=fbox(0.12,0.5,0.3,cols[(s*5+k)%cols.length]);
      bk.position.set(-0.5+k*0.25, 0.55+s*0.6, 0.06); g.add(bk); } return g; },
  plant(o){ const g=new THREE.Group(); const pot=fcyl(0.22,0.28,0.4,'#b5764a'); pot.position.y=0.2; g.add(pot);
    const f1=new THREE.Mesh(new THREE.SphereGeometry(0.35,12,10), fmat('#5a8a4a')); f1.position.y=0.7; g.add(f1);
    const f2=new THREE.Mesh(new THREE.SphereGeometry(0.25,12,10), fmat('#6fa05a')); f2.position.set(0.18,0.92,0.05); g.add(f2); return g; },
  lamp(o){ const g=new THREE.Group(); const base=fcyl(0.18,0.22,0.08,'#444'); base.position.y=0.04; g.add(base);
    const pole=fcyl(0.04,0.04,1.4,'#666'); pole.position.y=0.74; g.add(pole);
    const shade=new THREE.Mesh(new THREE.ConeGeometry(0.32,0.4,16,1,true),
      new THREE.MeshStandardMaterial({color:0xf5e6b0,emissive:0xffe9a0,emissiveIntensity:0.6,side:THREE.DoubleSide}));
    shade.position.y=1.5; g.add(shade); const lp=new THREE.PointLight(0xffe9b0,0.6,6); lp.position.y=1.4; g.add(lp); return g; },
  picture(o){ const g=new THREE.Group(); g.add(fbox(1.0,0.7,0.06,'#5a4a35')); g.add(fbox(0.85,0.55,0.07,o.color||'#9ab0c8')); g.position.y=2.2; return g; },
  window(o){ const g=new THREE.Group(); g.add(fbox(0.1,1.4,1.6,'#6a5a45')); g.add(fbox(0.05,1.2,1.4,'#add3e6')); g.position.y=2.0; return g; },
};
async function loadRoom(){
  let data; try { data = await (await fetch('/room')).json(); } catch(e){ return; }
  (data.items||[]).forEach(it=>{
    const build = FURNITURE[it.item]; if(!build) return;
    const g = build(it);
    g.position.x += (it.x||0); g.position.z += (it.z||0);
    if(it.ry) g.rotation.y = it.ry * Math.PI/180;
    if(it.scale) g.scale.multiplyScalar(it.scale);
    scene.add(g);
  });
}

// 텍스트/이모지 → 스프라이트
function sprite(text, px, color){
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d');
  g.font = px + 'px -apple-system,"Apple Color Emoji","Apple SD Gothic Neo",sans-serif';
  g.textAlign = 'center'; g.textBaseline = 'middle';
  if(color){ g.fillStyle = color; }
  g.fillText(text, 64, 70);
  const tex = new THREE.CanvasTexture(c); tex.needsUpdate = true;
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true }));
  return sp;
}

// 아바타 관리
const avatars = {};   // id -> {group, body, emo, ring, pulse, isMine, emoji}
function placeCell(i, n){
  if(n === 1) return [0, 0];
  const ang = -Math.PI/2 + i*(2*Math.PI/n);
  return [RADIUS*Math.cos(ang), RADIUS*Math.sin(ang)];
}
function makeAvatar(a, i, n, idx){
  const group = new THREE.Group();
  const [x, z] = placeCell(i, n);
  group.position.set(x, 0, z);

  const body = new THREE.Mesh(
    new THREE.CapsuleGeometry(0.32, 0.7, 4, 12),
    new THREE.MeshStandardMaterial({ color: PALETTE[idx % PALETTE.length] })
  );
  body.position.y = 0.75; group.add(body);

  const emo = sprite(a.emoji, 92);
  emo.scale.set(0.9, 0.9, 0.9); emo.position.y = 2.0; group.add(emo);

  const nm = sprite(a.name + (a.is_mine ? ' ★' : ''), 30, a.is_mine ? '#c4621f' : '#5a5444');
  nm.scale.set(1.6, 0.8, 1); nm.position.y = -0.05; group.add(nm);

  let ring = null, pulse = null;
  if(a.is_mine){
    ring = new THREE.Mesh(new THREE.TorusGeometry(0.55, 0.05, 8, 32),
      new THREE.MeshStandardMaterial({ color: ACCENT }));
    ring.rotation.x = Math.PI/2; ring.position.y = 0.02; group.add(ring);
  }
  pulse = new THREE.Mesh(new THREE.RingGeometry(0.5, 0.62, 32),
    new THREE.MeshBasicMaterial({ color: ACCENT, transparent: true, opacity: 0, side: THREE.DoubleSide }));
  pulse.rotation.x = -Math.PI/2; pulse.position.y = 0.03; group.add(pulse);

  scene.add(group);
  avatars[a.id] = { group, body, emo, ring, pulse, isMine: a.is_mine, emoji: a.emoji, speaking: a.speaking };
}
function updateAvatar(a){
  const av = avatars[a.id];
  if(av.emoji !== a.emoji){ av.emo.material.map.dispose(); av.emo.material = sprite(a.emoji, 92).material; av.emoji = a.emoji; }
  av.speaking = a.speaking;
}

let STATE = null, ready = false;
function syncScene(){
  if(!STATE) return;
  const n = STATE.agents.length;
  STATE.agents.forEach((a, i) => {
    if(avatars[a.id]) updateAvatar(a);
    else makeAvatar(a, i, n, i);
  });
}

const clock = new THREE.Clock();
function animate(){
  requestAnimationFrame(animate);
  const t = clock.getElapsedTime();
  const watching = STATE ? STATE.watching : true;
  for(const id in avatars){
    const av = avatars[id];
    // 발화중 펄스
    if(av.speaking && watching){
      const ph = (t % 1.2) / 1.2;
      av.pulse.scale.setScalar(1 + ph*1.8);
      av.pulse.material.opacity = 0.5 * (1 - ph);
    } else { av.pulse.material.opacity = 0; }
    // 살짝 떠다니는 바디(생동감)
    av.body.position.y = 0.75 + (watching ? Math.sin(t*1.5 + av.group.position.x)*0.04 : 0);
  }
  renderer.toneMappingExposure = watching ? 1 : 0.7;
  controls.update();
  renderer.render(scene, camera);
}

function resize(){
  const r = cv.getBoundingClientRect();
  renderer.setSize(r.width, r.height, false);
  makeCamera();
  controls.object = camera;
}
window.addEventListener('resize', resize);

function esc(s){ const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

async function poll(){
  let s;
  try { s = await (await fetch('/state')).json(); }
  catch(e){ document.getElementById('status').textContent = '서버 연결 끊김'; return; }
  STATE = s;
  if(!ready){ ready = true; document.getElementById('loading').style.display = 'none'; }
  document.getElementById('status').textContent =
    (s.watching ? '관전 중' : '자는 중 💤') + ` · 틱 ${s.t} · $${s.cost}`;
  if(s.my_agent) document.getElementById('whomLabel').textContent = s.my_agent.name;
  syncScene();
  // 피드
  const feed = document.getElementById('feed');
  let html = '', lastT = null;
  if(s.feed.length === 0) html = '<div class="tk">(아직 조용하다...)</div>';
  s.feed.forEach(f => {
    if(f.t !== lastT){ html += `<div class="tk">— 틱 ${f.t}${f.decisive ? ' ⚡' : ''} —</div>`; lastT = f.t; }
    html += `<div class="line${f.is_mine ? ' me' : ''}${f.decisive ? ' moment' : ''}">` +
            `<span class="sp">${esc(f.name)}:</span> ${esc(f.text)} ${f.emoji}</div>`;
  });
  feed.innerHTML = html; feed.scrollTop = feed.scrollHeight;
}

async function sendWhisper(){
  const inp = document.getElementById('wInput'), text = inp.value.trim();
  if(!text) return; inp.value = '';
  try {
    const r = await (await fetch('/whisper', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ text }) })).json();
    document.getElementById('hint').textContent = (r.ok ? '🤫 ' : '⏳ ') + r.message;
  } catch(e){ document.getElementById('hint').textContent = '전송 실패'; }
}
document.getElementById('wSend').onclick = sendWhisper;
document.getElementById('wInput').addEventListener('keydown', e => { if(e.key === 'Enter') sendWhisper(); });

resize();
animate();
loadRoom();   // 마이룸 가구 1회 로드
poll();
setInterval(poll, 1000);
</script>
</body></html>"""
