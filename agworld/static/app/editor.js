// 가구 편집 모드 — 내 방에서만. 탭으로 선택, 드래그로 이동, 툴바로 회전/크기/삭제/추가.
//
// 동작 원리: items(작업 사본)가 진실이고, 변경마다 buildFurniture(items)로 씬을 다시 짓는다.
// 드래그만 예외 — 매 프레임 재빌드는 비싸서 선택된 그룹의 position을 직접 옮기고 item에 반영.

import * as THREE from 'three';
import { api } from './net.js';
import { ACCENT, buildFurniture, camera, controls, cv, furnitureGroup, roomSize, scene } from './scene3d.js';

// 편집기에서 추가할 수 있는 실내 가구 (서버 INDOOR_CATALOG와 동일)
const ADDABLE = ['rug', 'sofa', 'table', 'chair', 'bookshelf', 'plant', 'lamp', 'picture', 'window'];

const els = {};
['editBtn','editbar','editHint','addSelect','addBtn','rotBtn','scaleDn','scaleUp','delBtn','saveEditBtn','cancelEditBtn','hint']
  .forEach(id => els[id] = document.getElementById(id));

let active = false;
let items = [];          // 작업 사본
let selected = -1;       // items 인덱스
let room = '';           // 편집 중인 방 id
let onExit = null;       // 종료 콜백(메인이 방 다시 로드)

// 선택 표시 링
const selRing = new THREE.Mesh(new THREE.TorusGeometry(0.8, 0.05, 8, 36),
  new THREE.MeshBasicMaterial({ color: ACCENT }));
selRing.rotation.x = Math.PI / 2; selRing.position.y = 0.04; selRing.visible = false;
scene.add(selRing);

function syncToolbar(){
  const has = selected >= 0;
  ['rotBtn','scaleDn','scaleUp','delBtn'].forEach(id => els[id].disabled = !has);
  selRing.visible = active && has;
  if(has){ const it = items[selected];
    selRing.position.x = it.x || 0; selRing.position.z = it.z || 0;
    selRing.scale.setScalar(Math.max(0.7, it.scale || 1)); }
}

function rebuild(){ buildFurniture(items); syncToolbar(); }

function select(idx){ selected = idx; syncToolbar(); }

export function isEditing(){ return active; }

export function enterEdit(place, currentItems, exitCb){
  active = true; room = place; onExit = exitCb;
  items = currentItems.map(it => ({ ...it }));
  selected = -1;
  els.editbar.style.display = 'flex';
  els.editHint.style.display = '';
  els.editBtn.style.display = 'none';
  rebuild();
}

async function exitEdit(reload){
  active = false; selected = -1; selRing.visible = false;
  els.editbar.style.display = 'none';
  els.editHint.style.display = 'none';
  els.editBtn.style.display = '';
  if(onExit) onExit(reload);
}

// ── 툴바 ──
ADDABLE.forEach(k => { const o = document.createElement('option'); o.value = k; o.textContent = k; els.addSelect.appendChild(o); });

els.addBtn.onclick = () => { if(!active) return;
  items.push({ item: els.addSelect.value, x: 0, z: 0 });
  rebuild(); select(items.length - 1); };

els.rotBtn.onclick = () => { if(selected < 0) return;
  const it = items[selected]; it.ry = ((it.ry || 0) + 45) % 360; rebuild(); };

els.scaleUp.onclick = () => bumpScale(+0.15);
els.scaleDn.onclick = () => bumpScale(-0.15);
function bumpScale(d){ if(selected < 0) return;
  const it = items[selected]; it.scale = Math.max(0.3, Math.min(3, (it.scale || 1) + d)); rebuild(); }

els.delBtn.onclick = () => { if(selected < 0) return;
  items.splice(selected, 1); selected = -1; rebuild(); };

els.saveEditBtn.onclick = async () => { if(!active) return;
  els.saveEditBtn.disabled = true;
  try {
    const r = await api.saveItems(room, items);
    els.hint.textContent = (r.ok ? '🛋 ' : '⏳ ') + r.message;
    if(r.ok) exitEdit(true);
  } catch(e){ els.hint.textContent = 'Failed to save'; }
  els.saveEditBtn.disabled = false; };

els.cancelEditBtn.onclick = () => exitEdit(true);   // 원본 다시 로드

// ── 선택 + 드래그 (OrbitControls와 공존: 가구를 잡았을 때만 카메라 잠금) ──
const ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
const floor = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
const hit3 = new THREE.Vector3();
let dragging = false;

function pick(e){
  const r = cv.getBoundingClientRect();
  ndc.x = ((e.clientX - r.left) / r.width) * 2 - 1;
  ndc.y = -((e.clientY - r.top) / r.height) * 2 + 1;
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
  select(idx);
  if(idx >= 0){ dragging = true; controls.enabled = false;
    try { cv.setPointerCapture(e.pointerId); } catch(_) {} }
});

cv.addEventListener('pointermove', e => {
  if(!active || !dragging || selected < 0) return;
  const r = cv.getBoundingClientRect();
  ndc.x = ((e.clientX - r.left) / r.width) * 2 - 1;
  ndc.y = -((e.clientY - r.top) / r.height) * 2 + 1;
  ray.setFromCamera(ndc, camera);
  if(!ray.ray.intersectPlane(floor, hit3)) return;
  const half = roomSize / 2 - 0.3;
  const it = items[selected];
  it.x = Math.max(-half, Math.min(half, hit3.x));
  it.z = Math.max(-half, Math.min(half, hit3.z));
  const g = furnitureGroup.children.find(c => c.userData.itemIndex === selected);
  if(g){ g.position.x = it.x; g.position.z = it.z; }
  selRing.position.x = it.x; selRing.position.z = it.z;
});

cv.addEventListener('pointerup', () => {
  if(dragging){ dragging = false; controls.enabled = true; }
});
