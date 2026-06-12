// 가구 편집 모드 — 내 방에서만.
//
// UX: 하단 팔레트 칩을 탭해 추가(빈 자리 자동 배치 + 자동 선택), 가구를 탭해 선택,
// 드래그로 이동(0.25 그리드 스냅), 선택 시 플로팅 패널(회전/크기/복제/색상/삭제),
// Undo 히스토리, ✓ Done = 저장+종료, ✕ = 변경 취소.
//
// 동작 원리: items(작업 사본)가 진실이고, 변경마다 buildFurniture(items)로 씬을 다시 짓는다.
// 드래그만 예외 — 매 프레임 재빌드는 비싸서 선택된 그룹의 position을 직접 옮기고 item에 반영.

import * as THREE from 'three';
import { api } from './net.js';
import { ACCENT, buildFurniture, camera, controls, cv, furnitureGroup, roomSize, scene } from './scene3d.js';

// 편집기에서 추가할 수 있는 실내 가구 (서버 INDOOR_CATALOG와 동일) + 팔레트 아이콘
const PALETTE_DEF = [
  ['sofa', '🛋', 'sofa'], ['chair', '🪑', 'chair'], ['table', '🪵', 'table'],
  ['bookshelf', '📚', 'shelf'], ['rug', '🟫', 'rug'], ['plant', '🪴', 'plant'],
  ['lamp', '💡', 'lamp'], ['picture', '🖼', 'picture'], ['window', '🪟', 'window'],
];
const COLORS = ['#c98f5a', '#7a8a6f', '#7a93b5', '#8a6f8a', '#d8a93f', '#c0573f', '#5aa05a', '#4a4a4a'];
const SNAP = 0.25;

const els = {};
['editBtn','editTop','editHint','undoBtn','doneBtn','discardBtn','selPanel','swatches','palette',
 'rotBtn','scaleDn','scaleUp','dupBtn','colorBtn','delBtn','hint']
  .forEach(id => els[id] = document.getElementById(id));

let active = false;
let items = [];          // 작업 사본
let selected = -1;       // items 인덱스
let room = '';           // 편집 중인 방 id
let onExit = null;       // 종료 콜백(메인이 방 다시 로드)
let history = [];        // Undo 스냅샷
let dirty = false;

// 선택 표시 링
const selRing = new THREE.Mesh(new THREE.TorusGeometry(0.8, 0.05, 8, 36),
  new THREE.MeshBasicMaterial({ color: ACCENT }));
selRing.rotation.x = Math.PI / 2; selRing.position.y = 0.04; selRing.visible = false;
scene.add(selRing);

export function isEditing(){ return active; }

// ── 히스토리 ──
function snapshot(){
  history.push(JSON.stringify(items));
  if(history.length > 60) history.shift();
  dirty = true;
  els.undoBtn.disabled = false;
}
function undo(){
  if(!history.length) return;
  items = JSON.parse(history.pop());
  if(selected >= items.length) selected = -1;
  rebuild();
  els.undoBtn.disabled = !history.length;
}

// ── 표시 동기화 ──
function hint(text){ els.editHint.textContent = text; }

function syncSelection(){
  const has = selected >= 0;
  els.selPanel.style.display = has ? 'flex' : 'none';
  if(!has) els.swatches.style.display = 'none';
  selRing.visible = active && has;
  if(has){
    const it = items[selected];
    selRing.position.x = it.x || 0; selRing.position.z = it.z || 0;
    selRing.scale.setScalar(Math.max(0.7, it.scale || 1));
    // 선택된 가구를 살짝 발광시켜 강조
    const g = groupOf(selected);
    if(g) g.traverse(m => { if(m.isMesh && m.material.emissive) m.material.emissive.setHex(0x5a2d08); });
    hint('Drag to move · tools below');
  } else {
    hint('Tap a chip below to add · tap furniture to select');
  }
}

function groupOf(idx){ return furnitureGroup.children.find(c => c.userData.itemIndex === idx); }
function rebuild(){ buildFurniture(items); syncSelection(); }
function select(idx){ selected = idx; rebuild(); }

// ── 진입/종료 ──
export function enterEdit(place, currentItems, exitCb){
  active = true; room = place; onExit = exitCb;
  items = currentItems.map(it => ({ ...it }));
  selected = -1; history = []; dirty = false;
  els.undoBtn.disabled = true;
  els.editTop.style.display = 'flex';
  els.palette.style.display = 'flex';
  els.editBtn.style.display = 'none';
  rebuild();
}

function exitEdit(){
  active = false; selected = -1; selRing.visible = false;
  ['editTop','palette','selPanel','swatches'].forEach(id => els[id].style.display = 'none');
  els.editBtn.style.display = '';
  if(onExit) onExit();
}

els.doneBtn.onclick = async () => {
  if(!active) return;
  if(!dirty){ exitEdit(); return; }
  els.doneBtn.disabled = true;
  try {
    const r = await api.saveItems(room, items);
    els.hint.textContent = (r.ok ? '🛋 ' : '⏳ ') + r.message;
    if(r.ok) exitEdit();
  } catch(e){ els.hint.textContent = 'Failed to save'; }
  els.doneBtn.disabled = false;
};

els.discardBtn.onclick = () => {
  if(!active) return;
  if(dirty && !confirm('Discard your changes?')) return;
  exitEdit();
};

els.undoBtn.onclick = undo;

// ── 팔레트(추가) ──
PALETTE_DEF.forEach(([kind, icon, label]) => {
  const b = document.createElement('button');
  b.className = 'pal-chip';
  b.innerHTML = icon + '<small>' + label + '</small>';
  b.onclick = () => addItem(kind);
  els.palette.appendChild(b);
});

// 기존 가구와 안 겹치는 자리를 중앙부터 나선형으로 탐색
function freeSpot(){
  const half = roomSize / 2 - 0.8;
  for(let r = 0; r <= half; r += 0.7){
    const steps = Math.max(1, Math.round(r * 8));
    for(let k = 0; k < steps; k++){
      const a = (k / steps) * Math.PI * 2;
      const x = Math.cos(a) * r, z = Math.sin(a) * r;
      if(Math.abs(x) > half || Math.abs(z) > half) continue;
      const clash = items.some(it => Math.hypot((it.x || 0) - x, (it.z || 0) - z) < 1.0);
      if(!clash) return { x, z };
    }
  }
  return { x: 0, z: 0 };
}

function addItem(kind){
  if(!active) return;
  snapshot();
  const p = freeSpot();
  items.push({ item: kind, x: Math.round(p.x / SNAP) * SNAP, z: Math.round(p.z / SNAP) * SNAP });
  select(items.length - 1);
}

// ── 선택 패널 ──
els.rotBtn.onclick = () => { if(selected < 0) return;
  snapshot(); const it = items[selected]; it.ry = ((it.ry || 0) + 45) % 360; rebuild(); };

els.scaleUp.onclick = () => bumpScale(+0.15);
els.scaleDn.onclick = () => bumpScale(-0.15);
function bumpScale(d){ if(selected < 0) return;
  snapshot(); const it = items[selected]; it.scale = Math.max(0.3, Math.min(3, (it.scale || 1) + d)); rebuild(); }

els.dupBtn.onclick = () => { if(selected < 0) return;
  snapshot();
  const half = roomSize / 2 - 0.4, src = items[selected];
  const copy = { ...src, x: Math.min(half, (src.x || 0) + 0.6), z: Math.min(half, (src.z || 0) + 0.6) };
  items.push(copy); select(items.length - 1); };

els.delBtn.onclick = () => { if(selected < 0) return;
  snapshot(); items.splice(selected, 1); selected = -1; rebuild(); };

// 색상 스와치
COLORS.forEach(c => {
  const b = document.createElement('button');
  b.className = 'swatch'; b.style.background = c;
  b.onclick = () => { if(selected < 0) return;
    snapshot(); items[selected].color = c; rebuild(); };
  els.swatches.appendChild(b);
});
els.colorBtn.onclick = () => {
  els.swatches.style.display = els.swatches.style.display === 'none' ? 'flex' : 'none';
};

// ── 선택 + 드래그 (OrbitControls와 공존: 가구를 잡았을 때만 카메라 잠금) ──
const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
const floor = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
const hit3 = new THREE.Vector3();
let dragging = false, dragMoved = false;

function toNDC(e){
  const r = cv.getBoundingClientRect();
  ndc.x = ((e.clientX - r.left) / r.width) * 2 - 1;
  ndc.y = -((e.clientY - r.top) / r.height) * 2 + 1;
}

function pick(e){
  toNDC(e);
  ray.setFromCamera(ndc, camera);
  const hits = ray.intersectObjects(furnitureGroup.children, true);
  if(!hits.length) return -1;
  let obj = hits[0].object;
  while(obj && obj.userData.itemIndex === undefined) obj = obj.parent;
  return obj ? obj.userData.itemIndex : -1;
}

cv.addEventListener('pointerdown', e => {
  if(!active) return;
  const idx = pick(e);
  if(idx !== selected) select(idx);
  if(idx >= 0){
    dragging = true; dragMoved = false; controls.enabled = false;
    try { cv.setPointerCapture(e.pointerId); } catch(_) {}
  }
});

cv.addEventListener('pointermove', e => {
  if(!active || !dragging || selected < 0) return;
  toNDC(e);
  ray.setFromCamera(ndc, camera);
  if(!ray.ray.intersectPlane(floor, hit3)) return;
  if(!dragMoved){ dragMoved = true; snapshot(); }   // 드래그 시작 시점 스냅샷(한 번만)
  const half = roomSize / 2 - 0.3;
  const it = items[selected];
  it.x = Math.round(Math.max(-half, Math.min(half, hit3.x)) / SNAP) * SNAP;
  it.z = Math.round(Math.max(-half, Math.min(half, hit3.z)) / SNAP) * SNAP;
  const g = groupOf(selected);
  if(g){ g.position.x = it.x; g.position.z = it.z; }
  selRing.position.x = it.x; selRing.position.z = it.z;
});

cv.addEventListener('pointerup', () => {
  if(dragging){ dragging = false; controls.enabled = true; }
});
