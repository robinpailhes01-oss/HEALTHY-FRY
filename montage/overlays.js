// Rend les overlays animés Healthy Fry (séquences PNG transparentes 1080x1920 + fichier ffconcat).
// Usage : node overlays.js specs.json
// specs.json = [{ "type": "hook|ingredients|etape|resultat|cta|vide", "prefix": "/tmp/x/ov_00",
//                 "duree": 6.2, "reveal": [0.8, 1.6, ...], "data": {...} }]
// Sortie pour chaque spec : <prefix>.ffconcat (+ PNG). Les animations CSS sont échantillonnées à 30 i/s
// uniquement pendant qu'elles bougent ; le reste du temps, l'image est tenue (rendu rapide).
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const FPS = 30;
const FONT_DIR = path.join(__dirname, 'fonts');
const font = (f) => fs.readFileSync(path.join(FONT_DIR, f)).toString('base64');
const C = { creme: '#F4EFE4', vert: '#2E5E3A', vertClair: '#6BAF6E', texte: '#1F3A26' };
const esc = (s = '') => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const d = (s) => `animation-delay:${(+s || 0).toFixed(3)}s;`;

const CSS = `
@font-face { font-family: P; font-weight: 600; src: url(data:font/ttf;base64,${font('Poppins-600.ttf')}); }
@font-face { font-family: P; font-weight: 800; src: url(data:font/ttf;base64,${font('Poppins-800.ttf')}); }
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { width: 1080px; height: 1920px; background: transparent; font-family: P, 'Noto Color Emoji', sans-serif; color: ${C.texte}; overflow: hidden; }
.abs { position: absolute; }
.row { position: absolute; left: 0; right: 0; display: flex; justify-content: center; }
.card { background: ${C.creme}; border-radius: 44px; box-shadow: 0 18px 50px rgba(0,0,0,.30); }
.pill { background: ${C.vert}; color: #fff; border-radius: 999px; font-weight: 800; }
.badge { background: ${C.creme}; color: ${C.vert}; border: 5px solid ${C.vert}; border-radius: 999px; font-weight: 800; white-space: nowrap; box-shadow: 0 10px 30px rgba(0,0,0,.22); }
.handle { right: 150px; top: 170px; font-size: 30px; font-weight: 600; color: #fff; background: rgba(46,94,58,.78); padding: 8px 22px; border-radius: 999px; }
.pop   { animation: pop .42s cubic-bezier(.2,1.5,.4,1) both; }
.punch { animation: punch .35s cubic-bezier(.2,.9,.3,1) both; }
.slide { animation: slide .38s cubic-bezier(.2,1.2,.4,1) both; }
.item  { animation: item .32s cubic-bezier(.2,1.4,.4,1) both; }
@keyframes pop   { from { opacity: 0; transform: scale(.55); } to { opacity: 1; transform: scale(1); } }
@keyframes punch { from { transform: scale(1.18); } to { transform: scale(1); } }
@keyframes slide { from { opacity: 0; transform: translateX(-160px); } to { opacity: 1; transform: none; } }
@keyframes item  { from { opacity: 0; transform: translateX(-40px) scale(.9); } to { opacity: 1; transform: none; } }
`;

const T = {
  hook: (x) => `
    <div class="abs card punch" style="left:70px; right:70px; top:230px; padding:46px 50px; text-align:center;">
      <div style="font-weight:800; font-size:${x.taille || 76}px; line-height:1.1; color:${C.vert};">${esc(x.titre)}</div>
      ${x.sous_titre ? `<div style="font-weight:600; font-size:40px; margin-top:16px;">${esc(x.sous_titre)}</div>` : ''}
    </div>
    ${x.badge ? `<div class="row" style="top:${x.badgeTop || 650}px;"><div class="badge pop" style="font-size:46px; padding:14px 42px; ${d(0.35)}">${esc(x.badge)}</div></div>` : ''}`,

  ingredients: (x, rv) => `
    <div class="abs card pop" style="left:90px; right:90px; top:300px; padding:44px 54px 50px; transform-origin: top center;">
      <div class="pill" style="display:inline-block; font-size:44px; padding:12px 38px; margin-bottom:26px;">${esc(x.titre || 'Ingrédients')}</div>
      ${(x.liste || []).map((i, k) => `<div class="item" style="font-weight:600; font-size:42px; line-height:1.55; display:flex; gap:18px; ${d(rv[k] ?? 0.3 + k * 0.4)}"><span style="color:${C.vertClair}">●</span><span>${esc(i)}</span></div>`).join('')}
    </div>`,

  etape: (x) => `
    <div class="abs" style="left:70px; right:150px; top:240px; display:flex; align-items:center;">
      <div class="pop" style="flex:none; width:118px; height:118px; border-radius:50%; background:${C.creme}; color:${C.vert}; border:6px solid ${C.vert}; font-weight:800; font-size:66px; display:flex; align-items:center; justify-content:center; z-index:2;">${esc(x.num)}</div>
      <div class="pill slide" style="margin-left:-30px; padding:22px 40px 22px 54px; font-size:46px; line-height:1.2; box-shadow:0 14px 40px rgba(0,0,0,.25); ${d(0.12)}">${esc(x.texte)}</div>
    </div>
    ${x.badge ? `<div class="abs badge pop" style="left:70px; top:400px; font-size:44px; padding:10px 34px; ${d(x.badgeDelay ?? 0.5)}">${esc(x.badge)}</div>` : ''}`,

  resultat: (x) => `
    <div class="row" style="top:250px;"><div class="pill pop" style="font-size:60px; padding:20px 56px; white-space:nowrap; box-shadow:0 14px 40px rgba(0,0,0,.25);">${esc(x.titre || 'Résultat')}</div></div>
    ${x.macros ? `<div class="row" style="top:405px;"><div class="badge pop" style="font-size:42px; padding:12px 36px; ${d(0.35)}">${esc(x.macros)}</div></div>` : ''}`,

  cta: (x) => `
    <div class="abs card pop" style="left:90px; right:90px; top:520px; padding:60px 50px; text-align:center;">
      <div style="font-weight:800; font-size:66px; line-height:1.15; color:${C.vert};">${esc(x.titre || 'Enregistre la recette')}</div>
      <div style="font-weight:600; font-size:42px; margin-top:24px; line-height:1.35;">${esc(x.texte || '')}</div>
      ${x.handle ? `<div class="pill pop" style="display:inline-block; margin-top:34px; font-size:44px; padding:14px 44px; ${d(0.3)}">${esc(x.handle)}</div>` : ''}
    </div>`,

  vide: () => '',
};

(async () => {
  const specs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  for (const s of specs) {
    const x = s.data || {};
    const tpl = T[s.type] || T.vide;
    const handle = s.type !== 'cta' && x.handle ? `<div class="abs handle">${esc(x.handle)}</div>` : '';
    await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>${CSS}</style></head><body>${tpl(x, s.reveal || [])}${handle}</body></html>`);
    await page.evaluate(() => document.fonts.ready);

    // instants à échantillonner : pendant chaque animation, à 30 i/s
    const spans = await page.evaluate(() => document.getAnimations().map((a) => {
      a.pause();
      const t = a.effect.getComputedTiming();
      return [t.delay / 1000, (t.delay + t.activeDuration) / 1000];
    }));
    const duree = Math.max(s.duree || 1, 0.1);
    const set = new Set([0]);
    for (const [a, b] of spans) {
      for (let t = a; t <= b + 1e-6; t += 1 / FPS) if (t < duree) set.add(Math.round(t * FPS) / FPS);
      if (b < duree) set.add(Math.round(b * FPS) / FPS + 1 / FPS);
    }
    const times = [...set].filter((t) => t < duree).sort((a, b) => a - b);

    const lines = ['ffconcat version 1.0'];
    for (let i = 0; i < times.length; i++) {
      const t = times[i];
      await page.evaluate((ms) => document.getAnimations().forEach((a) => { a.currentTime = ms; }), t * 1000);
      const png = `${s.prefix}_${String(i).padStart(3, '0')}.png`;
      await page.screenshot({ path: png, omitBackground: true });
      const dur = (i + 1 < times.length ? times[i + 1] : duree) - t;
      lines.push(`file '${png}'`, `duration ${dur.toFixed(4)}`);
    }
    lines.push(`file '${s.prefix}_${String(times.length - 1).padStart(3, '0')}.png'`);
    fs.writeFileSync(`${s.prefix}.ffconcat`, lines.join('\n') + '\n');
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
