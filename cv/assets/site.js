/* délais d'apparition : posés en CSSOM (autorisé même avec une politique CSP stricte) */
[].forEach.call(document.querySelectorAll('[data-d]'),function(e){e.style.setProperty('--d',e.getAttribute('data-d'))});
(function(){
  var root=document.documentElement;
  var reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.getElementById('y').textContent=new Date().getFullYear();

  /* ---------- thème clair / sombre ---------- */
  try{var t=localStorage.getItem('cm-theme');if(t)root.setAttribute('data-theme',t)}catch(e){}
  document.getElementById('theme').addEventListener('click',function(){
    var cur=root.getAttribute('data-theme')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
    var next=cur==='dark'?'light':'dark';
    root.setAttribute('data-theme',next);
    try{localStorage.setItem('cm-theme',next)}catch(e){}
    drawAll();
  });

  /* ---------- apparitions au défilement ---------- */
  var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){e.target.classList.add('in');io.unobserve(e.target)}})},{rootMargin:'0px 0px -8% 0px'});
  document.querySelectorAll('.rv').forEach(function(el){io.observe(el)});

  /* ---------- reflet spéculaire du verre ---------- */
  document.querySelectorAll('.glass').forEach(function(el){
    el.addEventListener('pointermove',function(e){
      var r=el.getBoundingClientRect();
      el.style.setProperty('--mx',(e.clientX-r.left)+'px');
      el.style.setProperty('--my',(e.clientY-r.top)+'px');
      el.classList.add('spec');
    });
    el.addEventListener('pointerleave',function(){el.classList.remove('spec')});
  });

  /* ---------- texte « Mon projet » qui s'illumine ---------- */
  var rt=document.getElementById('reveal');
  rt.innerHTML=rt.textContent.trim().split(/\s+/).map(function(w){
    var k=w.charAt(0)==='*';if(k)w=w.slice(1);
    return '<span class="w'+(k?' k':'')+'">'+w+'</span>';
  }).join(' ');
  var words=rt.querySelectorAll('.w');
  function lightWords(){
    var r=rt.getBoundingClientRect(),vh=innerHeight;
    var p=(vh*.85-r.top)/(r.height+vh*.35);
    var n=Math.round(Math.max(0,Math.min(1,p))*words.length);
    for(var i=0;i<words.length;i++)words[i].classList.toggle('on',i<n);
  }

  /* ---------- dock : longueur de tracé normalisée pour l'animation de dessin ---------- */
  var dock=document.querySelector('.dock');
  dock.querySelectorAll('svg>*').forEach(function(el){el.setAttribute('pathLength','1')});
  /* section active */
  var secs=['accueil','profil','competences','parcours','projets','contact'].map(function(id){return document.getElementById(id)});
  function activeNav(){
    var cur=secs[0];secs.forEach(function(s){if(s.getBoundingClientRect().top<innerHeight*.4)cur=s});
    dock.querySelectorAll('a').forEach(function(a){a.classList.toggle('on',a.getAttribute('href')==='#'+cur.id)});
  }

  /* barre de progression : un segment par section, qui se remplit avant de passer à la suivante */
  var prog=document.querySelector('.progress'),segs=prog.querySelectorAll('.seg');
  function progress(){
    var ih=innerHeight,docH=document.documentElement.scrollHeight,pos=scrollY+ih*.4;
    var tops=secs.map(function(s){return s.getBoundingClientRect().top+scrollY});
    for(var i=0;i<secs.length;i++){
      var start=tops[i],end=i<secs.length-1?tops[i+1]:Math.max(start+1,docH-ih*.6);
      var p=Math.max(0,Math.min(1,(pos-start)/(end-start)));
      segs[i].firstChild.style.setProperty('--p',p);
      segs[i].classList.toggle('done',p>=1&&i<secs.length-1);
    }
    prog.setAttribute('aria-valuenow',Math.round(Math.min(1,scrollY/Math.max(1,docH-ih))*100));
  }

  /* ---------- lecteurs vidéo ---------- */
  var players=[].slice.call(document.querySelectorAll('.vplayer'));
  function fmt(s){if(!isFinite(s))return '0:00';s=Math.max(0,Math.floor(s));return Math.floor(s/60)+':'+String(s%60).padStart(2,'0')}
  players.forEach(function(pl){
    var v=pl.querySelector('video'),prog=pl.querySelector('.vp-prog'),fill=pl.querySelector('.vp-fill'),buf=pl.querySelector('.vp-buf'),knob=pl.querySelector('.vp-knob'),
        cur=pl.querySelector('.vp-cur-t'),dur=pl.querySelector('.vp-dur-t'),vol=pl.querySelector('.vp-vol'),idleT=0,raf=0;
    pl.classList.add('fresh');
    function toggle(){if(v.paused||v.ended){players.forEach(function(o){if(o!==pl)o.querySelector('video').pause()});var pr=v.play();if(pr&&pr.catch)pr.catch(function(){})}else v.pause()}
    function paint(){var d=v.duration||0,f=d?v.currentTime/d:0;fill.style.width=(f*100)+'%';knob.style.left=(f*100)+'%';cur.textContent=fmt(v.currentTime);prog.setAttribute('aria-valuenow',Math.round(f*100));
      if(v.buffered.length&&d)buf.style.width=(v.buffered.end(v.buffered.length-1)/d*100)+'%'}
    function loop(){paint();if(!v.paused)raf=requestAnimationFrame(loop)}
    function wake(){pl.classList.remove('idle');clearTimeout(idleT);if(!v.paused)idleT=setTimeout(function(){pl.classList.add('idle')},2500)}
    pl.querySelector('.vp-big').addEventListener('click',toggle);
    pl.querySelector('.vp-play').addEventListener('click',toggle);
    v.addEventListener('click',toggle);
    v.addEventListener('play',function(){pl.classList.add('playing');pl.classList.remove('fresh');cancelAnimationFrame(raf);loop();wake()});
    v.addEventListener('pause',function(){pl.classList.remove('playing','idle');paint()});
    v.addEventListener('ended',function(){pl.classList.remove('playing','idle')});
    v.addEventListener('loadedmetadata',function(){dur.textContent=fmt(v.duration);paint()});
    v.addEventListener('progress',paint);v.addEventListener('timeupdate',paint);
    v.addEventListener('waiting',function(){pl.classList.add('waiting')});
    ['playing','canplay','seeked'].forEach(function(e){v.addEventListener(e,function(){pl.classList.remove('waiting')})});
    v.addEventListener('error',function(){pl.classList.add('error')});
    var src=v.querySelector('source')||v;src.addEventListener('error',function(){pl.classList.add('error')});
    if(v.error)pl.classList.add('error');
    /* déplacement dans la vidéo */
    function seekAt(x){var r=prog.getBoundingClientRect(),f=Math.min(1,Math.max(0,(x-r.left)/r.width));if(v.duration){v.currentTime=f*v.duration;paint()}}
    prog.addEventListener('pointerdown',function(e){pl.classList.add('scrub');prog.setPointerCapture(e.pointerId);seekAt(e.clientX)});
    prog.addEventListener('pointermove',function(e){if(pl.classList.contains('scrub'))seekAt(e.clientX)});
    prog.addEventListener('pointerup',function(){pl.classList.remove('scrub')});
    prog.addEventListener('keydown',function(e){if(e.key==='ArrowRight'){v.currentTime+=5;e.preventDefault()}if(e.key==='ArrowLeft'){v.currentTime-=5;e.preventDefault()}});
    /* son */
    function syncMute(){pl.classList.toggle('muted',v.muted||v.volume===0)}
    pl.querySelector('.vp-mute').addEventListener('click',function(){v.muted=!v.muted;if(!v.muted&&v.volume===0){v.volume=.6;vol.value=.6}syncMute()});
    vol.addEventListener('input',function(){v.volume=+vol.value;v.muted=+vol.value===0;syncMute()});
    /* plein écran */
    pl.querySelector('.vp-fs').addEventListener('click',function(){
      if(document.fullscreenElement){document.exitFullscreen()}
      else if(pl.requestFullscreen){pl.requestFullscreen()}
      else if(v.webkitEnterFullscreen){v.webkitEnterFullscreen()}
    });
    /* commandes qui se cachent pendant la lecture */
    pl.addEventListener('pointermove',wake);pl.addEventListener('pointerdown',wake);
    /* clavier */
    pl.setAttribute('tabindex','0');
    pl.addEventListener('keydown',function(e){if(e.target===vol)return;var k=e.key.toLowerCase();
      if(k===' '||k==='k'){toggle();e.preventDefault()}else if(k==='f'){pl.querySelector('.vp-fs').click()}else if(k==='m'){pl.querySelector('.vp-mute').click()}
      else if(e.target!==prog&&k==='arrowright'){v.currentTime+=5}else if(e.target!==prog&&k==='arrowleft'){v.currentTime-=5}wake()});
  });
  /* ---------- courbes de niveau (relevé topographique) ----------
     bruit de valeur + marching squares : un clin d'œil au métier */
  var P=new Uint8Array(512);(function(){var p=[],i,j,t,s=7;for(i=0;i<256;i++)p[i]=i;for(i=255;i>0;i--){s=(s*16807)%2147483647;j=s%(i+1);t=p[i];p[i]=p[j];p[j]=t}for(i=0;i<512;i++)P[i]=p[i&255]})();
  function h(x,y){return P[P[x&255]+(y&255)]/255}
  function sm(t){return t*t*(3-2*t)}
  function noise(x,y){var xi=Math.floor(x),yi=Math.floor(y),xf=sm(x-xi),yf=sm(y-yi);
    var a=h(xi,yi),b=h(xi+1,yi),c=h(xi,yi+1),d=h(xi+1,yi+1);
    return a+(b-a)*xf+(c-a)*yf+(a-b-c+d)*xf*yf}
  function fbm(x,y){return noise(x,y)*.55+noise(x*2.1+5,y*2.1+3)*.28+noise(x*4.3+9,y*4.3+1)*.17}

  function drawTopo(cv,color,scale,levels){
    var dpr=Math.min(devicePixelRatio||1,2),W=cv.clientWidth,H=cv.clientHeight;
    if(!W||!H)return;
    cv.width=W*dpr;cv.height=H*dpr;
    var c=cv.getContext('2d');c.setTransform(dpr,0,0,dpr,0,0);c.clearRect(0,0,W,H);
    var s=12,cols=Math.ceil(W/s)+1,rows=Math.ceil(H/s)+1,f=new Float32Array(cols*rows),x,y,l;
    for(y=0;y<rows;y++)for(x=0;x<cols;x++)f[y*cols+x]=fbm(x*s*scale,y*s*scale);
    c.lineWidth=1;c.strokeStyle=color;c.lineJoin='round';
    for(l=1;l<levels;l++){
      var t=.18+(l/levels)*.64;c.beginPath();
      c.globalAlpha=(l%4===0)?1:.55;
      for(y=0;y<rows-1;y++)for(x=0;x<cols-1;x++){
        var a=f[y*cols+x],b=f[y*cols+x+1],d=f[(y+1)*cols+x],e=f[(y+1)*cols+x+1];
        var k=(a>t?8:0)|(b>t?4:0)|(e>t?2:0)|(d>t?1:0);
        if(k===0||k===15)continue;
        var X=x*s,Y=y*s,
          T=[X+s*(t-a)/(b-a),Y],R=[X+s,Y+s*(t-b)/(e-b)],
          B=[X+s*(t-d)/(e-d),Y+s],L=[X,Y+s*(t-a)/(d-a)],seg;
        switch(k){
          case 1:case 14:seg=[L,B];break;case 2:case 13:seg=[B,R];break;
          case 3:case 12:seg=[L,R];break;case 4:case 11:seg=[T,R];break;
          case 6:case 9:seg=[T,B];break;case 7:case 8:seg=[L,T];break;
          case 5:seg=[L,T,B,R];break;case 10:seg=[T,R,L,B];break;
        }
        for(var i=0;i<seg.length;i+=2){c.moveTo(seg[i][0],seg[i][1]);c.lineTo(seg[i+1][0],seg[i+1][1])}
      }
      c.stroke();
    }
    c.globalAlpha=1;
  }
  var topo=document.getElementById('topo'),topo2=document.getElementById('topo2');
  function drawAll(){
    drawTopo(topo,getComputedStyle(root).getPropertyValue('--topo').trim(),.0026,22);
    drawTopo(topo2,'rgba(141,184,154,.28)',.0034,18);
  }
  drawAll();
  var rz;addEventListener('resize',function(){clearTimeout(rz);rz=setTimeout(drawAll,200)});
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change',drawAll);

  /* ---------- boucle de défilement ---------- */
  var ticking=false;
  function onScroll(){
    if(ticking)return;ticking=true;
    requestAnimationFrame(function(){
      if(!reduce)topo.style.transform='translate3d(0,'+(scrollY*.25)+'px,0)';
      lightWords();activeNav();progress();ticking=false;
    });
  }
  addEventListener('scroll',onScroll,{passive:true});addEventListener('resize',onScroll);onScroll();
})();
