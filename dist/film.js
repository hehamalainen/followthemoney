'use strict';
window.MoneyFilm=(()=>{
 const dialog=document.querySelector('#film-dialog'),video=dialog.querySelector('video');
 let returnFocus=null,oldOverflow='',format='wide';
 function select(next){
  if(next===format)return;
  const playing=!video.paused,time=video.currentTime;
  format=next;
  video.pause();video.src=`media/ai-money-map-30s-${format}.mp4`;
  video.poster=`media/film-${format}.jpg`;
  dialog.classList.toggle('film-vertical',format==='vertical');
  dialog.querySelectorAll('[data-film-format]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.filmFormat===format));
  video.onloadedmetadata=()=>{video.currentTime=Math.min(time,video.duration||30);if(playing&&dialog.open)video.play().catch(()=>{});};
  video.load();
 }
 function open(play=true){
  if(dialog.open)return;
  returnFocus=document.activeElement;oldOverflow=document.body.style.overflow;
  dialog.showModal();document.body.style.overflow='hidden';window.MoneyUniverse?.setActive(false);
  if(play)video.play().catch(()=>{});
 }
 dialog.querySelector('[data-film-close]').onclick=()=>dialog.close();
 dialog.addEventListener('close',()=>{
  video.pause();document.body.style.overflow=oldOverflow;
  if(location.hash==='#film')history.replaceState(null,'',location.pathname+location.search);
  if(document.body.classList.contains('universe-mode'))window.MoneyUniverse?.setActive(true);
  returnFocus?.focus({preventScroll:true});
 });
 dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});
 dialog.querySelectorAll('[data-film-format]').forEach(b=>b.onclick=()=>select(b.dataset.filmFormat));
 dialog.querySelector('[data-film-evidence]').onclick=()=>{dialog.close();setView('circulation')};
 video.addEventListener('play',()=>{if(!dialog.open)video.pause();});
 video.addEventListener('error',()=>{dialog.querySelector('.film-error').hidden=false;});
 video.addEventListener('loadeddata',()=>{dialog.querySelector('.film-error').hidden=true;});
 window.addEventListener('hashchange',()=>{if(location.hash==='#film')open(false)});
 if(location.hash==='#film')window.addEventListener('load',()=>open(false),{once:true});
 return{open};
})();
