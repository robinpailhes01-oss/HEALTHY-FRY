// Capture la scène image par image et l'encode en vidéo.  node frames.js timeline.json sortie.mp4
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs'); const path = require('path');
(async () => {
  const T = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const out = process.argv[3]; const FPS = 30; const n = Math.round(T.total * FPS);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  await page.goto('file://' + path.join(__dirname, 'scene.html'));
  await page.evaluate(async () => { await document.fonts.ready; await Promise.all([...document.images].map((i) => i.decode())); });
  await page.evaluate((t) => window.setup(t), T);
  const ff = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-',
    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '16', '-pix_fmt', 'yuv420p', out], { stdio: ['pipe', 'inherit', 'inherit'] });
  for (let i = 0; i < n; i++) {
    await page.evaluate((t) => window.render(t), i / FPS);
    const buf = await page.screenshot({ type: 'jpeg', quality: 92 });
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
    if (i % 90 === 0) process.stdout.write(`  ${i}/${n}\n`);
  }
  ff.stdin.end(); await new Promise((r) => ff.on('close', r)); await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
