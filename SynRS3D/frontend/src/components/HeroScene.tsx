import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { makeFloor, fitFloor, floorUniforms, Skirt, blockBase } from '../engine/block';

// The landing's fixed film: the terrain baked into public/hero (scripts/bake_hero.py) on its own renderer, flown by a slow,
// low drone orbit. Independent of the workspace engine and the scene library, so it is the same shot every time.

export interface HeroTerrain {
  name: string; n: number; width_m: number; height_m: number; base_m: number; peak_m: number;
  peak_uv: [number, number]; profile: number[]; profile_len_m: number;
}
const url = (f: string) => `${import.meta.env.BASE_URL}hero/${f}`;
// loaded once per page and shared by every mount (React's dev double-mount would otherwise race two identical downloads)
let assets: Promise<[HeroTerrain, ArrayBuffer, HTMLImageElement]> | null = null;
const loadAssets = () => assets ??= Promise.all([fetch(url('terrain.json')).then(r => r.json() as Promise<HeroTerrain>),
  fetch(url('terrain.f32')).then(r => r.arrayBuffer()), new THREE.ImageLoader().loadAsync(url('terrain.jpg'))]);

export default function HeroScene({ peak, onReady }: { peak: React.RefObject<HTMLElement | null>; onReady: (t: HeroTerrain) => void }) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = host.current!, still = matchMedia('(prefers-reduced-motion: reduce)');
    let raf = 0, alive = true, onScreen = true;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(2, devicePixelRatio)); renderer.setClearColor(0, 0);
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(42, 1, 1, 20000);
    scene.add(new THREE.HemisphereLight(0xffffff, 0x6b5a48, 1.7));
    const sun = new THREE.DirectionalLight(0xfff1e0, 1.5); sun.position.set(1, 1.6, -0.6); scene.add(sun);
    const floor = makeFloor(), skirt = new Skirt(), top = new THREE.Vector3(), ndc = new THREE.Vector3();
    scene.add(floor, skirt.mesh);
    let S = 0, relief = 0, mesh: THREE.Mesh<THREE.PlaneGeometry, THREE.MeshLambertMaterial> | null = null;
    const seen = new IntersectionObserver(e => { onScreen = e[0].isIntersecting; }); seen.observe(el);

    loadAssets().then(([t, buf, img]) => {
      if (!alive) return;
      const tex = new THREE.Texture(img); tex.needsUpdate = true;
      const h = new Float32Array(buf), n = t.n, W = t.width_m, H = t.height_m;
      tex.colorSpace = THREE.SRGBColorSpace; tex.anisotropy = 8;
      const geo = new THREE.PlaneGeometry(W, H, n - 1, n - 1).rotateX(-Math.PI / 2), pos = geo.attributes.position as THREE.BufferAttribute;
      for (let i = 0; i < pos.count; i++) pos.setY(i, h[i]);
      geo.computeVertexNormals();
      S = Math.max(W, H); relief = t.peak_m - t.base_m;
      const band = { value: Math.max(2, relief / 12) }, mat = new THREE.MeshLambertMaterial({ map: tex });
      // pencil contour lines on the surface, the same spacing as the strata on the sides
      mat.onBeforeCompile = sh => {
        sh.uniforms.band = band;
        sh.vertexShader = 'varying float vY;\n' + sh.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\nvY = position.y;');
        sh.fragmentShader = 'uniform float band;\nvarying float vY;\n' + sh.fragmentShader.replace('#include <map_fragment>',
          '#include <map_fragment>\nfloat dl = abs(fract(vY / band + 0.5) - 0.5) * band / fwidth(vY);\ndiffuseColor.rgb = mix(diffuseColor.rgb, vec3(1.0), 0.45 * (1.0 - smoothstep(0.4, 1.4, dl)));');
      };
      mesh = new THREE.Mesh(geo, mat); scene.add(mesh);
      const base = blockBase(S, relief);
      skirt.build(n, n); skirt.fit(pos, base, band.value);
      fitFloor(floor, W, H); floor.position.y = base - 0.05;
      const fu = floorUniforms(floor); fu.strength.value = 0.3; fu.reach.value = S * 2.6;
      scene.fog = new THREE.Fog(0xe2d6c6, S * 1.6, S * 4);
      const [pu, pv] = t.peak_uv, pi = Math.round(pv * (n - 1)) * n + Math.round(pu * (n - 1));
      top.set((pu - 0.5) * W, h[pi], (pv - 0.5) * H);
      el.classList.add('ready'); onReady(t);
    });

    const frame = () => {
      raf = requestAnimationFrame(frame);
      const w = el.clientWidth, ht = el.clientHeight;
      if (!onScreen || !mesh || !w || !ht) return;
      // wide screens: the model sits in the right half, a little above centre, clear of the headline and the cards
      // phones: further back and lifted above the title
      const wide = w > 860, sx = wide ? -Math.round(w * 0.22) : 0, sy = Math.round(ht * (wide ? 0.05 : 0.14));
      if (renderer.domElement.width !== Math.floor(w * renderer.getPixelRatio()) || camera.view?.offsetX !== sx) {
        renderer.setSize(w, ht); camera.aspect = w / ht; camera.setViewOffset(w, ht, sx, sy, w, ht); camera.updateProjectionMatrix();
      }
      const t = still.matches ? 8 : performance.now() / 1000, a = 0.6 + t * 0.045, r = S * (wide ? 2.1 : 3) * (1 - 0.04 * Math.sin(t * 0.09));
      camera.position.set(Math.sin(a) * r, S * 0.3 + relief * 0.9, Math.cos(a) * r);
      camera.lookAt(0, relief * 0.4, 0);
      renderer.render(scene, camera);
      if (peak.current) {   // the summit label rides on the projected peak
        ndc.copy(top).project(camera);
        peak.current.style.transform = `translate(${((ndc.x + 1) / 2 * w).toFixed(1)}px, ${((1 - ndc.y) / 2 * ht).toFixed(1)}px)`;
      }
    };
    frame();
    return () => {
      alive = false; cancelAnimationFrame(raf); seen.disconnect();
      mesh?.geometry.dispose(); mesh?.material.map?.dispose(); mesh?.material.dispose();
      skirt.mesh.geometry.dispose(); skirt.mesh.material.dispose(); floor.geometry.dispose(); (floor.material as THREE.Material).dispose();
      renderer.dispose(); renderer.domElement.remove();
    };
  }, []);
  return <div className="hero-3d" ref={host} aria-hidden="true" />;
}
