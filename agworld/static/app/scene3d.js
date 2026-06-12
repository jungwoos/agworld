// Three.js 씬 — 렌더러/카메라/조명/셸(방·잔디)/가구 카탈로그.
// 모듈 상태는 live binding으로 노출한다(camera는 리사이즈마다 재생성).

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

export const ACCENT = 0xe0742f;
export const PALETTE = [0x6fa8a0,0xb08a6f,0xe0a36f,0x8f9bd0,0xc08fb0,0xa0b07a,0xd0a060,0x70b0c0,0xc09070,0x90c090];
export const HAIRS = [0x2b2118,0x4a3526,0x1a1a1a,0x6b4a2f,0x5c3a1e,0x8a6a3a,0x3a2a1a,0x705038,0x4a4a4a,0x2a1c14];

export const cv = document.getElementById('scene');
export const renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;

export const scene = new THREE.Scene();
scene.background = new THREE.Color(0xf2e9d6);

export function setShadow(obj, cast, recv){ obj.traverse(m=>{ if(m.isMesh){ m.castShadow=cast; m.receiveShadow=recv; } }); }

export let roomSize = 8, radius = 2.4, currentScene = 'indoor';
export let camera, controls;

export function makeCamera(){
  const r = cv.getBoundingClientRect(), aspect = r.width/Math.max(1,r.height), F = roomSize*0.78;
  camera = new THREE.OrthographicCamera(-F*aspect, F*aspect, F, -F, 0.1, 200);
  const d = roomSize*1.1;
  camera.position.set(d, d*0.9, d); camera.lookAt(0, 1, 0);
  if(controls) controls.object = camera;
}
makeCamera();
controls = new OrbitControls(camera, renderer.domElement);
controls.enablePan = false; controls.minPolarAngle = 0.3; controls.maxPolarAngle = 1.35; controls.target.set(0,1,0);

export function setRoom(size, sceneType){
  roomSize = size; radius = size*0.28; currentScene = sceneType;
  makeCamera();
}

export function resize(){
  const r = cv.getBoundingClientRect();
  renderer.setSize(r.width, r.height, false);
  makeCamera();
}
window.addEventListener('resize', resize);

// ── 자연광: 하늘광(HemisphereLight) + 태양(그림자 캐스팅 DirectionalLight) ──
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

// ── 씬 셸 — 장소 크기/테마에 맞춰 재생성 (indoor=방, outdoor=잔디 마을) ──
let shellGroup = new THREE.Group(); scene.add(shellGroup);
export function buildShell(size, sceneType){
  scene.remove(shellGroup); shellGroup = new THREE.Group(); scene.add(shellGroup);
  tuneSun(size, sceneType);
  if(sceneType === 'outdoor'){
    scene.background = new THREE.Color(0xbfe3f2);                       // 하늘
    const grass = new THREE.Mesh(new THREE.BoxGeometry(size*1.9,0.3,size*1.9), new THREE.MeshStandardMaterial({color:0x86b96a}));
    grass.position.y = -0.15; shellGroup.add(grass);                   // 잔디밭(넓게)
    const plazaR = Math.min(size*0.42, 6.2);                            // 광장은 절대 크기 유지
    const plaza = new THREE.Mesh(new THREE.CircleGeometry(plazaR,48), new THREE.MeshStandardMaterial({color:0xd8cdb4}));
    plaza.rotation.x = -Math.PI/2; plaza.position.y = 0.02; shellGroup.add(plaza);
    const edge = new THREE.Mesh(new THREE.RingGeometry(plazaR,plazaR+0.55,48), new THREE.MeshStandardMaterial({color:0xb6a886,side:THREE.DoubleSide}));
    edge.rotation.x = -Math.PI/2; edge.position.y = 0.025; shellGroup.add(edge);
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

// ── 스프라이트(이모지/이름) ──
export function sprite(text, px, color){
  const c=document.createElement('canvas'); c.width=c.height=128; const g=c.getContext('2d');
  g.font=px+'px -apple-system,"Apple Color Emoji","Apple SD Gothic Neo",sans-serif'; g.textAlign='center'; g.textBaseline='middle';
  if(color) g.fillStyle=color; g.fillText(text,64,70);
  const tex=new THREE.CanvasTexture(c); return new THREE.Sprite(new THREE.SpriteMaterial({map:tex,transparent:true}));
}

// ── 가구 카탈로그 ──
function fmat(c){ return new THREE.MeshStandardMaterial({ color:new THREE.Color(c), roughness:0.85 }); }
function fbox(w,h,d,c){ return new THREE.Mesh(new THREE.BoxGeometry(w,h,d), fmat(c)); }
function fcyl(rt,rb,h,c){ return new THREE.Mesh(new THREE.CylinderGeometry(rt,rb,h,16), fmat(c)); }

export const FURNITURE = {
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
    const ped=new THREE.Mesh(new THREE.CylinderGeometry(0.001,1.5,1.0,4), fmat('#a5634c'));
    ped.rotation.y=Math.PI/4; ped.scale.set(2.0,1,1.3); ped.position.y=3.2; g.add(ped);
    [-1.6,-0.55,0.55,1.6].forEach(x=>{ const c=fcyl(0.16,0.16,2.2,'#f3ece0'); c.position.set(x,1.2,1.15); g.add(c); });
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

// ── 가구 배치 ──
export let furnitureGroup = new THREE.Group(); scene.add(furnitureGroup);
export let houses = [];   // 탭 내비게이션 대상: {group, place, label, x, z}
export function buildFurniture(items){
  scene.remove(furnitureGroup); furnitureGroup = new THREE.Group(); scene.add(furnitureGroup);
  houses = [];
  (items||[]).forEach((it, idx)=>{ const b=FURNITURE[it.item]; if(!b) return; const g=b(it);
    g.position.x+=(it.x||0); g.position.z+=(it.z||0);
    if(it.ry) g.rotation.y=it.ry*Math.PI/180;
    if(it.scale) g.scale.multiplyScalar(it.scale);
    g.userData.itemIndex = idx;   // 편집기에서 선택 → 원본 item 매핑
    furnitureGroup.add(g);
    if(it.item==='house' && it.place){ g.userData.place=it.place; houses.push({group:g, place:it.place, label:it.label||it.place, x:it.x||0, z:it.z||0}); } });
  setShadow(furnitureGroup, true, true);   // 가구/타운홀/나무는 그림자를 '드리움'
}
