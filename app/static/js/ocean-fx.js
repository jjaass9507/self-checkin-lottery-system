/*
 * Ocean FX — 海洋風背景（WebGL 水波光影＋光束）、泡泡、慶祝特效 OceanFX.burst()
 *
 * 用法：<ocean-scene palette="lagoon|abyss|twilight" intensity="1" bubbles="40" interactive="true"></ocean-scene>
 * 網址參數 ?fx=0~1.8 可覆蓋特效強度；?fx=0 只顯示靜態背景（適合較舊的報到機/投影電腦）。
 *
 * 效能設計（相較設計稿原型）：
 *  - 水波 shader 以 0.5 倍解析度、最高 30fps 繪製，泡泡與光點以預先繪好的貼圖 drawImage，不再每幀建立漸層。
 *  - 所有移動以時間計算，120/144Hz 螢幕不會變快也不會多算。
 *  - 分頁隱藏時完全暫停；偵測到掉幀時自動降級（降解析度、減少泡泡，最後改靜態背景）。
 *  - 系統設定「減少動態效果」時只畫一張靜態背景。
 */
(function () {
  'use strict';
  if (window.OceanFX) return;

  const PALETTES = {
    lagoon: { top: [0.05, 0.52, 0.68], bot: [0.005, 0.06, 0.14], ray: [0.55, 0.95, 1.0] },
    abyss: { top: [0.03, 0.30, 0.50], bot: [0.0, 0.025, 0.08], ray: [0.45, 0.80, 1.0] },
    twilight: { top: [0.10, 0.32, 0.62], bot: [0.02, 0.03, 0.12], ray: [0.85, 0.80, 1.0] }
  };

  // 品質等級：掉幀時逐級下降
  const LEVELS = [
    { scale: 0.5, fps: 30, bub: 1, motes: 1, burst: 1 },
    { scale: 0.36, fps: 24, bub: 0.5, motes: 0.5, burst: 0.6 },
    { scale: 0.25, fps: 0, bub: 0.25, motes: 0.3, burst: 0.4 } // fps 0 = 水波定格，只剩泡泡在動
  ];

  const reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const urlFx = (function () {
    const v = new URLSearchParams(location.search).get('fx');
    if (v === null || v === '') return null;
    const n = parseFloat(v);
    return isNaN(n) ? null : Math.max(0, Math.min(1.8, n));
  })();
  const staticOnly = reduceMotion || urlFx === 0;
  let quality = 0; // 全頁共用，背景降級時慶祝特效也一起減量

  const VS = 'attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}';
  const FS = `precision mediump float;
uniform vec2 r;uniform float t;uniform float k;uniform vec3 cT;uniform vec3 cB;uniform vec3 cR;uniform vec2 m;
#define TAU 6.28318530718
float caustic(vec2 uv,float time){vec2 p=mod(uv*TAU,TAU)-250.0;vec2 i=p;float c=1.0;float inten=.005;
for(int n=0;n<5;n++){float tt=time*(1.0-(3.5/float(n+1)));i=p+vec2(cos(tt-i.x)+sin(tt+i.y),sin(tt-i.y)+cos(tt+i.x));
c+=1.0/length(vec2(p.x/(sin(i.x+tt)/inten),p.y/(cos(i.y+tt)/inten)));}
c/=5.0;c=1.17-pow(c,1.4);return pow(abs(c),8.0);}
void main(){vec2 uv=gl_FragCoord.xy/r;float asp=r.x/r.y;
vec3 col=mix(cB,cT,pow(uv.y,1.7));
vec2 cuv=vec2(uv.x*asp,uv.y*1.2+t*0.01)*0.85+m*0.03;
float ca=caustic(cuv,t*0.45+23.0);
col+=cR*ca*0.32*k*(0.15+pow(uv.y,1.3));
vec2 src=vec2(0.5+0.12*sin(t*0.07)+m.x*0.05,1.3);vec2 d=uv-src;d.x*=asp*0.6;float ang=atan(d.x,-d.y);
float rays=0.5+0.5*sin(ang*17.0+t*0.35)*sin(ang*7.3-t*0.23);
rays=pow(rays,3.0)*smoothstep(1.6,0.1,length(d));
col+=cR*rays*0.20*k;
col+=cR*smoothstep(0.92,1.0,uv.y)*0.12*k*(0.6+0.4*sin(uv.x*asp*30.0+t*1.6));
vec2 v=uv-vec2(0.5,0.55);col*=1.0-dot(v,v)*0.7;
gl_FragColor=vec4(col,1.0);}`;

  // 預先繪製的泡泡與光點貼圖（每幀只做 drawImage）
  function makeSprite(size, stops) {
    const c = document.createElement('canvas');
    c.width = c.height = size;
    const g = c.getContext('2d');
    const h = size / 2;
    const grad = g.createRadialGradient(h - h * 0.35, h - h * 0.35, h * 0.1, h, h, h);
    stops.forEach(([o, col]) => grad.addColorStop(o, col));
    g.fillStyle = grad;
    g.beginPath(); g.arc(h, h, h, 0, Math.PI * 2); g.fill();
    return c;
  }
  let BUBBLE, MOTE;
  function sprites() {
    if (BUBBLE) return;
    BUBBLE = makeSprite(64, [[0, 'rgba(255,255,255,.55)'], [0.6, 'rgba(160,235,255,.08)'], [1, 'rgba(190,245,255,.45)']]);
    MOTE = document.createElement('canvas');
    MOTE.width = MOTE.height = 8;
    const g = MOTE.getContext('2d');
    const grad = g.createRadialGradient(4, 4, 0, 4, 4, 4);
    grad.addColorStop(0, 'rgba(200,245,255,1)'); grad.addColorStop(0.6, 'rgba(200,245,255,.8)'); grad.addColorStop(1, 'rgba(200,245,255,0)');
    g.fillStyle = grad; g.fillRect(0, 0, 8, 8);
  }

  class OceanScene extends HTMLElement {
    static get observedAttributes() { return ['palette', 'intensity', 'bubbles']; }

    constructor() {
      super();
      const s = this.attachShadow({ mode: 'open' });
      s.innerHTML = '<style>:host{display:block;position:fixed;inset:0;overflow:hidden;pointer-events:none;z-index:0;background:linear-gradient(180deg,#0b5f7c,#02101f)}canvas{position:absolute;inset:0;width:100%;height:100%;display:block}</style><canvas id="g"></canvas><canvas id="b"></canvas>';
      this.g = s.getElementById('g');
      this.b = s.getElementById('b');
      this.bub = [];
      this.motes = [];
      this.mouse = [0, 0];
      this.ptr = null;
      this.lastShader = -1e9;
      this.frameTimes = [];
      this.levelChangedAt = 0;
      this.running = false;
    }

    get pal() { return PALETTES[this.getAttribute('palette')] || PALETTES.lagoon; }
    get intensity() {
      if (urlFx !== null) return urlFx;
      const n = parseFloat(this.getAttribute('intensity'));
      return isNaN(n) ? 1 : n;
    }
    get bubbleCount() { const n = parseInt(this.getAttribute('bubbles'), 10); return isNaN(n) ? 40 : n; }

    attributeChangedCallback() { if (this.isConnected && !this.running) this.drawShader(this.time()); }

    connectedCallback() {
      sprites();
      this.initGL();
      this.ctx = this.b.getContext('2d');
      this.t0 = performance.now();
      this.ro = new ResizeObserver(() => this.resize());
      this.ro.observe(this);
      this.resize();

      if (this.getAttribute('interactive') !== 'false' && !staticOnly) {
        this.onMove = (e) => {
          this.mouse = [e.clientX / this.w - 0.5, 0.5 - e.clientY / this.h];
          this.ptr = [e.clientX, e.clientY];
        };
        this.onDown = (e) => {
          const n = Math.round(14 * LEVELS[quality].bub) || 4;
          for (let i = 0; i < n; i++) this.spawn(e.clientX + (Math.random() - 0.5) * 30, e.clientY + (Math.random() - 0.5) * 30, 3 + Math.random() * 10, true);
        };
        window.addEventListener('pointermove', this.onMove, { passive: true });
        window.addEventListener('pointerdown', this.onDown, { passive: true });
      }

      this.onVis = () => (document.hidden ? this.stop() : this.start());
      document.addEventListener('visibilitychange', this.onVis);

      if (staticOnly) this.drawShader(30); else this.start();
    }

    disconnectedCallback() {
      this.stop();
      if (this.ro) this.ro.disconnect();
      window.removeEventListener('pointermove', this.onMove);
      window.removeEventListener('pointerdown', this.onDown);
      document.removeEventListener('visibilitychange', this.onVis);
    }

    start() {
      if (this.running || staticOnly) return;
      this.running = true;
      this.prev = performance.now();
      const loop = (now) => {
        if (!this.running) return;
        this.raf = requestAnimationFrame(loop);
        this.frame(now);
      };
      this.raf = requestAnimationFrame(loop);
    }

    stop() { this.running = false; cancelAnimationFrame(this.raf); }

    time() { return (performance.now() - this.t0) / 1000; }

    initGL() {
      const gl = this.g.getContext('webgl', { antialias: false, alpha: false, depth: false, stencil: false, preserveDrawingBuffer: false, powerPreference: 'low-power' });
      if (!gl) return;
      const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); return s; };
      const p = gl.createProgram();
      gl.attachShader(p, sh(gl.VERTEX_SHADER, VS));
      gl.attachShader(p, sh(gl.FRAGMENT_SHADER, FS));
      gl.linkProgram(p);
      if (!gl.getProgramParameter(p, gl.LINK_STATUS)) return; // 不支援時退回 CSS 漸層
      gl.useProgram(p);
      const buf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
      const loc = gl.getAttribLocation(p, 'p');
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
      this.u = {};
      ['r', 't', 'k', 'cT', 'cB', 'cR', 'm'].forEach((n) => { this.u[n] = gl.getUniformLocation(p, n); });
      this.gl = gl;
    }

    resize() {
      const w = this.clientWidth || window.innerWidth || 1;
      const h = this.clientHeight || window.innerHeight || 1;
      const lv = LEVELS[quality];
      this.w = w; this.h = h;
      this.g.width = Math.max(1, Math.round(w * lv.scale));
      this.g.height = Math.max(1, Math.round(h * lv.scale));
      if (this.gl) this.gl.viewport(0, 0, this.g.width, this.g.height);
      const d = Math.min(1.5, window.devicePixelRatio || 1);
      this.dpr = d;
      this.b.width = Math.round(w * d);
      this.b.height = Math.round(h * d);
      const n = Math.min(160, Math.round((w * h / 9000) * lv.motes));
      this.motes = Array.from({ length: n }, () => ({ x: Math.random() * w, y: Math.random() * h, r: Math.random() * 1.4 + 0.3, s: Math.random() * 15 + 3, ph: Math.random() * 6 }));
      this.lastShader = -1e9;
      if (!this.running) this.drawShader(this.time());
    }

    spawn(x, y, r, fast) {
      if (this.bub.length > 160) return;
      this.bub.push({ x, y, r, vy: -((fast ? 54 : 21) + r * 3.6), ph: Math.random() * 6, a: 0 });
    }

    drawShader(t) {
      const gl = this.gl;
      if (!gl) return;
      const pal = this.pal;
      gl.uniform2f(this.u.r, this.g.width, this.g.height);
      gl.uniform1f(this.u.t, t);
      gl.uniform1f(this.u.k, this.intensity);
      gl.uniform3fv(this.u.cT, pal.top);
      gl.uniform3fv(this.u.cB, pal.bot);
      gl.uniform3fv(this.u.cR, pal.ray);
      gl.uniform2fv(this.u.m, this.mouse);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    }

    // 連續掉幀時降一級
    watchPerf(dtMs) {
      if (dtMs > 250) return; // 切回分頁、除錯中斷等，不列入
      const ft = this.frameTimes;
      ft.push(dtMs);
      if (ft.length < 90) return;
      const avg = ft.reduce((a, b) => a + b, 0) / ft.length;
      ft.length = 0;
      const now = performance.now();
      if (avg > 26 && quality < LEVELS.length - 1 && now - this.levelChangedAt > 3000) {
        quality++;
        this.levelChangedAt = now;
        this.resize();
      }
    }

    frame(now) {
      const dtMs = now - this.prev;
      this.prev = now;
      this.watchPerf(dtMs);
      const dt = Math.min(0.05, dtMs / 1000); // 秒；上限避免分頁切回時大跳
      const t = (now - this.t0) / 1000;
      const lv = LEVELS[quality];

      if (lv.fps > 0 && t - this.lastShader >= 1 / lv.fps) { this.lastShader = t; this.drawShader(t); }
      else if (lv.fps === 0 && this.lastShader < 0) { this.lastShader = t; this.drawShader(t); }

      const c = this.ctx, w = this.w, h = this.h;
      if (!c) return;
      c.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
      c.clearRect(0, 0, w, h);

      // 光點
      for (const m of this.motes) {
        m.y -= m.s * dt;
        m.x += Math.sin(t * 0.6 + m.ph) * 9 * dt;
        if (m.y < -4) { m.y = h + 4; m.x = Math.random() * w; }
        c.globalAlpha = 0.18 + 0.15 * Math.sin(t + m.ph);
        const s = m.r * 2.4;
        c.drawImage(MOTE, m.x - s / 2, m.y - s / 2, s, s);
      }

      // 滑鼠移動時冒泡（每秒約 12 顆）
      if (this.ptr && Math.random() < 12 * dt * lv.bub) { this.spawn(this.ptr[0], this.ptr[1], 3 + Math.random() * 5, true); this.ptr = null; }

      const ambient = this.bubbleCount * (w / 1400) * lv.bub;
      if (this.bub.length < ambient && Math.random() < 15 * dt) this.spawn(Math.random() * w, h + 20, 2 + Math.random() * 9, false);

      let j = 0;
      const decay = Math.pow(0.999, dt * 60);
      for (let i = 0; i < this.bub.length; i++) {
        const b = this.bub[i];
        b.y += b.vy * dt;
        b.vy *= decay;
        b.x += Math.sin(t * 2 + b.ph) * 21 * dt;
        b.a = Math.min(1, b.a + 2.4 * dt);
        if (b.y <= -30) continue;
        this.bub[j++] = b;
        c.globalAlpha = b.a;
        c.drawImage(BUBBLE, b.x - b.r, b.y - b.r, b.r * 2, b.r * 2);
      }
      this.bub.length = j;
      c.globalAlpha = 1;
    }
  }
  if (!customElements.get('ocean-scene')) customElements.define('ocean-scene', OceanScene);

  // 慶祝特效：金色碎片＋泡泡＋漣漪。共用一張畫布，連續觸發也不會疊出多張全螢幕畫布。
  let fxCanvas = null, fxCtx = null, particles = [], rings = [], fxRaf = 0, fxPrev = 0;
  const GOLDS = ['#F6D58E', '#E9B95A', '#FFF1C9', '#C9973F'];
  const AQUAS = ['#7EF0E0', '#BDF7FF', '#5CC8F0'];

  function ensureCanvas() {
    if (fxCanvas) return;
    fxCanvas = document.createElement('canvas');
    fxCanvas.style.cssText = 'position:fixed;inset:0;width:100vw;height:100vh;pointer-events:none;z-index:9999';
    document.body.appendChild(fxCanvas);
    fxCtx = fxCanvas.getContext('2d');
  }

  function sizeCanvas() {
    const d = Math.min(1.5, window.devicePixelRatio || 1);
    fxCanvas.width = Math.round(innerWidth * d);
    fxCanvas.height = Math.round(innerHeight * d);
    fxCtx.setTransform(d, 0, 0, d, 0, 0);
  }

  function tick(now) {
    const k = Math.min(3, (now - fxPrev) / (1000 / 60)); // 以 60fps 為基準的步進倍數
    fxPrev = now;
    const c = fxCtx, W = innerWidth, H = innerHeight;
    c.clearRect(0, 0, W, H);
    const reach = Math.max(W, H) * 0.45;

    let ri = 0;
    for (const rg of rings) {
      const tt = (now - rg.t0) / 900;
      if (tt > 1) continue;
      rings[ri++] = rg;
      if (tt < 0) continue;
      c.globalAlpha = (1 - tt) * 0.7;
      c.strokeStyle = 'rgb(190,245,255)';
      c.lineWidth = 2 + (1 - tt) * 3;
      c.beginPath(); c.arc(rg.x, rg.y, 30 + tt * reach, 0, 7); c.stroke();
    }
    rings.length = ri;

    const drag = Math.pow(0.985, k);
    let pi = 0;
    for (const p of particles) {
      p.vy += (p.gold ? 0.22 : -0.12) * k;
      p.vx *= drag; p.vy *= drag;
      p.x += p.vx * k; p.y += p.vy * k;
      p.rot += p.vr * k;
      p.life -= 0.008 * k;
      if (p.life <= 0) continue;
      particles[pi++] = p;
      c.globalAlpha = p.life;
      if (p.gold) {
        const d = fxCanvas.width / W;
        const cos = Math.cos(p.rot), sin = Math.sin(p.rot), sy = Math.cos(p.rot * 3);
        c.setTransform(d * cos, d * sin, -d * sin * sy, d * cos * sy, d * p.x, d * p.y);
        c.fillStyle = p.col;
        c.fillRect(-p.s / 2, -p.s / 4, p.s, p.s / 2);
        c.setTransform(d, 0, 0, d, 0, 0);
      } else {
        c.strokeStyle = p.col; c.lineWidth = 1.5;
        c.beginPath(); c.arc(p.x, p.y, p.s, 0, 7); c.stroke();
      }
    }
    particles.length = pi;
    c.globalAlpha = 1;

    if (particles.length || rings.length) fxRaf = requestAnimationFrame(tick);
    else { fxRaf = 0; c.clearRect(0, 0, W, H); fxCanvas.style.display = 'none'; }
  }

  function burst(x, y, opts) {
    if (staticOnly) return;
    opts = opts || {};
    ensureCanvas();
    if (!fxRaf) { fxCanvas.style.display = ''; sizeCanvas(); }
    x = x == null ? innerWidth / 2 : x;
    y = y == null ? innerHeight / 2 : y;
    const n = Math.round((opts.count || 140) * LEVELS[quality].burst);
    const goldRatio = opts.gold == null ? 0.65 : opts.gold;
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2, sp = 4 + Math.random() * (opts.power || 11), gold = Math.random() < goldRatio;
      particles.push({ x, y, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp - 4, s: gold ? 5 + Math.random() * 7 : 3 + Math.random() * 6, rot: Math.random() * 6, vr: (Math.random() - 0.5) * 0.4, gold, col: gold ? GOLDS[i % 4] : AQUAS[i % 3], life: 1 });
    }
    if (particles.length > 600) particles.splice(0, particles.length - 600);
    const t0 = performance.now();
    [0, 120, 260].forEach((dl) => rings.push({ x, y, t0: t0 + dl }));
    if (!fxRaf) { fxPrev = performance.now(); fxRaf = requestAnimationFrame(tick); }
  }

  // 票卡傾斜＋流光：滑鼠事件只記座標，每個畫面幀最多更新一次，且只改 transform
  function tilt(wrap, card) {
    const band = card.querySelector('.holo-band');
    const spot = card.querySelector('.holo-spot');
    let frame = 0, pos = null;
    function apply() {
      frame = 0;
      if (!pos) {
        card.style.transform = '';
        card.classList.remove('tilting');
        if (band) band.style.transform = '';
        if (spot) spot.style.transform = 'translate(30%, 0%)';
        return;
      }
      const x = pos[0], y = pos[1];
      card.style.transform = 'rotateX(' + ((0.5 - y) * 14).toFixed(2) + 'deg) rotateY(' + ((x - 0.5) * 18).toFixed(2) + 'deg)';
      card.classList.add('tilting');
      if (band) band.style.transform = 'translate(' + ((0.5 - x) * 30).toFixed(1) + '%, ' + ((0.5 - y) * 30).toFixed(1) + '%)';
      if (spot) spot.style.transform = 'translate(' + (x * 100).toFixed(1) + '%, ' + (y * 100).toFixed(1) + '%)';
    }
    function queue(p) { pos = p; if (!frame) frame = requestAnimationFrame(apply); }
    apply();
    if (staticOnly || !window.matchMedia('(hover: hover) and (pointer: fine)').matches) return { reset: function () {} };
    wrap.addEventListener('pointermove', function (e) {
      const b = wrap.getBoundingClientRect();
      queue([(e.clientX - b.left) / b.width, (e.clientY - b.top) / b.height]);
    });
    wrap.addEventListener('pointerleave', function () { queue(null); });
    return { reset: function () { queue(null); } };
  }

  window.OceanFX = { burst, tilt, reducedMotion: staticOnly };
})();
