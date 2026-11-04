// Browser test of the toolbar tools in the glass UI (React, served at /) against demo/tools_harness.py on port 8765:
//   python demo/tools_harness.py /tmp/dw     (keeps serving; then, in a second terminal)
//   node demo/glass_tools_test.js /tmp/dw
// Known truth: model buildings = 0.75 × true height, trees 12 m vs 18 m, sun 45° from 135°, town_after has blocks 1 and 3
// collapsed and one new building; the observed flood mask is the ground below +2.5 m.
const { chromium } = require('playwright');
const fs = require('fs');
const SP = process.argv[2], B = 'http://127.0.0.1:8765';
const results = [];
const check = (name, ok, info = '') => { results.push([ok ? 'PASS' : 'FAIL', name, info]); console.log(ok ? 'PASS' : 'FAIL', name, info); };
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1600, height: 950 }, deviceScaleFactor: 1, acceptDownloads: true });
  const errs = [];
  p.on('pageerror', e => errs.push(e.message + ' ' + (e.stack || '').split('\n')[1]));
  const ev = (f, a) => p.evaluate(f, a);
  const T = () => ev(() => __dw.tools.s);
  const go = async (page, scene = 'town_before') => {
    await p.goto(`${B}/#/${page}?scene=${scene}&view=2d&v2test=1`);
    await p.waitForFunction(() => window.__dw && __dw.data, null, { timeout: 30000 });
    if (await ev(() => __dw.s.current) !== scene) await p.selectOption('.scene-pick select', scene);   // the top bar's scene picker
    await p.waitForFunction(s => window.__dw && __dw.data && __dw.data.name === s && __dw.tools.T.los, scene, { timeout: 30000 });
    await p.waitForTimeout(400);
  };
  const on = async id => { if (!(await p.$eval(`#tool-${id} .switch`, e => e.checked))) await p.click(`#tool-${id} .switch`); await p.waitForTimeout(150); };
  const btn = (id, text) => p.locator(`#tool-${id} button`, { hasText: text }).first().click();
  const map = async () => p.$eval('.imgwrap', e => { const r = e.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; });
  const at = async (u, v) => { const m = await map(); await p.mouse.click(m[0] + u * m[2], m[1] + v * m[3]); };

  // ---------------- Explore ----------------
  await go('explore');
  const cards = await p.$$eval('.panel .card', cs => cs.map(c => c.id).filter(Boolean));
  check('Explore shows its tool cards, all switched off', ['tool-los', 'tool-vol', 'tool-drone', 'tool-solar', 'tool-wms', 'tool-mosaic'].every(id => cards.includes(id))
    && !(await ev(() => Object.values(__dw.tools.s.open).some(Boolean))), cards.join(','));

  await on('drone'); await btn('drone', 'Draw path');
  await at(0.1, 0.5); await at(0.5, 0.2); await at(0.9, 0.6);
  await btn('drone', 'Done');
  const dr = await ev(() => { const t = __dw.tools, D = t.T.drone, S = t.surfaceGrid(), W = __dw.data.meta.grid_w, H = __dw.data.meta.grid_h;
    const okAlt = D.wps.every(w => w.alt >= S[Math.min(H - 1, Math.floor(w.v * H)) * W + Math.min(W - 1, Math.floor(w.u * W))] + 30 - 1e-6);
    let plan = null; try { plan = JSON.parse(t.dronePlan()); } catch {}
    return { n: D.wps.length, okAlt, plan: plan && plan.mission.items.length, kml: t.droneKML().includes('<coordinates>') }; });
  check('drone plan drawn on the 2D map clears the surface', dr.n > 10 && dr.okAlt && dr.plan === dr.n + 2 && dr.kml, JSON.stringify(dr));
  const dl = p.waitForEvent('download'); await btn('drone', 'QGroundControl'); check('drone .plan download', (await dl).suggestedFilename().endsWith('.plan'));

  await on('los'); await at(0.5, 0.5); await p.waitForTimeout(200);
  const l1 = (await T()).los.seen;
  await p.locator('#tool-los label', { hasText: 'Observer height' }).locator('input').fill('200'); await p.waitForTimeout(500);
  const L = (await T()).los;
  check('line of sight: higher mast sees more', l1 > 0 && L.seen >= l1 && L.seen / L.inR > 0.95, `${l1}→${L.seen} of ${L.inR}`);

  await on('vol'); await p.locator('#tool-vol button', { hasText: 'Bare ground' }).click();
  for (const [u, v] of [[95, 95], [165, 95], [165, 145], [95, 145]]) await at(u / 800, v / 800);
  await btn('vol', 'Done');
  const V = (await T()).vol;
  check('volume of a 40×60 px, 18 m block ≈ 10 800 m³', V && Math.abs(V.above - 10800) / 10800 < 0.12, V && `${Math.round(V.above)} m³`);

  await on('solar'); await btn('solar', 'Calculate'); await p.waitForFunction(() => __dw.tools.s.solar, null, { timeout: 30000 });
  const so = await ev(() => { const r = __dw.tools.T.solar.res; return { n: r.length, ok: r.every(x => x.shade >= 0 && x.shade <= 1), max: Math.max(...r.map(x => x.kWh / (x.area * 0.7))) }; });
  check('rooftop solar: every roof, yield within physics', so.n === 8 && so.ok && so.max <= 285 + 1e-6, JSON.stringify(so));
  await on('mosaic');
  check('mosaic lists the georeferenced scenes', (await p.$$eval('#tool-mosaic input[type=checkbox]', e => e.length)) >= 3);
  await on('wms');
  check('map overlay ready for a GeoTIFF', await p.locator('#tool-wms button', { hasText: 'Load overlay' }).isEnabled());
  await p.screenshot({ path: `${SP}/glass_explore.png` });

  // ---------------- tool finder ----------------
  await p.keyboard.press('Control+k'); await p.waitForTimeout(150); await p.keyboard.type('shadow'); await p.keyboard.press('Enter');
  await p.waitForFunction(() => location.hash.startsWith('#/validate') && __dw.tools.s.open.shadow, null, { timeout: 10000 });
  check('Ctrl K finds "shadow", opens Validate with the tool on', true);
  check('leaving Explore switched its tools off', !(await ev(() => __dw.tools.s.open.los || __dw.tools.s.open.solar)));

  // ---------------- Validate ----------------
  await btn('shadow', 'Measure all buildings'); await p.waitForFunction(() => __dw.tools.s.shadow && __dw.tools.s.shadow.autoN != null, null, { timeout: 30000 });
  const sr = (await T()).shadow.ratio;
  check('shadow heights find the 0.75 under-estimate (×1.33)', sr && Math.abs(sr.k - 4 / 3) < 0.08, JSON.stringify(sr));
  await btn('shadow', 'Measure a shadow'); await at(230 / 800, 230 / 800); await at((230 - 12.7) / 800, (230 - 12.7) / 800); await btn('shadow', 'Done');
  const man = await ev(() => __dw.tools.T.shadow.meas[0]);
  check('manual shadow measure ≈ 9 m', man && Math.abs(man.H - 9) < 1.2, man && man.H.toFixed(2));

  await on('fix'); await btn('fix', 'Fit from ICESat-2'); await p.waitForFunction(() => __dw.tools.s.fixFit, null, { timeout: 30000 });
  check('ICESat-2 canopy fit ≈ ×1.5', Math.abs((await T()).fixFit.k - 1.5) < 0.05, JSON.stringify((await T()).fixFit));
  const before = await ev(() => __dw.data.buildings[0].height_m);
  await btn('shadow', 'for all buildings'); await p.waitForFunction(() => __dw.data.meta.class_scale, null, { timeout: 20000 }); await p.waitForTimeout(500);
  const fx = await ev(() => ({ h: __dw.data.buildings[0].height_m, k: __dw.data.meta.class_scale.buildings, t: __dw.data.meta.class_scale.trees }));
  check('applying the fix scales building heights (trees ×1.5 kept)', Math.abs(fx.h / before - fx.k) < 0.01 && Math.abs(fx.t - 1.5) < 0.05, JSON.stringify(fx));
  await btn('fix', 'Reset'); await p.waitForFunction(() => !__dw.data.meta.class_scale, null, { timeout: 20000 }); await p.waitForTimeout(300);
  check('reset restores model heights', Math.abs((await ev(() => __dw.data.buildings[0].height_m)) - before) < 1e-6);

  // GEDI check + canopy map (task 2): trees are 12 m in the model, 18 m in GEDI and in the canopy map
  await p.locator('.card button', { hasText: 'Check with GEDI' }).click(); await p.waitForFunction(() => __dw.s.val.gedi, null, { timeout: 30000 });
  const gd = await ev(() => __dw.s.val.gedi);
  check('GEDI check: ground right, model trees 6 m low, fit ×1.5', gd.ground.mae < 0.5 && Math.abs(gd.trees_model.bias + 6) < 0.5 && Math.abs(gd.tree_fit.k - 1.5) < 0.05,
    JSON.stringify({ shots: gd.shots, trees: gd.tree_shots, bias: gd.trees_model.bias, fit: gd.tree_fit }));
  check('GEDI results shown with map dots', (await p.textContent('.panel')).includes('model vs GEDI canopy top'));
  await p.locator('#tool-fix button', { hasText: 'Meta canopy map' }).click();
  await p.waitForFunction(() => __dw.data.meta.canopy && __dw.tools.s.fixTrees === 'canopy', null, { timeout: 30000 });
  const cpy = await ev(() => __dw.data.meta.canopy);
  check('canopy map loaded: trees 18 m vs model 12 m', cpy.canopy_median_m === 18 && cpy.model_median_m === 12, JSON.stringify(cpy));
  await btn('fix', 'Apply'); await p.waitForFunction(() => __dw.data.meta.class_scale && __dw.data.meta.class_scale.trees_source === 'canopy', null, { timeout: 20000 }); await p.waitForTimeout(400);
  const treeH = await ev(() => { const d = __dw.data, W = d.meta.grid_w, H = d.meta.grid_h; const i = Math.round(0.175 * H) * W + Math.round(0.64 * W); return [d.lc[i], d.grid[i]]; });
  check('trees take the canopy map heights in every view', treeH[0] === 4 && Math.abs(treeH[1] - 18) < 0.5, JSON.stringify(treeH));
  await p.locator('.card button', { hasText: 'Check with GEDI' }).click(); await p.waitForTimeout(300); await p.waitForFunction(() => !__dw.s.vbusy, null, { timeout: 30000 });
  check('after the canopy fix, trees match GEDI', Math.abs((await ev(() => __dw.s.val.gedi.trees_model.bias))) < 0.5, String(await ev(() => __dw.s.val.gedi.trees_model.bias)));
  await btn('fix', 'Reset'); await p.waitForFunction(() => !__dw.data.meta.class_scale, null, { timeout: 20000 }); await p.waitForTimeout(300);

  await p.locator('.card button', { hasText: 'Check with ICESat-2' }).click(); await p.waitForFunction(() => __dw.s.val.icesat2, null, { timeout: 30000 });
  await on('err'); await btn('err', 'Use these error bars'); await p.waitForFunction(() => __dw.data.meta.conformal, null, { timeout: 10000 });
  const chips = await p.textContent('.topbar .chips');
  check('calibrated error bars in read-outs and the top bar', (await ev(() => __dw.tools.pm(1))).includes('90%') && chips.includes('Error (90%)'), chips);
  await btn('err', 'Back to the consistency score'); await p.waitForFunction(() => !__dw.data.meta.conformal);

  fs.writeFileSync(`${SP}/gnss.csv`, 'name,lat,lon,alt\nP1,31.078,76.889,1043\nP2,31.0785,76.8895,1050\nFAR,10,70,5\n');
  await on('gnss'); await p.setInputFiles('#tool-gnss input[type=file]', `${SP}/gnss.csv`); await btn('gnss', 'Import file');
  await p.waitForFunction(() => __dw.data.gcpPts.length >= 2, null, { timeout: 10000 });
  const g = await ev(() => __dw.data.gcpPts.slice(-2).map(q => q.z));
  check('GNSS points become control points (ellipsoid → sea level)', g[0] === 1083 && g[1] === 1090, JSON.stringify(g));
  await ev(() => { __dw.data.gcpPts.length = 0; __dw.renderGcp(); });

  fs.writeFileSync(`${SP}/dem_test.tif`, Buffer.from(await (await fetch(`${B}/results/dem_test.tif`)).arrayBuffer()));
  await on('dem'); await p.setInputFiles('#tool-dem input[type=file]', `${SP}/dem_test.tif`); await btn('dem', 'Use this DEM');
  await p.waitForFunction(() => __dw.data && __dw.data.meta.terrain && __dw.data.meta.terrain.source.includes('dem_test'), null, { timeout: 30000 });
  check('uploaded DEM becomes the terrain source', true, await ev(() => __dw.data.meta.terrain.source));
  await p.waitForTimeout(500); await on('dem'); await btn('dem', 'Back to the default');
  await p.waitForFunction(() => __dw.data && __dw.data.meta.terrain && !__dw.data.meta.terrain.source.includes('dem_test'), null, { timeout: 30000 });
  check('"Back to the default" really restores the default terrain', true, await ev(() => __dw.data.meta.terrain.source));
  await p.screenshot({ path: `${SP}/glass_validate.png` });

  // ---------------- Prepare ----------------
  await go('prepare');
  await on('slide');
  const s1 = (await T()).slide;
  check('landslide risk classes every land cell', s1.total === await ev(() => __dw.data.grid.length - [...__dw.data.lc].filter(c => c === 5).length), JSON.stringify(s1.count));
  await p.locator('#tool-slide label', { hasText: 'Rain in 24 h' }).locator('input').fill('250'); await p.waitForTimeout(500);
  const s2 = (await T()).slide;
  check('heavier rain raises the risk', s2.count[2] + s2.count[3] >= s1.count[2] + s1.count[3] && s2.count[0] <= s1.count[0], JSON.stringify(s2.count));
  const pp = await ev(() => ({ t: __dw.tools.s.people.total, exp: __dw.data.buildings.reduce((a, b) => a + b.area_m2 * b.floors * 0.8 / 10, 0), groups: __dw.tools.s.people.groups.map(g => g.title) }));
  check('people at risk: residents formula, landslide group', Math.abs(pp.t - pp.exp) < 1e-6 && pp.groups.includes('Landslide risk'), JSON.stringify(pp));
  await p.screenshot({ path: `${SP}/glass_prepare.png` });

  // ---------------- Respond ----------------
  await go('respond');
  await p.locator('.card label.check', { hasText: 'Simulate flooding' }).locator('input').check();
  await ev(() => __dw.setDepth(14)); await p.waitForTimeout(300);
  check('flood card shows the people in flooded buildings', (await p.textContent('.panel')).includes('people live in buildings with water inside'));
  fs.writeFileSync(`${SP}/obsmask_test.tif`, Buffer.from(await (await fetch(`${B}/results/obsmask_test.tif`)).arrayBuffer()));
  await on('obs'); await p.setInputFiles('#tool-obs input[type=file]', `${SP}/obsmask_test.tif`); await btn('obs', 'Load & compare');
  await p.waitForFunction(() => __dw.tools.s.obs, null, { timeout: 20000 });
  await btn('obs', 'Fit the water level'); await p.waitForTimeout(500);
  const of = (await T()).obs.fit;
  check('observed flood: fitted level ≈ +2.5 m, CSI high', of && Math.abs(of.rise - 2.5) < 0.25 && of.csi > 0.9, JSON.stringify(of));
  const ob = (await T()).obs, exp = await ev(() => { const t = __dw.tools, d = __dw.data, c = t.blockCells(), r = t.blockRims(), g = t.T.obs.grid;
    return d.buildings.filter(b => c[b.id].some(i => g[i] > 0.5) || r[b.id].some(i => g[i] > 0.5)).length; });
  check('observed flood: buildings reached counted (card, people, report)', ob.hitB === exp && (await p.textContent('#tool-obs')).includes('Buildings the observed flood reached')
    && (await ev(() => __dw.tools.s.people.groups.some(g => g.title.startsWith('Observed flood')))), `${ob.hitB} buildings, ${Math.round(ob.hitPpl)} people`);
  await on('flow');
  check('flowing water switches the level flood off', !(await ev(() => __dw.s.flood)));
  await p.locator('#tool-flow label', { hasText: 'Simulate' }).locator('input').fill('0.25');
  await p.locator('#tool-flow label', { hasText: 'Inflow per point' }).locator('input').fill('20');
  await at(0.05, 0.5); await btn('flow', 'Done');
  await ev(() => __dw.tools.runFlow(true)); await p.waitForTimeout(300);
  const fl = await ev(() => { const F = __dw.tools.T.flow.sim, G = F.G, h = F.snaps.at(-1); let vol = 0; for (let c = 0; c < G.Nc; c++) vol += h[c] * G.dxc * G.dyc; return { vin: F.vin, vout: F.vout, vol, wet: h.filter(x => x > 0.1).length }; });
  check('flowing water conserves water (in = standing + out, ±5%)', fl.wet > 0 && Math.abs(fl.vin - fl.vol - fl.vout) / fl.vin < 0.05, JSON.stringify(fl));
  check('flowing water: time slider and 3D water surface', (await p.$$('#tool-flow input[type=range]')).length === 1 && await ev(() => __dw.water.visible));
  await p.screenshot({ path: `${SP}/glass_respond.png` });

  // ---------------- Relief ----------------
  await go('relief');
  await p.locator('.card label.check', { hasText: 'Simulate flooding' }).count();   // flood is off when entering a disaster page fresh
  await on('evac'); await p.locator('#tool-evac button', { hasText: 'Everyone' }).click(); await btn('evac', 'Make the plan');
  await p.waitForFunction(() => __dw.tools.s.evac && !__dw.tools.s.evac.busy, null, { timeout: 30000 });
  const E = (await T()).evac;
  check('evacuation: everyone placed, unreachable or over capacity', !E.error && E.n === 8 && Math.abs(E.load.reduce((a, b) => a + b, 0) + E.unreach + E.full - E.total) < 1e-6, JSON.stringify(E));
  await p.screenshot({ path: `${SP}/glass_relief.png` });

  // ---------------- Assess ----------------
  await go('assess', 'town_after');
  await on('dmg');
  check('damage picks the "before" scene by name', (await p.$eval('#tool-dmg select', e => e.value)) === 'town_before');
  await btn('dmg', 'Compare'); await p.waitForFunction(() => __dw.tools.s.dmg || __dw.tools.s.dmgMsg.startsWith('⚠'), null, { timeout: 30000 });
  const dm = (await T()).dmg;
  check('damage: 2 collapsed, 0 damaged, 1 new, canopy lost', dm && dm.col === 2 && dm.dam === 0 && dm.newN === 1 && dm.canopy.lost_m2 > 3000, JSON.stringify(dm && { col: dm.col, dam: dm.dam, newN: dm.newN }));
  const rep = await ev(() => __dw.tools.reportHTML());
  check('situation report includes the damage and people sections', rep.includes('Damage: before / after') && rep.includes('People at risk'));
  await p.screenshot({ path: `${SP}/glass_assess.png` });

  check('no page errors', errs.length === 0, errs.slice(0, 5).join(' | '));
  console.log(`\n${results.filter(r => r[0] === 'PASS').length}/${results.length} passed`);
  await b.close();
})().catch(e => { console.log('CRASH', e.message.split('\n').slice(0, 6).join('\n')); process.exit(1); });
