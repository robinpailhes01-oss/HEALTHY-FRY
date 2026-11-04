// Rend les overlays Healthy Fry (PNG transparents 1080x1920) à partir d'une liste de specs JSON.
// Usage : node overlays.js specs.json
// specs.json = [{ "type": "hook|ingredients|etape|resultat|cta", "out": "chemin.png", "data": {...} }]
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const FONT_DIR = path.join(__dirname, 'fonts');
const font = (f) => fs.readFileSync(path.join(FONT_DIR, f)).toString('base64');

const C = {
  creme: '#F4EFE4',
  vert: '#2E5E3A',
  vertClair: '#6BAF6E',
  texte: '#1F3A26',
};

const esc = (s = '') => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const BASE_CSS = `
@font-face { font-family: P; font-weight: 600; src: url(data:font/ttf;base64,${font('Poppins-600.ttf')}); }
@font-face { font-family: P; font-weight: 800; src: url(data:font/ttf;base64,${font('Poppins-800.ttf')}); }
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { width: 1080px; height: 1920px; background: transparent; font-family: P, 'Noto Color Emoji', sans-serif; color: ${C.texte}; }
.abs { position: absolute; }
.card { background: ${C.creme}; border-radius: 44px; box-shadow: 0 18px 50px rgba(0,0,0,.28); }
.pill { background: ${C.vert}; color: #fff; border-radius: 999px; font-weight: 800; }
.badge { background: ${C.creme}; color: ${C.vert}; border: 5px solid ${C.vert}; border-radius: 999px; font-weight: 800; }
.handle { right: 150px; top: 170px; font-size: 30px; font-weight: 600; color: #fff; background: rgba(46,94,58,.75); padding: 8px 22px; border-radius: 999px; }
`;

const handle = (d) => (d.handle ? `<div class="abs handle">${esc(d.handle)}</div>` : '');

const T = {
  hook: (d) => `
    <div class="abs card" style="left:70px; right:70px; top:230px; padding:46px 50px; text-align:center;">
      <div style="font-weight:800; font-size:${d.taille || 74}px; line-height:1.12; color:${C.vert};">${esc(d.titre)}</div>
      ${d.sous_titre ? `<div style="font-weight:600; font-size:40px; margin-top:18px;">${esc(d.sous_titre)}</div>` : ''}
    </div>
    ${d.badge ? `<div class="abs badge" style="left:50%; transform:translateX(-50%); top:${d.badgeTop || 640}px; font-size:44px; padding:14px 40px; white-space:nowrap;">${esc(d.badge)}</div>` : ''}`,

  ingredients: (d) => `
    <div class="abs card" style="left:90px; right:90px; top:300px; padding:44px 54px 50px;">
      <div class="pill" style="display:inline-block; font-size:44px; padding:12px 38px; margin-bottom:26px;">${esc(d.titre || 'Ingrédients')}</div>
      ${(d.liste || []).map((i) => `<div style="font-weight:600; font-size:42px; line-height:1.55; display:flex; gap:18px;"><span style="color:${C.vertClair}">●</span><span>${esc(i)}</span></div>`).join('')}
    </div>`,

  etape: (d) => `
    <div class="abs" style="left:70px; right:150px; top:240px; display:flex; align-items:center; gap:0;">
      <div style="flex:none; width:118px; height:118px; border-radius:50%; background:${C.creme}; color:${C.vert}; border:6px solid ${C.vert}; font-weight:800; font-size:66px; display:flex; align-items:center; justify-content:center; z-index:2;">${esc(d.num)}</div>
      <div class="pill" style="margin-left:-30px; padding:22px 40px 22px 54px; font-size:46px; line-height:1.2; box-shadow:0 14px 40px rgba(0,0,0,.25);">${esc(d.texte)}</div>
    </div>
    ${d.badge ? `<div class="abs badge" style="left:70px; top:400px; font-size:42px; padding:10px 34px;">${esc(d.badge)}</div>` : ''}`,

  resultat: (d) => `
    <div class="abs pill" style="left:50%; transform:translateX(-50%); top:250px; font-size:58px; padding:20px 54px; white-space:nowrap; box-shadow:0 14px 40px rgba(0,0,0,.25);">${esc(d.titre || 'Résultat')}</div>
    ${d.macros ? `<div class="abs badge" style="left:50%; transform:translateX(-50%); top:400px; font-size:42px; padding:12px 36px; white-space:nowrap;">${esc(d.macros)}</div>` : ''}`,

  cta: (d) => `
    <div class="abs card" style="left:90px; right:90px; top:520px; padding:60px 50px; text-align:center;">
      <div style="font-weight:800; font-size:68px; line-height:1.15; color:${C.vert};">${esc(d.titre || 'Enregistre la recette')}</div>
      <div style="font-weight:600; font-size:42px; margin-top:24px; line-height:1.35;">${esc(d.texte || 'Abonne-toi pour une recette Airfryer chaque jour')}</div>
      ${d.handle ? `<div class="pill" style="display:inline-block; margin-top:34px; font-size:44px; padding:14px 44px;">${esc(d.handle)}</div>` : ''}
    </div>`,

  vide: () => '',
};

(async () => {
  const specs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  for (const s of specs) {
    const tpl = T[s.type] || T.vide;
    const showHandle = s.type !== 'cta';
    await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>${BASE_CSS}</style></head><body>${tpl(s.data || {})}${showHandle ? handle(s.data || {}) : ''}</body></html>`);
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: s.out, omitBackground: true });
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
