import * as THREE from 'three';

// A scene drawn as a model on a table, shared by the workspace (Engine) and the landing hero (HeroScene):
// a grid floor that fades into the CSS sky behind the canvas, with a soft contact shadow under the scene,
// and soil-coloured sides from the surface edge down to a base, banded with contour strata.

export function makeFloor() {
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(1, 1).rotateX(-Math.PI / 2), new THREE.ShaderMaterial({
    transparent: true, depthWrite: false,
    uniforms: { tint: { value: new THREE.Color(0x8a6a4a) }, cell: { value: 50 }, reach: { value: 2000 }, strength: { value: 0.6 }, foot: { value: new THREE.Vector2(1, 1) } },
    vertexShader: 'varying vec2 vXZ; void main() { vec4 w = modelMatrix * vec4(position, 1.0); vXZ = w.xz; gl_Position = projectionMatrix * viewMatrix * w; }',
    fragmentShader: `uniform vec3 tint; uniform vec2 foot; uniform float cell, reach, strength; varying vec2 vXZ;
      float lines(vec2 p) { vec2 g = abs(fract(p - 0.5) - 0.5) / fwidth(p); return 1.0 - min(min(g.x, g.y), 1.0); }
      void main() {
        float r = length(vXZ), ring = abs(fract(r / (cell * 4.0) - 0.5) - 0.5) / fwidth(r / (cell * 4.0));
        float a = lines(vXZ / cell) * 0.22 + lines(vXZ / (cell * 5.0)) * 0.34 + (1.0 - min(ring, 1.0)) * 0.16;
        float la = strength * a * (1.0 - smoothstep(reach * 0.15, reach, r));
        vec2 q = abs(vXZ) - foot; float d = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0);   // distance to the scene's footprint
        float sh = 0.32 * (1.0 - smoothstep(0.0, max(foot.x, foot.y) * 0.6, d));               // soft contact shadow under the block
        gl_FragColor = vec4(mix(tint, vec3(0.06, 0.13, 0.19), sh / max(sh + la, 1e-4)), max(la, sh));
      }`,
  }));
  floor.renderOrder = -1; floor.frustumCulled = false; floor.raycast = () => {};
  return floor;
}
export const floorUniforms = (floor: THREE.Mesh) => (floor.material as THREE.ShaderMaterial).uniforms;
/** Size the floor for a W × H m scene: tiles 12 scenes wide, cell size a round number, shadow footprint W × H. */
export function fitFloor(floor: THREE.Mesh, W: number, H: number) {
  const span = Math.max(W, H), u = floorUniforms(floor);
  floor.scale.set(span * 12, 1, span * 12);
  u.cell.value = [10, 25, 50, 100, 250].find(c => c >= span / 12) ?? 500; u.foot.value.set(W / 2, H / 2);
}

export class Skirt {
  mesh = new THREE.Mesh(new THREE.BufferGeometry(), new THREE.MeshLambertMaterial({ vertexColors: true, side: THREE.DoubleSide, emissive: 0x241c14 }));
  private band = { value: 5 };
  private ring = new Uint32Array(0);   // grid indices around the scene's edge, in order
  constructor() {
    this.mesh.raycast = () => {};
    this.mesh.material.onBeforeCompile = sh => {
      sh.uniforms.band = this.band;
      sh.vertexShader = 'varying float vY;\n' + sh.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\nvY = position.y;');
      sh.fragmentShader = 'uniform float band;\nvarying float vY;\n' + sh.fragmentShader.replace('#include <color_fragment>',
        '#include <color_fragment>\nfloat dl = abs(fract(vY / band + 0.5) - 0.5) * band / fwidth(vY);\ndiffuseColor.rgb *= mix(0.78, 1.0, smoothstep(0.5, 1.5, dl));');
    };
  }
  /** Topology for a PlaneGeometry of gw × gh vertices (vertex (x, y) is index y * gw + x). */
  build(gw: number, gh: number) {
    const ring: number[] = [];
    for (let x = 0; x < gw; x++) ring.push(x);
    for (let y = 1; y < gh; y++) ring.push(y * gw + gw - 1);
    for (let x = gw - 2; x >= 0; x--) ring.push((gh - 1) * gw + x);
    for (let y = gh - 2; y > 0; y--) ring.push(y * gw);
    const n = ring.length, g = new THREE.BufferGeometry(), col = new Float32Array(n * 6), idx: number[] = [];
    for (let k = 0; k < n; k++) { col.set([0.36, 0.27, 0.19, 0.8, 0.71, 0.57], k * 6); const j = (k + 1) % n; idx.push(2 * k, 2 * k + 1, 2 * j, 2 * j, 2 * k + 1, 2 * j + 1); }
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(n * 6), 3));
    g.setAttribute('color', new THREE.BufferAttribute(col, 3)); g.setIndex(idx);
    this.mesh.geometry.dispose(); this.mesh.geometry = g; this.ring = Uint32Array.from(ring);
  }
  /** Follow the surface's current heights down to `base`; strata every `band` m. */
  fit(surface: THREE.BufferAttribute, base: number, band: number) {
    const sp = this.mesh.geometry.attributes.position as THREE.BufferAttribute;
    for (let j = 0; j < this.ring.length; j++) {
      const i = this.ring[j];
      sp.setXYZ(2 * j, surface.getX(i), surface.getY(i), surface.getZ(i)); sp.setXYZ(2 * j + 1, surface.getX(i), base, surface.getZ(i));
    }
    sp.needsUpdate = true; this.mesh.geometry.computeVertexNormals(); this.mesh.geometry.computeBoundingSphere();
    this.band.value = band;
  }
}
/** Depth of the block below the lowest ground: enough to read as solid, more for hilly scenes. */
export const blockBase = (span: number, relief: number) => -Math.max(span * 0.03, relief * 0.12);
