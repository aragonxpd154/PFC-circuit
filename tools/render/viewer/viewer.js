// Visualizador 3D das placas PSH-CARD1 / PSH-JIG1 (three.js)
//
// Modelo: STEP exportado pelo KiCad (modelos 3D reais dos componentes),
// tesselado em GLB pelo OpenCascade. As faces da placa recebem texturas
// geradas a partir dos Gerbers (cobre, máscara, serigrafia, furos).
//
// Coordenadas glTF: x = x_KiCad, z = y_KiCad, y = altura (topo da placa em 1,6 mm).
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

const T = 1.6; // espessura da placa (mm)

async function loadBoard(b, loader, texLoader) {
  // GLB embutido (data:) é decodificado direto — sem fetch (funciona sob CSP restritiva e offline)
  let gltf;
  if (b.glb.startsWith("data:")) {
    const bin = atob(b.glb.slice(b.glb.indexOf(",") + 1));
    const buf = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
    gltf = await loader.parseAsync(buf.buffer, "");
  } else {
    gltf = await loader.loadAsync(b.glb);
  }
  const g = new THREE.Group();
  const model = gltf.scene;
  model.traverse((o) => {
    if (o.isMesh) {
      o.castShadow = true;
      o.receiveShadow = true;
      const m = o.material;
      if (m && m.isMeshStandardMaterial) {
        m.roughness = Math.min(0.75, Math.max(0.35, m.roughness));
        m.envMapIntensity = 0.55;
      }
    }
  });
  g.add(model);

  const face = (url, top) => {
    const tex = texLoader.load(url);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 8;
    if (!top) { tex.center.set(0.5, 0.5); tex.rotation = Math.PI; }
    const mat = new THREE.MeshStandardMaterial({
      map: tex, transparent: true, alphaTest: 0.5, roughness: 0.5, metalness: 0.0, envMapIntensity: 0.5,
      polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2,
    });
    const mesh = new THREE.Mesh(new THREE.PlaneGeometry(b.w, b.h), mat);
    mesh.rotation.x = top ? -Math.PI / 2 : Math.PI / 2;
    mesh.position.set(b.w / 2, top ? T + 0.015 : -0.015, b.h / 2);
    mesh.receiveShadow = true;
    return mesh;
  };
  g.add(face(b.top, true));
  g.add(face(b.bottom, false));
  return g;
}

export async function createViewer(container, boards, opts = {}) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(opts.pixelRatio || Math.min(2, window.devicePixelRatio || 1));
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NoToneMapping;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(renderer), 0.04).texture;

  const camera = new THREE.PerspectiveCamera(30, container.clientWidth / container.clientHeight, 1, 2000);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;

  const sun = new THREE.DirectionalLight(0xffffff, 1.25);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.radius = 6;
  sun.shadow.bias = -0.0004;
  scene.add(sun);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 0.25));

  const ground = new THREE.Mesh(new THREE.PlaneGeometry(600, 600),
    new THREE.ShadowMaterial({ opacity: 0.22 }));
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);

  const loader = new GLTFLoader();
  const texLoader = new THREE.TextureLoader();
  const groups = {};
  for (const b of boards) groups[b.id] = await loadBoard(b, loader, texLoader);

  // Montagem: PSH-CARD1 em pé no soquete J1 da PSH-JIG1 (pino n ↔ pino n)
  const assembly = new THREE.Group();
  if (groups.card && groups.jig) {
    const jig = groups.jig.clone();
    const card = groups.card.clone();
    // (x_c, y_c, z_c) → (63 − z_c, 9,3 + x_c, 12,92 − y_c)
    //   pino n da barra 90° (z_c = 29,43 − 2,54·(n−1), eixo a 2,92 mm) → furo n do soquete (x = 33,57 + 2,54·(n−1), z = 10)
    card.matrixAutoUpdate = false;
    card.matrix.set(0, 0, -1, 63.0,
                    1, 0, 0, 9.3,
                    0, -1, 0, 12.92,
                    0, 0, 0, 1);
    assembly.add(jig, card);
  }
  groups.assembly = assembly;

  const VIEWS = {
    card: { group: "card", target: [24, 1, 18], pos: [-22, 52, 78], ground: -6 },
    "card-top": { group: "card", target: [25, 0, 18], pos: [25, 95, 18.01], ground: -6 },
    "card-bottom": { group: "card", target: [25, 0, 18], pos: [25, -95, 18.01], ground: -200 },
    jig: { group: "jig", target: [45, 0, 31], pos: [-22, 104, 160], ground: -6 },
    assembly: { group: "assembly", target: [44, 20, 30], pos: [-70, 118, 196], ground: -6 },
  };

  let current = null;
  function show(name) {
    const v = VIEWS[name];
    if (current) scene.remove(current);
    current = groups[v.group];
    scene.add(current);
    controls.target.set(...v.target);
    camera.position.set(...v.pos);
    camera.up.set(0, 1, 0);
    if (name === "card-top") camera.up.set(0, 0, -1);
    if (name === "card-bottom") camera.up.set(0, 0, -1);
    ground.position.y = v.ground;
    sun.position.set(v.target[0] - 60, 140, v.target[2] + 80);
    sun.target.position.set(...v.target);
    scene.add(sun.target);
    const s = sun.shadow.camera;
    s.left = -90; s.right = 90; s.top = 90; s.bottom = -90; s.near = 1; s.far = 400;
    s.updateProjectionMatrix();
    controls.update();
  }

  function resize() {
    const w = container.clientWidth, h = container.clientHeight;
    renderer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  window.addEventListener("resize", resize);

  renderer.setAnimationLoop(() => {
    controls.update();
    renderer.render(scene, camera);
  });

  return {
    show, resize, renderer,
    stop: () => renderer.setAnimationLoop(null),
    renderOnce: () => { controls.update(); renderer.render(scene, camera); },
  };
}

window.PFC3D = { createViewer };
