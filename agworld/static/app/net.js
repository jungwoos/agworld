// 입장 키 + API 클라이언트.
// URL의 ?me=&key=를 localStorage에 기억 → 이후엔 주소만 쳐도 유지. 키 없으면 관전 모드.

const q = new URLSearchParams(location.search);
if (q.get('me') && q.get('key')) {
  localStorage.setItem('agw_me', q.get('me'));
  localStorage.setItem('agw_key', q.get('key'));
}

export const ME = localStorage.getItem('agw_me') || '';
const KEY = localStorage.getItem('agw_key') || '';
export const AUTH = ME ? ('&me=' + encodeURIComponent(ME) + '&key=' + encodeURIComponent(KEY)) : '';

const json = r => r.json();
const post = body => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });

export const api = {
  places: () => fetch('/places').then(json),
  state: place => fetch(`/state?place=${place}${AUTH}`).then(json),
  room: place => fetch(`/room?place=${place}`).then(json),
  whisper: (place, text) => fetch(`/whisper?place=${place}${AUTH}`, post({ text })).then(json),
  saveItems: (room, items) => fetch(`/room/items?room=${room}${AUTH}`, post({ items })).then(json),
};
