// 블록 아바타 — 생성/감정 갱신/배회·경로 추종 애니메이션.

import * as THREE from 'three';
import { ACCENT, HAIRS, PALETTE, currentScene, radius, roomSize, scene, sprite } from './scene3d.js';

export let avatars = {};
export function clearAvatars(){ for(const id in avatars){ scene.remove(avatars[id].group); } avatars = {}; }

function placeCell(i, n){ if(n===1) return [0,0]; const a=-Math.PI/2 + i*(2*Math.PI/n); return [radius*Math.cos(a), radius*Math.sin(a)]; }

// 팔/다리: 윗부분(어깨/엉덩이)을 피벗으로 회전하게 — 피벗 그룹 + 아래로 내린 박스
function limbPivot(px,py,pz, w,h,d, color, offy){
  const pivot=new THREE.Group(); pivot.position.set(px,py,pz);
  const m=new THREE.Mesh(new THREE.BoxGeometry(w,h,d), new THREE.MeshStandardMaterial({color})); m.position.y=offy; m.castShadow=true;
  pivot.add(m); return pivot;
}

export function makeAvatar(a, i, n, idx, elapsed){
  const group=new THREE.Group(); const [x,z]=placeCell(i,n); group.position.set(x,0,z);
  const shirt=PALETTE[idx%PALETTE.length], skin=0xe8c39a, pants=0x3f4a6a;
  const bodyGroup=new THREE.Group(); group.add(bodyGroup);  // 통째로 살짝 bob
  // 마인크래프트풍 블록 휴머노이드 (발 y=0 기준)
  const legL=limbPivot(-0.13,0.7,0, 0.2,0.7,0.22, pants, -0.35);
  const legR=limbPivot( 0.13,0.7,0, 0.2,0.7,0.22, pants, -0.35);
  const armL=limbPivot(-0.34,1.3,0, 0.16,0.6,0.2, shirt, -0.3);
  const armR=limbPivot( 0.34,1.3,0, 0.16,0.6,0.2, shirt, -0.3);
  const torso=new THREE.Mesh(new THREE.BoxGeometry(0.5,0.6,0.28), new THREE.MeshStandardMaterial({color:shirt})); torso.position.y=1.0; torso.castShadow=true;
  const head=new THREE.Mesh(new THREE.BoxGeometry(0.5,0.5,0.5), new THREE.MeshStandardMaterial({color:0xe8c39a})); head.position.y=1.55; head.castShadow=true;
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

export function updateAvatar(a, elapsed){ const av=avatars[a.id];
  if(av.emoji!==a.emoji){ av.emo.material.map.dispose(); av.emo.material=sprite(a.emoji,92).material; av.emoji=a.emoji; av.emoShownAt=elapsed; } // 감정 바뀜 → 다시 팝
  av.speaking=a.speaking; }

// 감정 이모지 표시 곡선: 0~3초 풀, 3~4초 페이드, 이후 숨김
const EMO_FULL=3.0, EMO_FADE=1.0;
function emoOpacity(shownAt, elapsed){ if(shownAt===undefined) return 0; const age=elapsed-shownAt;
  return age<EMO_FULL ? 1 : (age<EMO_FULL+EMO_FADE ? 1-(age-EMO_FULL)/EMO_FADE : 0); }

// 랜덤 배회: 방/광장 안 한 점을 목표로 천천히 걷고, 도착하면 새 목표. 중앙(분수 등)은 회피.
const WANDER_SPEED = 0.7, PATH_SPEED = 1.8;
function newTarget(){
  const maxR = Math.min(roomSize*0.38, 7.5), keep = (currentScene==='outdoor' ? 1.9 : 0.6);
  let x, z, r;
  do { x=(Math.random()*2-1)*maxR; z=(Math.random()*2-1)*maxR; r=Math.hypot(x,z); } while(r<keep || r>maxR);
  return { x, z };
}

// 매 프레임 호출 — idle↔walk 상태머신 + 경로 추종 + 팔다리 스윙 + 감정 페이드
export function animateAvatars(dt, elapsed, watching){
  for(const id in avatars){ const av=avatars[id], g=av.group;
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
    const eop = emoOpacity(av.emoShownAt, elapsed); av.emo.material.opacity=eop; av.emo.visible = eop>0.01;
  }
}
