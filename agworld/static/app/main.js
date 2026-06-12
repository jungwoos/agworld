// 부트스트랩 + UI 글루 — 탭/폴링/피드/귓속말/집 탭 내비게이션/렌더 루프.

import * as THREE from 'three';
import { animateAvatars, avatars, clearAvatars, makeAvatar, updateAvatar } from './avatars.js';
import { enterEdit, isEditing } from './editor.js';
import { api, ME } from './net.js';
import { buildFurniture, buildShell, camera, controls, cv, houses, renderer, resize, scene, setRoom } from './scene3d.js';

const $ = id => document.getElementById(id);

let STATE = null, currentPlace = null, currentItems = [], ready = false;
let elapsed = 0;
const clock = new THREE.Clock();

function esc(s){ const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

// ── 방 로드 ──
async function loadRoom(place){
  let data; try { data = await api.room(place); } catch(e){ return; }
  currentItems = data.items || [];
  setRoom(data.room_size || 8, data.scene || 'indoor');
  buildShell(data.room_size || 8, data.scene || 'indoor');
  buildFurniture(currentItems);
}

// ── 보는 사람 UI: 내 에이전트면 속삭임 활성, 아니면 관전 모드로 잠금 ──
let _lastViewer = '__init__';
function applyViewerUI(my){
  const cur = my ? my.id : null;
  if(cur === _lastViewer) return; _lastViewer = cur;
  const lab = $('wLab'), wIn = $('wInput'), wBtn = $('wSend');
  if(my){
    lab.innerHTML = '🤫 Whisper to <span id="whomLabel">' + esc(my.name) + '</span>';
    wIn.disabled = false; wBtn.disabled = false;
    wIn.placeholder = 'e.g. Tell Jayy to go easy on Dan';
  } else {
    lab.textContent = '👀 Spectator mode';
    wIn.disabled = true; wIn.placeholder = 'Open your agent invite link (?me=…&key=…) to whisper';
    wBtn.disabled = true;
  }
}

// ── 폴링 ──
async function poll(){
  if(!currentPlace) return;
  let s; try { s = await api.state(currentPlace); }
  catch(e){ $('status').textContent = 'Disconnected'; return; }
  STATE = s;
  if(!ready){ ready = true; $('loading').style.display = 'none'; }
  $('status').textContent = (s.watching ? 'Watching' : 'Sleeping 💤') + ` · tick ${s.t} · $${s.cost}`;
  applyViewerUI(s.my_agent);
  const n = s.agents.length;
  s.agents.forEach((a, i) => { if(avatars[a.id]) updateAvatar(a, elapsed); else makeAvatar(a, i, n, i, elapsed); });
  const feed = $('feed'); let html = '', lastT = null;
  if(s.feed.length === 0) html = '<div class="tk">(quiet so far...)</div>';
  s.feed.forEach(f => {
    if(f.t !== lastT){ html += `<div class="tk">— tick ${f.t}${f.decisive ? ' ⚡' : ''} —</div>`; lastT = f.t; }
    html += `<div class="line${f.is_mine ? ' me' : ''}${f.decisive ? ' moment' : ''}"><span class="sp">${esc(f.name)}:</span> ${esc(f.text)} ${f.emoji}</div>`;
  });
  feed.innerHTML = html; feed.scrollTop = feed.scrollHeight;
}

// ── 장소 전환 + 탭 ──
async function switchPlace(pid){
  if(pid === currentPlace || isEditing()) return;   // 편집 중 장소 전환 금지
  currentPlace = pid; STATE = null;
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.place === pid));
  // 가구 편집은 내 방에서만 (방 id == 주인 에이전트 id)
  $('editBtn').style.display = (pid === ME && !isEditing()) ? '' : 'none';
  clearPath(); clearAvatars();
  await loadRoom(pid);
  poll();
}

async function buildTabs(){
  let list; try { list = await api.places(); } catch(e){ list = [{ id: 'jungs', title: "Jungs' Room" }]; }
  const tabs = $('tabs');
  tabs.innerHTML = '';
  list.forEach(p => { const b = document.createElement('div'); b.className = 'tab'; b.dataset.place = p.id;
    b.textContent = p.title + (p.agents ? ` (${p.agents})` : ''); b.onclick = () => switchPlace(p.id); tabs.appendChild(b); });
  await switchPlace(list[0].id);
}

// ── 귓속말 ──
async function sendWhisper(){
  const inp = $('wInput'), text = inp.value.trim(); if(!text || !currentPlace) return; inp.value = '';
  try { const r = await api.whisper(currentPlace, text);
    $('hint').textContent = (r.ok ? '🤫 ' : '⏳ ') + r.message; } catch(e){ $('hint').textContent = 'Failed to send'; }
}
$('wSend').onclick = sendWhisper;
$('wInput').addEventListener('keydown', e => { if(e.key === 'Enter') sendWhisper(); });

// ── 가구 편집 모드 ──
$('editBtn').onclick = () => {
  if(currentPlace !== ME) return;
  $('editBtn').style.display = 'none';
  enterEdit(currentPlace, currentItems, async () => {   // 종료 시(저장/취소 공통) 방 다시 로드
    await loadRoom(currentPlace);
    $('editBtn').style.display = (currentPlace === ME) ? '' : 'none';
  });
};

// ── 집 탭 내비게이션: 경로 하이라이트 + 경로 따라 걷기 ──
let pathGroup = null;
function clearPath(){ if(pathGroup){ scene.remove(pathGroup); pathGroup = null; } }
function buildPathDots(wps){
  clearPath(); pathGroup = new THREE.Group();
  for(let s = 0; s < wps.length - 1; s++){
    const a = wps[s], b = wps[s+1], d = Math.hypot(b.x - a.x, b.z - a.z), n = Math.max(2, Math.round(d / 0.7));
    for(let k = 0; k <= n; k++){ const t = k / n;
      const dot = new THREE.Mesh(new THREE.CircleGeometry(0.14, 12),
        new THREE.MeshBasicMaterial({ color: 0xe0742f, transparent: true, opacity: 0.85 }));
      dot.rotation.x = -Math.PI / 2; dot.position.set(a.x + (b.x - a.x) * t, 0.05, a.z + (b.z - a.z) * t);
      dot.userData.ph = t * 4;   // 펄스 위상(흐르는 느낌)
      pathGroup.add(dot); }
  }
  scene.add(pathGroup);
}
// start→target 직선이 분수(중앙 r≈2.6)를 지나면 우회 경유점을 끼운다
function routeAround(start, target){
  const wps = [start];
  const dx = target.x - start.x, dz = target.z - start.z, len = Math.hypot(dx, dz);
  if(len > 0.01){
    const t = Math.max(0, Math.min(1, -(start.x * dx + start.z * dz) / (len * len)));
    const cx = start.x + dx * t, cz = start.z + dz * t;
    if(Math.hypot(cx, cz) < 2.6){
      const ma = Math.atan2((start.z + target.z) / 2, (start.x + target.x) / 2);
      wps.push({ x: Math.cos(ma) * 3.6, z: Math.sin(ma) * 3.6 });
    }
  }
  wps.push(target);
  return wps;
}
function navigateToHouse(h){
  // 집 정면(광장 쪽)으로 2.6만큼 떨어진 접근점
  const dl = Math.hypot(h.x, h.z) || 1, door = { x: h.x - h.x / dl * 2.6, z: h.z - h.z / dl * 2.6 };
  const mover = avatars[ME];
  const start = mover ? { x: mover.group.position.x, z: mover.group.position.z } : { x: 0, z: 2.4 };
  const wps = routeAround(start, door);
  buildPathDots(wps);
  if(mover){
    mover.path = wps.slice(1);   // 첫 점은 현재 위치
    mover.onArrive = () => { clearPath(); switchPlace(h.place); };
  } else {
    setTimeout(() => { clearPath(); switchPlace(h.place); }, 1400);
  }
}
// 탭 감지: 드래그(OrbitControls)와 구분 — 이동 6px 미만 + 400ms 미만일 때만
const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
let downX = 0, downY = 0, downT = 0;
cv.addEventListener('pointerdown', e => { downX = e.clientX; downY = e.clientY; downT = performance.now(); });
cv.addEventListener('pointerup', e => {
  if(isEditing()) return;   // 편집 모드에선 editor가 포인터를 소유
  if(Math.hypot(e.clientX - downX, e.clientY - downY) > 6 || performance.now() - downT > 400) return;
  if(!houses.length) return;
  const r = cv.getBoundingClientRect();
  ndc.x = ((e.clientX - r.left) / r.width) * 2 - 1; ndc.y = -((e.clientY - r.top) / r.height) * 2 + 1;
  ray.setFromCamera(ndc, camera);
  const hits = ray.intersectObjects(houses.map(h => h.group), true);
  if(!hits.length) return;
  let obj = hits[0].object; while(obj && !obj.userData.place) obj = obj.parent;
  if(!obj) return;
  const h = houses.find(x => x.place === obj.userData.place);
  if(h) navigateToHouse(h);
});

// ── 렌더 루프 ──
function animate(){
  requestAnimationFrame(animate);
  const dt = Math.min(clock.getDelta(), 0.05); elapsed += dt;
  const watching = STATE ? STATE.watching : true;
  if(pathGroup){ pathGroup.children.forEach(d => { d.material.opacity = 0.45 + 0.4 * Math.sin(elapsed * 5 - d.userData.ph); }); }
  animateAvatars(dt, elapsed, watching, isEditing());   // 편집 중엔 아바타 숨김
  renderer.toneMappingExposure = watching ? 1 : 0.7;
  controls.update();
  renderer.render(scene, camera);
}

resize(); animate(); buildTabs(); setInterval(poll, 1000);
