// Gera docs/3d/viewer.html autocontido (three.js + GLB + texturas embutidos)
// Uso: node build.mjs <raiz_do_repo> <node_modules_dir>
import { build } from "esbuild";
import fs from "node:fs";
import path from "node:path";

const [rootArg, nm] = process.argv.slice(2);
const root = path.resolve(rootArg);
const here = path.dirname(new URL(import.meta.url).pathname);
const res = await build({
  entryPoints: [path.join(here, "viewer.js")], bundle: true, minify: true, format: "iife",
  write: false, nodePaths: [nm], legalComments: "none",
});
const b64 = (f, mime) => `data:${mime};base64,${fs.readFileSync(f).toString("base64")}`;
const boards = [
  { id: "card", w: 50, h: 36, glb: b64(`${root}/docs/3d/psh-card1.glb`, "model/gltf-binary"),
    top: b64(`${root}/build/tex/psh-card1-top.png`, "image/png"), bottom: b64(`${root}/build/tex/psh-card1-bottom.png`, "image/png") },
  { id: "jig", w: 90, h: 60, glb: b64(`${root}/docs/3d/psh-jig1.glb`, "model/gltf-binary"),
    top: b64(`${root}/build/tex/psh-jig1-top.png`, "image/png"), bottom: b64(`${root}/build/tex/psh-jig1-bottom.png`, "image/png") },
];
let html = fs.readFileSync(path.join(here, "template.html"), "utf8");
html = html.replace("/*BOARDS*/", () => JSON.stringify(boards)).replace("/*BUNDLE*/", () => res.outputFiles[0].text);
fs.writeFileSync(`${root}/docs/3d/viewer.html`, html);
console.log(`✓ docs/3d/viewer.html (${(html.length / 1e6).toFixed(1)} MB)`);
