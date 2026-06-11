import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const PALETTE = [0x6fa8a0,0xb08a6f,0xe0a36f,0x8f9bd0,0xc08fb0,0xa0b07a,0xd0a060,0x70b0c0,0xc09070,0x90c090];
const HAIRS = [0x2b2118,0x4a3526,0x1a1a1a,0x6b4a2f,0x5c3a1e,0x8a6a3a,0x3a2a1a,0x705038,0x4a4a4a,0x2a1c14];
const ACCENT = 0xe0742f;

const cv = document.getElementById('scene');
const renderer = new THREE.WebGLRenderer({ canvas: cv, antialias: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
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

const hemi = new THREE.HemisphereLight(0xbfe3f2, 0x8a9a6a, 0.6); scene.add(hemi);
const sun = new THREE.DirectionalLight(0xfff1d8, 1.7); sun.castShadow = true;
sun.shadow.mapSize.set(1024, 1024); sun.shadow.bias = -0.0005;
scene.add(sun); scene.add(sun.target);

function tuneSun(size, sceneType){
  sun.position.set(size*0.85, size*1.6, size*0.7); sun.target.position.set(0,0,0);
  const c = sun.shadow.camera; c.left=-size; c.right=size; c.top=size; c.bottom=-size; c.near=1; c.far=size*5; c.updateProjectionMatrix();
  if(sceneType === 'outdoor'){ hemi.color.set(0xbfe3f2); hemi.groundColor.set(0x7d9a5a); hemi.intensity=0.7; sun.color.set(0xfff1d8); sun.intensity=1.9; }
  else { hemi.color.set(0xf3e8d2); hemi.groundColor.set(0xb0a080); hemi.intensity=0.85; sun.color.set(0xffe9c8); sun.intensity=1.15; }
}

let shellGroup = new THREE.Group(); scene.add(shellGroup);
function buildShell(size, sceneType){
  scene.remove(shellGroup); shellGroup = new THREE.Group(); scene.add(shellGroup);
  tuneSun(size, sceneType);
  if(sceneType === 'outdoor'){
    scene.background = new THREE.Color(0xbfe3f2);
    const grass = new THREE.Mesh(new THREE.BoxGeometry(size*1.9,0.3,size*1.9), new THREE.MeshStandardMaterial({color:0x86b96a}));
    grass.position.y = -0.15; shellGroup.add(grass);
  } else {
    scene.background = new THREE.Color(0xf2e9d6);
    const floor = new THREE.Mesh(new THREE.BoxGeometry(size,0.3,size), new THREE.MeshStandardMaterial({color:0xd9c8a2}));
    floor.position.y = -0.15; shellGroup.add(floor);
  }
  setShadow(shellGroup, false, true);
}

function fmat(c){ return new THREE.MeshStandardMaterial({ color:new THREE.Color(c), roughness:0.85 }); }
function fbox(w,h,d,c){ return new THREE.Mesh(new THREE.BoxGeometry(w,h,d), fmat(c)); }

const FURNITURE = {
  rug(o){ const g=new THREE.Group(); const r=fbox(2,0.04,1.4,o.color||'#c98f5a'); r.position.y=0.02; g.add(r); return g; },
  sofa(o){ const c=o.color||'#7a8a6f', g=new THREE.Group(); const b=fbox(2,0.4,0.9,c); b.position.y=0.3; g.add(b); return g; }
};

let furnitureGroup = new THREE.Group(); scene.add(furnitureGroup);
function buildFurniture(items){
  scene.remove(furnitureGroup); furnitureGroup = new THREE.Group(); scene.add(furnitureGroup);
}

let avatars = {};
function clearAvatars(){ for(const id in avatars){ scene.remove(avatars[id].group); } avatars = {}; }

function makeAvatar(a, i, n, idx){
  const group = new THREE.Group();
  const shirt = PALETTE[idx%PALETTE.length], skin = 0xe8c39a;
  const torso = new THREE.Mesh(new THREE.BoxGeometry(0.5,0.6,0.28), new THREE.MeshStandardMaterial({color:shirt}));
  torso.position.y = 1.0; torso.castShadow = true;
  const head = new THREE.Mesh(new THREE.BoxGeometry(0.5,0.5,0.5), new THREE.MeshStandardMaterial({color:skin}));
  head.position.y = 1.55; head.castShadow = true;
  group.add(torso, head);
  scene.add(group);
  avatars[a.id] = { group };
}

function updateAvatar(a){}

let STATE = null, currentPlace = null, ready = false;

async function loadRoom(place){
  let data; try { data = await (await fetch('/room?place='+place)).json(); } catch(e){ return; }
  roomSize = data.room_size || 8; radius = roomSize*0.28;
  makeCamera(); controls.object = camera;
  buildShell(roomSize, data.scene || 'indoor'); buildFurniture(data.items);
}

async function poll(){
  if(!currentPlace) return;
  let s; try { s = await (await fetch('/state?place='+currentPlace)).json(); }
  catch(e){ return; }
  STATE = s;
  if(!ready){ ready = true; }
  syncScene();
}

function syncScene(){
  if(!STATE) return;
  STATE.agents.forEach((a,i)=>{ if(avatars[a.id]) updateAvatar(a); else makeAvatar(a,i,STATE.agents.length,i); });
}

const clock = new THREE.Clock();
let elapsed = 0;

function animate(){
  requestAnimationFrame(animate);
  const dt = Math.min(clock.getDelta(),0.05); elapsed += dt;
  controls.update(); renderer.render(scene, camera);
}

function resize(){
  const r = cv.getBoundingClientRect();
  renderer.setSize(r.width, r.height, false);
  makeCamera(); controls.object = camera;
}
window.addEventListener('resize', resize);

async function buildTabs(){ /* placeholder */ }
async function sendWhisper(){ /* placeholder */ }

console.log('Full logic skeleton ready');