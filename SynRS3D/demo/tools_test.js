// Browser test of every toolbar tool (Playwright) against demo/tools_harness.py running on port 8765:
//   python demo/tools_harness.py /tmp/dw     (keeps serving; then, in a second terminal)
//   node demo/tools_test.js /tmp/dw
// Known truth: model buildings = 0.75 × true height, trees 12 m vs 18 m, sun 45° from 135°, town_after has blocks 1 and 3
// collapsed and one new building.
const { chromium } = require('playwright');
const fs = require('fs');
const SP = process.argv[2], B = 'http://127.0.0.1:8765';
const results = [];
const check = (name, ok, info = '') => { results.push([ok ? 'PASS' : 'FAIL', name, info]); console.log(ok ? 'PASS' : 'FAIL', name, info); };
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-unsafe-swiftshader'] });
  const p = await b.newPage({ viewport: { width: 1500, height: 900 }, deviceScaleFactor: 1, acceptDownloads: true });
  const errs = [];
  p.on('pageerror', e => errs.push(e.message + ' ' + (e.stack || '').split('\n')[1]));
  await p.goto(`${B}/classic#v2test-scene=town_before`);
  await p.waitForFunction(() => window.__dw && __dw.data && __dw.data.name === 'town_before' && __dw.T.los, null, { timeout: 30000 });
  const ev = (f, a) => p.evaluate(f, a);
  const visible = async sel => p.$eval(sel, e => !e.hidden && e.getBoundingClientRect().width > 0);

  // --- toolbar per mode
  const vis = await ev(() => [...document.querySelectorAll('#toolbar .tool[data-mode]')].filter(e => !e.hidden).map(e => e.dataset.mode));
  check('toolbar shows only Explore tools in Explore', vis.length === 6 && vis.every(m => m === 'explore'), vis.join(','));

  // --- tool finder: Ctrl+K, "drone", Enter
  await p.keyboard.press('Control+k'); await p.keyboard.type('drone'); await p.keyboard.press('Enter'); await p.waitForTimeout(300);
  check('Ctrl+K finder opens the drone tool', await visible('#dronecard'));
  await ev(() => __dw.setMode('validate')); await p.keyboard.press('Control+k'); await p.keyboard.type('landslide'); await p.keyboard.press('Enter'); await p.waitForTimeout(300);
  check('finder switches mode for a tool in another mode', await ev(() => !__dw.$('slidecard').hidden && document.querySelector('#modes .on').dataset.m === 'disaster'));
  await ev(() => __dw.setMode('explore'));

  // --- drone: draw a path on the 2D map
  await p.click('[data-tool=dronecard]');
  await p.click('#drdraw');
  const box = await p.$eval('#wrap', e => { const r = e.getBoundingClientRect(); return [r.x, r.y, r.width, r.height]; });
  const at = (u, v) => p.mouse.click(box[0] + u * box[2], box[1] + v * box[3]);
  await at(0.1, 0.5); await at(0.5, 0.2); await at(0.9, 0.6);
  await p.click('#drdraw');
  const dr = await ev(() => { const D = __dw.T.drone, S = __dw.surfaceGrid(), d = __dw.data, W = d.meta.grid_w;
    const okAlt = D.wps.every(w => w.alt >= S[Math.min(d.meta.grid_h - 1, Math.floor(w.v * d.meta.grid_h)) * W + Math.min(W - 1, Math.floor(w.u * W))] + 30 - 1e-6);
    let plan; try { plan = JSON.parse(__dw.dronePlan()); } catch { plan = null; }
    return { n: D.wps.length, len: D.len, okAlt, plan: plan && plan.mission.items.length, kml: __dw.droneKML().includes('<coordinates>'), csv: __dw.droneCSV().split('\n').length }; });
  check('drone plan: waypoints clear the surface by the clearance', dr.n > 10 && dr.okAlt, JSON.stringify(dr));
  check('drone exports: QGC plan, KML, CSV', dr.plan === dr.n + 2 && dr.kml && dr.csv === dr.n + 1);
  const dl = p.waitForEvent('download'); await p.click('#drplan'); check('drone .plan download', (await dl).suggestedFilename().endsWith('.plan'));

  // --- line of sight
  await p.click('[data-tool=loscard]'); await at(0.5, 0.5); await p.waitForTimeout(200);
  const los = await ev(() => { const L = __dw.T.los; return { seen: L.seen, inR: L.inR, obsVis: L.vis[L.obs[0]] }; });
  await ev(() => { __dw.$('losh').value = 200; __dw.computeLOS(); });
  const los2 = await ev(() => __dw.T.los.seen);
  check('line of sight: observer visible, higher mast sees more', los.obsVis === 2 && los.seen > 0 && los2 >= los.seen && los2 / los.inR > 0.95, `${los.seen}→${los2} of ${los.inR}`);
  await ev(() => { __dw.$('losh').value = 10; __dw.T.los.obs = []; __dw.computeLOS(); __dw.setPick(null); });

  // --- volume: outline around building 1 (rows 100-140, cols 100-160 of 800 px; model 18 m), against bare ground
  await p.click('[data-tool=volcard]');
  await p.selectOption('#volbase', 'ground');
  for (const [u, v] of [[95, 95], [165, 95], [165, 145], [95, 145]]) await at(u / 800, v / 800);
  await p.click('#voldraw');
  const vol = await ev(() => __dw.T.vol.res);
  check('volume of a 40×60 px, 18 m block ≈ 10 800 m³', Math.abs(vol.above - 10800) / 10800 < 0.12, `${Math.round(vol.above)} m³, area ${Math.round(vol.area)} m²`);

  // --- solar
  await p.click('[data-tool=solarcard]'); await p.click('#solrun'); await p.waitForFunction(() => __dw.T.solar, null, { timeout: 30000 });
  const sol = await ev(() => { const r = __dw.T.solar.res; return { n: r.length, okShade: r.every(x => x.shade >= 0 && x.shade <= 1), total: r.reduce((a, x) => a + x.kWh, 0),
    max: Math.max(...r.map(x => x.kWh / (x.area * 0.7))) }; });
  check('solar: every roof, yields within physics', sol.n === 8 && sol.okShade && sol.total > 0 && sol.max <= 1900 * 0.2 * 0.75 + 1e-6, JSON.stringify(sol));

  // --- mosaic + WMS cards render
  await p.click('[data-tool=mosaiccard]');
  check('mosaic lists georeferenced scenes', (await p.$$eval('#moslist input', e => e.length)) >= 3);
  await p.click('[data-tool=wmscard]');
  check('map overlay card ready', (await p.$eval('#wmsload', e => !e.disabled)));

  // --- report
  const rep = await ev(() => __dw.reportHTML());
  check('situation report contains the open tools', rep.includes('situation report') && rep.includes('Rooftop solar') && rep.includes('Line of sight'));

  // --- validate: shadows
  await ev(() => __dw.setMode('validate'));
  check('leaving Explore closes its tools', await ev(() => __dw.$('solarcard').hidden && __dw.$('dronecard').hidden));
  await p.click('[data-tool=shadowcard]'); await p.click('#shauto'); await p.waitForFunction(() => __dw.T.shadow.auto, null, { timeout: 30000 });
  const sh = await ev(() => ({ r: __dw.shadowRatio(), n: __dw.T.shadow.auto.length }));
  check('shadow heights find the 0.75 under-estimate (ratio ≈ 1.33)', sh.r && Math.abs(sh.r.k - 4 / 3) < 0.08, JSON.stringify(sh));
  // manual: building 4 (rows 230-270, cols 230-270, 9 m): its shadow runs 9 m = 18 px north-west from its corner
  await p.click('#shpick'); await at(230 / 800, 230 / 800); await at((230 - 12.7) / 800, (230 - 12.7) / 800); await p.click('#shpick');
  const man = await ev(() => __dw.T.shadow.meas[0]);
  check('manual shadow measure ≈ 9 m', man && Math.abs(man.H - 9) < 1.2, man && man.H.toFixed(2));

  // --- fixes: trees from ICESat-2, buildings from shadows
  await p.click('[data-tool=fixcard]'); await p.click('#fixfit'); await p.waitForFunction(() => __dw.T.fixFit, null, { timeout: 30000 });
  const tf = await ev(() => __dw.T.fixFit);
  check('ICESat-2 canopy fit ≈ ×1.5', Math.abs(tf.k - 1.5) < 0.05, JSON.stringify(tf));
  const before = await ev(() => __dw.data.buildings[0].height_m);
  await p.click('#shuse'); await p.waitForFunction(() => __dw.data.meta.class_scale, null, { timeout: 20000 }); await p.waitForTimeout(500);
  const fx = await ev(() => ({ h: __dw.data.buildings[0].height_m, k: __dw.data.meta.class_scale.buildings, t: __dw.data.meta.class_scale.trees }));
  check('applying the fix scales building heights', Math.abs(fx.h / before - fx.k) < 0.01 && Math.abs(fx.t - 1.5) < 0.05, JSON.stringify(fx));
  check('fixed-height download offered', await ev(() => !__dw.$('dl').querySelector('option[value="_height_fixed.tif"]').hidden));
  await p.click('#fixreset'); await p.waitForFunction(() => !__dw.data.meta.class_scale, null, { timeout: 20000 });
  check('reset restores model heights', Math.abs((await ev(() => __dw.data.buildings[0].height_m)) - before) < 1e-6);

  // --- calibrated error from the ICESat-2 check
  await p.click('#vice'); await p.waitForFunction(() => __dw.data.val.icesat2, null, { timeout: 30000 });
  await p.click('[data-tool=errcard]'); await p.click('#erruse'); await p.waitForFunction(() => __dw.data.meta.conformal, null, { timeout: 10000 });
  check('calibrated error bars shown in read-outs', (await ev(() => __dw.pm(1))).includes('(90 %)') && (await p.textContent('#stats')).includes('90 %'));
  await p.click('#erroff'); await p.waitForFunction(() => !__dw.data.meta.conformal);

  // --- GNSS import into control points
  fs.writeFileSync(`${SP}/gnss.csv`, 'name,lat,lon,alt\nP1,31.078,76.889,1043\nP2,31.0785,76.8895,1050\nFAR,10,70,5\n');
  const n0 = await ev(() => __dw.data.gcpPts.length);
  await p.setInputFiles('#gnssfile', `${SP}/gnss.csv`); await p.click('#gnssload'); await p.waitForFunction(n => __dw.data.gcpPts.length > n, n0, { timeout: 10000 });
  const g = await ev(() => __dw.data.gcpPts.slice(-2).map(q => q.z));
  check('GNSS points imported with ellipsoid → sea level (+40 m)', g[0] === 1083 && g[1] === 1090, JSON.stringify(g) + ' ' + await p.textContent('#gnssout'));
  await ev(() => { __dw.data.gcpPts.length = 0; });

  // --- user DEM
  const dem = Buffer.from(await (await fetch(`${B}/results/dem_test.tif`)).arrayBuffer()); fs.writeFileSync(`${SP}/dem_test.tif`, dem);
  await p.click('[data-tool=demcard]'); await p.setInputFiles('#demfile', `${SP}/dem_test.tif`); await p.click('#demuse');
  await p.waitForFunction(() => __dw.data && (__dw.data.meta.terrain || {}).source && __dw.data.meta.terrain.source.includes('dem_test'), null, { timeout: 30000 });
  check('uploaded DEM becomes the terrain source', true, await ev(() => __dw.data.meta.terrain.source));
  await ev(() => __dw.$('demreset').click()); await p.waitForFunction(() => __dw.data && __dw.data.meta.terrain && !__dw.data.meta.terrain.source.includes('dem_test'), null, { timeout: 30000 });

  // --- disaster: flood + people
  await ev(() => __dw.setMode('disaster')); await p.waitForTimeout(300);
  await p.click('label.tool:has(#flood)'); await ev(() => { __dw.$('depth').value = 14; __dw.updateFlood(); });
  await p.click('[data-tool=peoplecard]');
  const pp = await ev(() => ({ txt: __dw.$('ppout').textContent, total: __dw.data.buildings.reduce((a, b) => a + __dw.residents(b), 0),
    exp: __dw.data.buildings.reduce((a, b) => a + b.area_m2 * b.floors * 0.8 / 10, 0), row: __dw.$('floodcard').textContent.includes('People in buildings with water') }));
  check('people at risk: residents formula and flood row', Math.abs(pp.total - pp.exp) < 1e-6 && pp.txt.includes('Water inside') && pp.row, Math.round(pp.total));

  // --- evacuation (opens relief sites itself)
  await p.click('[data-tool=evaccard]'); await p.waitForTimeout(500);
  check('evacuation opens relief sites', await visible('#sitecard'));
  await ev(() => { __dw.$('depth').value = 1.5; __dw.updateFlood(); }); await p.selectOption('#evwho', 'all');
  await p.click('#evrun'); await p.waitForFunction(() => __dw.T.evac, null, { timeout: 30000 });
  const E = await ev(() => { const E = __dw.T.evac; return E.error ? E : { n: E.n, total: E.total, placed: E.load.reduce((a, b) => a + b, 0), un: E.unreach, full: E.full, cap: E.cap }; });
  check('evacuation: everyone placed, unreachable or over capacity; camps not overfilled', !E.error && E.n === 8 && E.placed > 0 && Math.abs(E.placed + E.un + E.full - E.total) < 1e-6 && E.placed <= E.cap.reduce((a, b) => a + b, 0) + 1e-6, JSON.stringify(E));

  // --- landslide
  await p.click('[data-tool=slidecard]');
  const sl = await ev(() => { const S = __dw.T.slide, d = __dw.data; return { count: S.count, n: d.grid.length, water: [...d.lc].filter(c => c === 5).length }; });
  check('landslide: every land cell classed', sl.count.reduce((a, b) => a + b, 0) === sl.n - sl.water, JSON.stringify(sl.count));
  await ev(() => { __dw.$('slrain').value = 250; __dw.$('slrain').oninput(); }); await p.waitForTimeout(500);
  const sl2 = await ev(() => __dw.T.slide.count);
  check('heavier rain raises the risk', sl2[2] + sl2[3] >= sl.count[2] + sl.count[3] && sl2[0] <= sl.count[0], JSON.stringify(sl2));

  // --- observed flood: mask = ground below +2.5 m; fit should find ≈ +2.5 m
  await p.click('[data-tool=obscard]');
  const mask = Buffer.from(await (await fetch(`${B}/results/obsmask_test.tif`)).arrayBuffer()); fs.writeFileSync(`${SP}/obsmask_test.tif`, mask);
  await p.setInputFiles('#obsfile', `${SP}/obsmask_test.tif`); await p.click('#obsrun'); await p.waitForFunction(() => __dw.T.obs && __dw.T.obs.grid, null, { timeout: 20000 });
  await p.click('#obsfit');
  const of = await ev(() => __dw.T.obs.fit);
  check('observed flood: fitted level ≈ +2.5 m, CSI high', Math.abs(of.rise - 2.5) < 0.25 && of.csi > 0.9, JSON.stringify(of));
  const db = Buffer.from(await (await fetch(`${B}/results/obsdb_test.tif`)).arrayBuffer()); fs.writeFileSync(`${SP}/obsdb_test.tif`, db);
  await p.setInputFiles('#obsfile', `${SP}/obsdb_test.tif`); await p.click('#obsrun'); await p.waitForFunction(() => __dw.T.obs && __dw.T.obs.res && __dw.T.obs.res.kind === 'db', null, { timeout: 20000 });
  const odb = await ev(() => __dw.T.obs.res);
  check('Sentinel-1 style dB image: water threshold found', odb.threshold_db > -19.5 && odb.threshold_db < -10, JSON.stringify(odb));

  // --- flowing water (turns the level flood off)
  await p.click('[data-tool=flowcard]');
  check('flowing water switches the level flood off', !(await ev(() => __dw.$('flood').checked)));
  await ev(() => { __dw.$('flhours').value = 0.25; __dw.$('flq').value = 20; });
  await at(0.05, 0.5); await p.click('#flpick');
  await ev(() => __dw.flowRun(true));
  const fl = await ev(() => { const F = __dw.T.flow.sim, G = F.G, h = F.snaps.at(-1); let vol = 0; for (let c = 0; c < G.Nc; c++) vol += h[c] * G.dxc * G.dyc;
    return { vin: F.vin, vout: F.vout, vol, wet: h.filter(x => x > 0.1).length, snaps: F.snaps.length, cells: `${G.Wc}x${G.Hc}` }; });
  check('flowing water: volume balance (in = standing + out, ±5 %)', fl.wet > 0 && Math.abs(fl.vin - fl.vol - fl.vout) / fl.vin < 0.05, JSON.stringify(fl));
  check('flowing water: 3D water surface shown', await ev(() => __dw.T.flow.cv && __dw.$('flout').textContent.includes('under water')));

  // --- damage: after scene vs before
  await ev(() => __dw.select('town_after')); await p.waitForFunction(() => __dw.data && __dw.data.name === 'town_after' && __dw.T.los, null, { timeout: 30000 });
  await ev(() => __dw.setMode('disaster'));
  if (await ev(() => __dw.$('dmgcard').hidden)) await p.click('[data-tool=dmgcard]');
  check('damage picks the "before" scene by name', (await p.$eval('#dmgbefore', e => e.value)) === 'town_before');
  await p.click('#dmgrun'); await p.waitForFunction(() => __dw.T.dmg && (__dw.T.dmg.cls || __dw.T.dmg.err), null, { timeout: 30000 });
  const dm = await ev(() => { const D = __dw.T.dmg; if (D.err) return D; const c = [...D.cls.values()]; return { col: c.filter(x => x === 'collapsed').length, dam: c.filter(x => x === 'damaged').length, new: D.res.new.length, shift: D.res.shift, canopy: D.res.canopy }; });
  check('damage: 2 collapsed, 0 damaged, 1 new, canopy lost', dm.col === 2 && dm.dam === 0 && dm.new === 1 && dm.canopy.lost_m2 > 3000, JSON.stringify(dm));

  // --- report with everything, the 3D view, palette downloads
  await p.click('#views [data-v=v3d]'); await p.waitForTimeout(1500);
  check('report includes the 3D view', (await ev(() => __dw.reportHTML())).includes('<h2>3D view</h2>'));
  await p.screenshot({ path: `${SP}/t_damage3d.png` });
  await p.click('#views [data-v=v2d]'); await p.waitForTimeout(500);
  await p.screenshot({ path: `${SP}/t_damage2d.png` });

  check('no page errors', errs.length === 0, errs.slice(0, 5).join(' | '));
  fs.writeFileSync(`${SP}/test_results.json`, JSON.stringify(results, null, 1));
  console.log(`\n${results.filter(r => r[0] === 'PASS').length}/${results.length} passed`);
  await b.close();
})().catch(e => { console.log('CRASH', e.message.split('\n').slice(0, 6).join('\n')); process.exit(1); });
