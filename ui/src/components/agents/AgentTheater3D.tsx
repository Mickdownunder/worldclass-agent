"use client";

import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

type EntryLike = {
  ts: string;
  from: string;
  to: string;
  plan: string;
  request?: string;
  command?: string;
  overall?: string;
};

type Props = {
  entries: EntryLike[];
};

type Pulse = {
  line: THREE.Line;
  orb: THREE.Mesh;
  from: THREE.Vector3;
  to: THREE.Vector3;
  t: number;
  speed: number;
};

type AgentId = "june" | "argus" | "atlas";

type Actor = {
  root: THREE.Object3D;
  materials: THREE.MeshStandardMaterial[];
};

type AgentCfg = {
  pos: THREE.Vector3;
  modelUrl: string;
  scale: number;
  animHint: RegExp;
  accent: number;
};

const AGENTS: Record<AgentId, AgentCfg> = {
  june: {
    pos: new THREE.Vector3(-4.7, 0, -1.4),
    modelUrl: "https://threejs.org/examples/models/gltf/RobotExpressive/RobotExpressive.glb",
    scale: 0.46,
    animHint: /idle|standing/i,
    accent: 0x4f89c5,
  },
  argus: {
    pos: new THREE.Vector3(0, 0, 3.9),
    modelUrl: "https://threejs.org/examples/models/gltf/Soldier.glb",
    scale: 1.05,
    animHint: /idle|standing/i,
    accent: 0xc78f4f,
  },
  atlas: {
    pos: new THREE.Vector3(4.7, 0, -1.4),
    modelUrl: "https://threejs.org/examples/models/gltf/RobotExpressive/RobotExpressive.glb",
    scale: 0.46,
    animHint: /idle|standing/i,
    accent: 0x5d9f78,
  },
};

function safeTime(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return ts;
  }
}

function shortText(v: string, max = 76): string {
  return v.length > max ? `${v.slice(0, max)}…` : v;
}

function commandText(e: EntryLike): string {
  if (e.command) return e.command;
  if (e.request) return e.request;
  return `${e.from} -> ${e.to} ${e.plan}`;
}

function makeBubbleSprite(text: string, accentHex: number, ts: string): THREE.Sprite {
  const canvas = document.createElement("canvas");
  canvas.width = 1040;
  canvas.height = 300;
  const ctx = canvas.getContext("2d");

  if (!ctx) {
    const fallback = new THREE.Sprite(new THREE.SpriteMaterial({ color: accentHex }));
    fallback.scale.set(5.8, 1.6, 1);
    return fallback;
  }

  const accent = `#${accentHex.toString(16).padStart(6, "0")}`;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "rgba(22, 27, 36, 0.92)";
  ctx.strokeStyle = "rgba(180, 190, 210, 0.55)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.roundRect(10, 10, canvas.width - 20, canvas.height - 20, 14);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = accent;
  ctx.font = "600 28px Inter, Segoe UI, Arial";
  ctx.fillText(`[${safeTime(ts)}]`, 28, 58);

  ctx.fillStyle = "#e6edf7";
  ctx.font = "500 27px Inter, Segoe UI, Arial";

  const words = shortText(text, 96).split(" ");
  const lines: string[] = [];
  let line = "";
  for (const w of words) {
    const next = line ? `${line} ${w}` : w;
    if (ctx.measureText(next).width > 970) {
      lines.push(line);
      line = w;
    } else {
      line = next;
    }
  }
  if (line) lines.push(line);

  lines.slice(0, 3).forEach((l, i) => {
    ctx.fillText(l, 28, 112 + i * 52);
  });

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;

  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false, depthWrite: false })
  );
  sprite.scale.set(6.2, 1.9, 1);
  return sprite;
}

function normalizeMaterials(root: THREE.Object3D): THREE.MeshStandardMaterial[] {
  const mats: THREE.MeshStandardMaterial[] = [];
  root.traverse((obj) => {
    const mesh = obj as THREE.Mesh;
    if (!mesh.isMesh || !mesh.material) return;

    const patch = (material: THREE.Material): THREE.MeshStandardMaterial => {
      const m = material.clone() as THREE.MeshStandardMaterial;
      m.transparent = false;
      m.opacity = 1;
      m.depthWrite = true;
      m.emissive = new THREE.Color(0x000000);
      m.emissiveIntensity = 0;
      mats.push(m);
      return m;
    };

    if (Array.isArray(mesh.material)) {
      mesh.material = mesh.material.map((m) => patch(m as THREE.Material));
    } else {
      mesh.material = patch(mesh.material as THREE.Material);
    }

    mesh.castShadow = true;
    mesh.receiveShadow = true;
  });
  return mats;
}

async function loadActor(
  loader: GLTFLoader,
  id: AgentId,
  scene: THREE.Scene,
  mixers: THREE.AnimationMixer[]
): Promise<Actor> {
  const cfg = AGENTS[id];

  const root = await new Promise<THREE.Object3D>((resolve) => {
    loader.load(
      cfg.modelUrl,
      (gltf) => {
        const model = gltf.scene.clone(true) as THREE.Object3D;
        model.scale.setScalar(cfg.scale);
        model.position.copy(cfg.pos);
        model.lookAt(0, 1.2, 0);

        if (gltf.animations.length > 0) {
          const mixer = new THREE.AnimationMixer(model);
          const clip = gltf.animations.find((a) => cfg.animHint.test(a.name)) ?? gltf.animations[0];
          mixer.clipAction(clip).play();
          mixers.push(mixer);
        }

        resolve(model);
      },
      undefined,
      () => {
        const fallback = new THREE.Mesh(
          new THREE.CapsuleGeometry(0.24, 0.92, 8, 12),
          new THREE.MeshStandardMaterial({ color: 0xb8c1cf, roughness: 0.35, metalness: 0.25 })
        );
        fallback.position.copy(cfg.pos).add(new THREE.Vector3(0, 1.14, 0));
        resolve(fallback);
      }
    );
  });

  const materials = normalizeMaterials(root);
  scene.add(root);

  const pedestal = new THREE.Mesh(
    new THREE.CylinderGeometry(1.2, 1.34, 0.28, 40),
    new THREE.MeshStandardMaterial({
      color: 0x202a35,
      roughness: 0.72,
      metalness: 0.1,
    })
  );
  pedestal.position.copy(cfg.pos).add(new THREE.Vector3(0, 0.14, 0));
  scene.add(pedestal);

  const rim = new THREE.Mesh(
    new THREE.TorusGeometry(1.44, 0.02, 10, 72),
    new THREE.MeshBasicMaterial({ color: cfg.accent, transparent: true, opacity: 0.48 })
  );
  rim.rotation.x = Math.PI / 2;
  rim.position.copy(cfg.pos).add(new THREE.Vector3(0, 0.02, 0));
  scene.add(rim);

  return { root, materials };
}

export default function AgentTheater3D({ entries }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const hostRef = useRef<HTMLDivElement | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const actorsRef = useRef<Record<string, Actor>>({});
  const pulsesRef = useRef<Pulse[]>([]);
  const bubbleRef = useRef<THREE.Sprite | null>(null);
  const mixersRef = useRef<THREE.AnimationMixer[]>([]);
  const frameRef = useRef<number | null>(null);
  const latestPulseKeyRef = useRef("");

  const newest = useMemo(() => entries[0] ?? null, [entries]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const host = hostRef.current;
    if (!canvas || !host) return;

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    const pulseStore = pulsesRef.current;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(host.clientWidth, host.clientHeight, false);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.shadowMap.enabled = false;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b121b);
    scene.fog = new THREE.Fog(0x0b121b, 14, 32);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(41, host.clientWidth / host.clientHeight, 0.1, 100);
    camera.position.set(0, 8.2, 12.0);
    camera.lookAt(0, 1.5, 0);

    scene.add(new THREE.HemisphereLight(0xaec6dd, 0x263445, 0.5));

    const key = new THREE.DirectionalLight(0xffffff, 0.72);
    key.position.set(3, 8.5, 5.2);
    scene.add(key);

    const fill = new THREE.PointLight(0x8fb3d6, 0.22, 26, 2);
    fill.position.set(-2, 4.2, -1);
    scene.add(fill);

    const floor = new THREE.Mesh(
      new THREE.CircleGeometry(6.8, 100),
      new THREE.MeshStandardMaterial({
        color: 0x1a2532,
        roughness: 0.84,
        metalness: 0.12,
      })
    );
    floor.rotation.x = -Math.PI / 2;
    scene.add(floor);

    const outerRing = new THREE.Mesh(
      new THREE.RingGeometry(6.82, 6.88, 100),
      new THREE.MeshBasicMaterial({ color: 0x8aa6c2, side: THREE.DoubleSide, transparent: true, opacity: 0.42 })
    );
    outerRing.rotation.x = -Math.PI / 2;
    outerRing.position.y = 0.02;
    scene.add(outerRing);

    const innerRing = new THREE.Mesh(
      new THREE.RingGeometry(3.2, 3.24, 76),
      new THREE.MeshBasicMaterial({ color: 0x708ca7, side: THREE.DoubleSide, transparent: true, opacity: 0.34 })
    );
    innerRing.rotation.x = -Math.PI / 2;
    innerRing.position.y = 0.02;
    scene.add(innerRing);

    const loader = new GLTFLoader();
    Promise.all([
      loadActor(loader, "june", scene, mixersRef.current),
      loadActor(loader, "argus", scene, mixersRef.current),
      loadActor(loader, "atlas", scene, mixersRef.current),
    ]).then((actors) => {
      actorsRef.current = {
        june: actors[0],
        argus: actors[1],
        atlas: actors[2],
      };
    });

    const clock = new THREE.Clock();

    const animate = () => {
      const dt = clock.getDelta();

      mixersRef.current.forEach((m) => m.update(dt));

      for (let i = pulseStore.length - 1; i >= 0; i -= 1) {
        const p = pulseStore[i];
        p.t += p.speed;
        p.orb.position.lerpVectors(p.from, p.to, p.t);
        const m = p.line.material as THREE.LineBasicMaterial;
        m.opacity = Math.max(0, 0.36 - p.t * 0.28);
        if (p.t >= 1) {
          scene.remove(p.line);
          scene.remove(p.orb);
          p.line.geometry.dispose();
          m.dispose();
          p.orb.geometry.dispose();
          (p.orb.material as THREE.MeshBasicMaterial).dispose();
          pulseStore.splice(i, 1);
        }
      }

      renderer.render(scene, camera);
      frameRef.current = requestAnimationFrame(animate);
    };
    frameRef.current = requestAnimationFrame(animate);

    const onResize = () => {
      const node = hostRef.current;
      if (!node) return;
      const w = node.clientWidth;
      const h = node.clientHeight;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
    };
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      if (frameRef.current) cancelAnimationFrame(frameRef.current);

      if (bubbleRef.current) {
        scene.remove(bubbleRef.current);
        const mat = bubbleRef.current.material as THREE.SpriteMaterial;
        mat.map?.dispose();
        mat.dispose();
      }

      pulseStore.forEach((p) => {
        p.line.geometry.dispose();
        (p.line.material as THREE.LineBasicMaterial).dispose();
        p.orb.geometry.dispose();
        (p.orb.material as THREE.MeshBasicMaterial).dispose();
      });

      Object.values(actorsRef.current).forEach((a) => {
        a.materials.forEach((m) => m.dispose());
      });

      renderer.dispose();
    };
  }, []);

  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene || !newest) return;

    const pulseKey = `${newest.ts}-${newest.from}-${newest.to}-${newest.plan}`;
    if (latestPulseKeyRef.current !== pulseKey) {
      latestPulseKeyRef.current = pulseKey;

      const fromCfg = AGENTS[newest.from as AgentId];
      const toCfg = AGENTS[newest.to as AgentId];
      if (fromCfg && toCfg) {
        const from = new THREE.Vector3(fromCfg.pos.x, 1.5, fromCfg.pos.z);
        const to = new THREE.Vector3(toCfg.pos.x, 1.5, toCfg.pos.z);

        const line = new THREE.Line(
          new THREE.BufferGeometry().setFromPoints([from, to]),
          new THREE.LineBasicMaterial({ color: fromCfg.accent, transparent: true, opacity: 0.36 })
        );
        const orb = new THREE.Mesh(
          new THREE.SphereGeometry(0.07, 10, 10),
          new THREE.MeshBasicMaterial({ color: fromCfg.accent })
        );
        orb.position.copy(from);

        scene.add(line);
        scene.add(orb);
        pulsesRef.current.push({ line, orb, from, to, t: 0, speed: 0.02 });
      }
    }

    if (bubbleRef.current) {
      scene.remove(bubbleRef.current);
      const m = bubbleRef.current.material as THREE.SpriteMaterial;
      m.map?.dispose();
      m.dispose();
      bubbleRef.current = null;
    }

    const fromId = (newest.from in AGENTS ? newest.from : "june") as AgentId;
    const cfg = AGENTS[fromId];
    const bubble = makeBubbleSprite(commandText(newest), cfg.accent, newest.ts);
    bubble.position.set(cfg.pos.x * 0.62, cfg.pos.y + 3.25, cfg.pos.z);
    scene.add(bubble);
    bubbleRef.current = bubble;
  }, [entries, newest]);

  return (
    <div
      className="relative overflow-hidden rounded-xl border"
      style={{ borderColor: "var(--tron-border)", minHeight: 560 }}
      ref={hostRef}
    >
      <canvas ref={canvasRef} className="block h-[560px] w-full" />

    </div>
  );
}
