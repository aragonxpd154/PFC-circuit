// Renderiza imagens do visualizador 3D (Chromium headless + WebGL)
// Uso: node shoot.mjs <raiz_do_repo>
import { createRequire } from "node:module";
const { chromium } = createRequire(import.meta.url)("playwright");
import path from "node:path";
const root = path.resolve(process.argv[2]);
const shots = [
  ["card", "psh-card1-3d.png", 1600, 1000],
  ["card-top", "psh-card1-3d-top.png", 1600, 1150],
  ["jig", "psh-jig1-3d.png", 1600, 1000],
  ["assembly", "psh-assembly-3d.png", 1600, 1000],
];
const browser = await chromium.launch({ args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] });
const only = process.argv[3];
for (const [view, file, w, h] of shots) {
  if (only && only !== view) continue;
  const page = await browser.newPage({ viewport: { width: w, height: h + 118 }, deviceScaleFactor: 1 });
  page.on("console", (m) => { if (m.type() === "error") console.log("console:", m.text().slice(0, 200)); });
  page.on("pageerror", (e) => console.log("pageerror:", e.message));
  await page.goto(`file://${root}/docs/3d/viewer.html?view=${view}`);
  await page.waitForFunction(() => window.__ready === true, null, { timeout: 400000 });
  await page.waitForTimeout(4000);
  // remove a interface e renderiza só o canvas com fundo transparente
  await page.evaluate(() => {
    document.querySelector("header").style.display = "none";
    document.querySelector("footer").style.display = "none";
    document.body.style.background = "transparent";
    document.documentElement.style.background = "transparent";
    const st = document.getElementById("stage"); st.style.inset = "0";
    window.__viewer.stop(); window.__viewer.resize(); window.__viewer.renderOnce();
  });
  await page.waitForTimeout(1500);
  await page.setViewportSize({ width: w, height: h });
  await page.evaluate(() => { window.__viewer.resize(); window.__viewer.renderOnce(); });
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${root}/docs/images/${file}`, omitBackground: true, timeout: 300000 });
  console.log("✓", file);
  await page.close();
}
await browser.close();
