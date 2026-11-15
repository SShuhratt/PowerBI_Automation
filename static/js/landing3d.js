/* ==========================================================================
   AutoBI Studio - 3D Data Analytics & Engineering Landing Visualizations
   Pure high-DPI 3D perspective engine supporting Dark & Light themes,
   interactive drag-orbit, camera presets, Star Schema topology,
   and morphing multi-domain 3D telemetry cubes.
   ========================================================================== */

(function () {
    const prefersReducedMotion =
        window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    function getThemeMode() {
        if (window.autobiTheme && typeof window.autobiTheme.getTheme === 'function') {
            return window.autobiTheme.getTheme();
        }
        return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
    }

    function t(key, vars) {
        if (window.autobiI18n && typeof window.autobiI18n.t === 'function') {
            return window.autobiI18n.t(key, vars);
        }
        return key;
    }

    function getPalettes(mode) {
        if (mode === 'light') {
            return {
                bgTop: '#f8faff',
                bgBottom: '#eef3fb',
                gridLine: 'rgba(79, 70, 229, 0.11)',
                gridAxis: 'rgba(79, 70, 229, 0.25)',
                ambientGlow1: 'rgba(99, 102, 241, 0.14)',
                ambientGlow2: 'rgba(6, 182, 212, 0.12)',
                ambientGlow3: 'rgba(16, 185, 129, 0.11)',
                labelBg: 'rgba(255, 255, 255, 0.90)',
                labelBorder: 'rgba(79, 70, 229, 0.28)',
                labelText: '#0f172a',
                subText: '#475569',
                raw: { top: '#fb923c', left: '#ea580c', right: '#c2410c', edge: 'rgba(194, 65, 12, 0.7)' },
                etl: { top: '#38bdf8', left: '#0284c7', right: '#0369a1', edge: 'rgba(2, 132, 199, 0.85)' },
                indigo: { top: '#818cf8', left: '#4f46e5', right: '#3730a3', edge: 'rgba(67, 56, 202, 0.75)' },
                emerald: { top: '#34d399', left: '#059669', right: '#047857', edge: 'rgba(4, 120, 87, 0.75)' },
                cyan: { top: '#22d3ee', left: '#0891b2', right: '#0e7490', edge: 'rgba(14, 116, 144, 0.75)' },
                rose: { top: '#fb7185', left: '#e11d48', right: '#be123c', edge: 'rgba(190, 18, 60, 0.75)' },
                spline: 'rgba(79, 70, 229, 0.34)',
                ringStroke: 'rgba(8, 145, 178, 0.55)',
                ringAlt: 'rgba(79, 70, 229, 0.45)',
                beam: 'rgba(16, 185, 129, 0.55)',
            };
        }
        return {
            bgTop: '#0b1120',
            bgBottom: '#060a14',
            gridLine: 'rgba(99, 102, 241, 0.14)',
            gridAxis: 'rgba(56, 189, 248, 0.30)',
            ambientGlow1: 'rgba(99, 102, 241, 0.22)',
            ambientGlow2: 'rgba(6, 182, 212, 0.16)',
            ambientGlow3: 'rgba(16, 185, 129, 0.14)',
            labelBg: 'rgba(15, 23, 42, 0.86)',
            labelBorder: 'rgba(129, 140, 248, 0.40)',
            labelText: '#f8fafc',
            subText: '#94a3b8',
            raw: { top: '#fbbf24', left: '#d97706', right: '#92400e', edge: 'rgba(253, 230, 138, 0.65)' },
            etl: { top: '#67e8f9', left: '#06b6d4', right: '#0e7490', edge: 'rgba(165, 243, 252, 0.75)' },
            indigo: { top: '#a5b4fc', left: '#6366f1', right: '#3730a3', edge: 'rgba(199, 210, 254, 0.75)' },
            emerald: { top: '#6ee7b7', left: '#10b981', right: '#065f46', edge: 'rgba(167, 243, 208, 0.78)' },
            cyan: { top: '#38bdf8', left: '#0284c7', right: '#075985', edge: 'rgba(186, 230, 253, 0.72)' },
            rose: { top: '#fda4af', left: '#f43f5e', right: '#9f1239', edge: 'rgba(254, 205, 211, 0.72)' },
            spline: 'rgba(129, 140, 248, 0.42)',
            ringStroke: 'rgba(34, 211, 238, 0.62)',
            ringAlt: 'rgba(129, 140, 248, 0.50)',
            beam: 'rgba(52, 211, 153, 0.58)',
        };
    }

    // 3D math & projection helpers
    function rotatePoint(x, y, z, yaw, pitch) {
        const cy = Math.cos(yaw);
        const sy = Math.sin(yaw);
        const x1 = x * cy - z * sy;
        const z1 = x * sy + z * cy;

        const cp = Math.cos(pitch);
        const sp = Math.sin(pitch);
        const y2 = y * cp - z1 * sp;
        const z2 = y * sp + z1 * cp;

        return { x: x1, y: y2, z: z2 };
    }

    function projectPoint(rx, ry, rz, cam) {
        const zAdj = rz + cam.dist;
        if (zAdj <= 0.4) return null;
        const factor = (cam.fov / zAdj) * cam.scale;
        return {
            x: cam.cx + (rx - cam.panX) * factor,
            y: cam.cy - (ry - cam.panY) * factor,
            z: zAdj,
            s: factor,
        };
    }

    function lerp(a, b, k) {
        return a + (b - a) * k;
    }

    function drawRoundedTag(ctx, x, y, text, pal, align = 'center') {
        ctx.save();
        ctx.font = '600 11px Inter, system-ui, sans-serif';
        const metrics = ctx.measureText(text);
        const padX = 9;
        const w = metrics.width + padX * 2;
        const h = 22;
        let rx = x - w / 2;
        if (align === 'left') rx = x;
        const ry = y - h / 2;

        ctx.fillStyle = pal.labelBg;
        ctx.strokeStyle = pal.labelBorder;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.roundRect(rx, ry, w, h, 7);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = pal.labelText;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(text, rx + w / 2, ry + h / 2 + 0.5);
        ctx.restore();
    }

    function buildBoxFaces(cx, cy, cz, w, h, d, shade, yaw, pitch, cam, localRotY = 0) {
        const hw = w / 2;
        const hh = h / 2;
        const hd = d / 2;
        const localVerts = [
            [-hw, -hh, -hd],
            [hw, -hh, -hd],
            [hw, hh, -hd],
            [-hw, hh, -hd],
            [-hw, -hh, hd],
            [hw, -hh, hd],
            [hw, hh, hd],
            [-hw, hh, hd],
        ];

        const cl = Math.cos(localRotY);
        const sl = Math.sin(localRotY);
        const projVerts = [];

        for (let i = 0; i < localVerts.length; i++) {
            const lx = localVerts[i][0];
            const ly = localVerts[i][1];
            const lz = localVerts[i][2];
            const wx = cx + (lx * cl - lz * sl);
            const wy = cy + ly;
            const wz = cz + (lx * sl + lz * cl);
            const r = rotatePoint(wx, wy, wz, yaw, pitch);
            const p = projectPoint(r.x, r.y, r.z, cam);
            if (!p) return [];
            projVerts.push(p);
        }

        const facesDef = [
            { idx: [3, 2, 6, 7], color: shade.top },   // +Y top
            { idx: [4, 5, 6, 7], color: shade.left },  // +Z front
            { idx: [1, 5, 6, 2], color: shade.right }, // +X right
            { idx: [0, 3, 7, 4], color: shade.right }, // -X left
            { idx: [0, 1, 2, 3], color: shade.left },  // -Z back
            { idx: [0, 4, 5, 1], color: shade.right }, // -Y bottom
        ];

        const out = [];
        for (let f = 0; f < facesDef.length; f++) {
            const def = facesDef[f];
            const p0 = projVerts[def.idx[0]];
            const p1 = projVerts[def.idx[1]];
            const p2 = projVerts[def.idx[2]];
            const p3 = projVerts[def.idx[3]];
            // Backface test via 2D winding order
            const cross = (p1.x - p0.x) * (p2.y - p0.y) - (p1.y - p0.y) * (p2.x - p0.x);
            if (cross >= 0) continue;
            const depth = (p0.z + p1.z + p2.z + p3.z) * 0.25;
            out.push({
                kind: 'poly',
                pts: [p0, p1, p2, p3],
                fill: def.color,
                stroke: shade.edge,
                depth,
            });
        }
        return out;
    }

    function sizeCanvas(canvas) {
        const rect = canvas.getBoundingClientRect();
        if (rect.width < 10 || rect.height < 10) return null;
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const targetW = Math.round(rect.width * dpr);
        const targetH = Math.round(rect.height * dpr);
        if (canvas.width !== targetW || canvas.height !== targetH) {
            canvas.width = targetW;
            canvas.height = targetH;
        }
        return { width: rect.width, height: rect.height, dpr };
    }

    function drawBackground(ctx, w, h, pal) {
        const bg = ctx.createLinearGradient(0, 0, 0, h);
        bg.addColorStop(0, pal.bgTop);
        bg.addColorStop(1, pal.bgBottom);
        ctx.fillStyle = bg;
        ctx.fillRect(0, 0, w, h);

        const g1 = ctx.createRadialGradient(w * 0.22, h * 0.35, 10, w * 0.22, h * 0.35, w * 0.45);
        g1.addColorStop(0, pal.ambientGlow1);
        g1.addColorStop(1, 'transparent');
        ctx.fillStyle = g1;
        ctx.fillRect(0, 0, w, h);

        const g2 = ctx.createRadialGradient(w * 0.78, h * 0.32, 10, w * 0.78, h * 0.32, w * 0.42);
        g2.addColorStop(0, pal.ambientGlow2);
        g2.addColorStop(1, 'transparent');
        ctx.fillStyle = g2;
        ctx.fillRect(0, 0, w, h);

        const g3 = ctx.createRadialGradient(w * 0.52, h * 0.72, 10, w * 0.52, h * 0.72, w * 0.38);
        g3.addColorStop(0, pal.ambientGlow3);
        g3.addColorStop(1, 'transparent');
        ctx.fillStyle = g3;
        ctx.fillRect(0, 0, w, h);
    }

    // =========================================================================
    // 1. Hero 3D Data Engineering & Analytics Pipeline Stage
    // =========================================================================
    function initHero3D() {
        const canvas = document.getElementById('hero3dCanvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const CAM_PRESETS = {
            all: { yaw: 0.38, pitch: 0.34, dist: 10.6, panX: 0, panY: 0.1 },
            etl: { yaw: -0.18, pitch: 0.28, dist: 8.6, panX: -1.15, panY: 0.15 },
            cube: { yaw: 0.62, pitch: 0.42, dist: 8.4, panX: 1.95, panY: 0.35 },
            schema: { yaw: -0.45, pitch: 0.48, dist: 9.2, panX: 0.9, panY: 0.2 },
        };

        let activePreset = 'all';
        let targetYaw = CAM_PRESETS.all.yaw;
        let targetPitch = CAM_PRESETS.all.pitch;
        let targetDist = CAM_PRESETS.all.dist;
        let targetPanX = CAM_PRESETS.all.panX;
        let targetPanY = CAM_PRESETS.all.panY;

        let yaw = targetYaw;
        let pitch = targetPitch;
        let dist = targetDist;
        let panX = targetPanX;
        let panY = targetPanY;

        let dragging = false;
        let lastX = 0;
        let lastY = 0;
        let hoverTiltX = 0;
        let hoverTiltY = 0;
        let userOrbited = false;
        let phase = 0;
        let isVisible = true;
        let rafId = null;

        // Preset buttons
        document.querySelectorAll('.cam-preset-btn[data-cam]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const mode = btn.getAttribute('data-cam') || 'all';
                if (!CAM_PRESETS[mode]) return;
                activePreset = mode;
                userOrbited = false;
                const p = CAM_PRESETS[mode];
                targetYaw = p.yaw;
                targetPitch = p.pitch;
                targetDist = p.dist;
                targetPanX = p.panX;
                targetPanY = p.panY;
                document.querySelectorAll('.cam-preset-btn[data-cam]').forEach((b) => {
                    const on = b === btn;
                    b.classList.toggle('active', on);
                    b.setAttribute('aria-pressed', on ? 'true' : 'false');
                });
                if (prefersReducedMotion) renderFrame(0);
            });
        });

        canvas.addEventListener('pointerdown', (e) => {
            dragging = true;
            userOrbited = true;
            lastX = e.clientX;
            lastY = e.clientY;
            canvas.setPointerCapture && canvas.setPointerCapture(e.pointerId);
        });

        canvas.addEventListener('pointermove', (e) => {
            const rect = canvas.getBoundingClientRect();
            const nx = ((e.clientX - rect.left) / Math.max(rect.width, 1)) * 2 - 1;
            const ny = ((e.clientY - rect.top) / Math.max(rect.height, 1)) * 2 - 1;
            hoverTiltX = nx * 0.08;
            hoverTiltY = ny * 0.06;

            if (!dragging) return;
            const dx = e.clientX - lastX;
            const dy = e.clientY - lastY;
            lastX = e.clientX;
            lastY = e.clientY;
            targetYaw += dx * 0.008;
            targetPitch = Math.max(-0.15, Math.min(0.88, targetPitch + dy * 0.007));
        });

        const endDrag = () => { dragging = false; };
        canvas.addEventListener('pointerup', endDrag);
        canvas.addEventListener('pointercancel', endDrag);
        canvas.addEventListener('pointerleave', () => {
            dragging = false;
            hoverTiltX = 0;
            hoverTiltY = 0;
        });

        // Pre-seeded streaming packets along 3 spline lanes
        const packets = [];
        for (let lane = 0; lane < 3; lane++) {
            for (let j = 0; j < 6; j++) {
                packets.push({
                    lane,
                    offset: (j / 6) + lane * 0.11,
                    speed: 0.0038 + lane * 0.0005,
                });
            }
        }

        function evalPipelineSpline(tNorm, lane, time) {
            const x = lerp(-3.1, 2.25, tNorm);
            const laneY = (lane - 1) * 0.42;
            const y = Math.sin(tNorm * Math.PI * 2 + lane) * 0.22 + laneY * (1 - Math.abs(tNorm - 0.5) * 0.55) + 0.15;
            const z = Math.cos(tNorm * Math.PI * 1.5 + lane * 1.4 + time * 0.4) * (lane === 1 ? 0.15 : 0.48);
            return { x, y, z };
        }

        function renderFrame(dt) {
            const dims = sizeCanvas(canvas);
            if (!dims) return;
            const { width, height, dpr } = dims;
            const pal = getPalettes(getThemeMode());

            if (!prefersReducedMotion) {
                phase += dt * 0.016;
            }

            const effYawTarget = userOrbited
                ? targetYaw + hoverTiltX
                : targetYaw + Math.sin(phase * 0.42) * 0.16 + hoverTiltX;
            const effPitchTarget = targetPitch + hoverTiltY;

            yaw = lerp(yaw, effYawTarget, 0.08);
            pitch = lerp(pitch, effPitchTarget, 0.08);
            dist = lerp(dist, targetDist, 0.08);
            panX = lerp(panX, targetPanX, 0.08);
            panY = lerp(panY, targetPanY, 0.08);

            ctx.save();
            ctx.scale(dpr, dpr);
            drawBackground(ctx, width, height, pal);

            const cam = {
                cx: width * 0.5,
                cy: height * 0.54,
                fov: 7.4,
                dist,
                scale: Math.min(width, height) * 0.132,
                panX,
                panY,
            };

            // 1. 3D Perspective Floor Grid (Warehouse Base Plane y = -1.15)
            ctx.lineWidth = 1;
            const gridY = -1.15;
            for (let gx = -4; gx <= 4; gx += 0.8) {
                const a = rotatePoint(gx, gridY, -3.2, yaw, pitch);
                const b = rotatePoint(gx, gridY, 3.2, yaw, pitch);
                const pa = projectPoint(a.x, a.y, a.z, cam);
                const pb = projectPoint(b.x, b.y, b.z, cam);
                if (pa && pb) {
                    ctx.strokeStyle = Math.abs(gx) < 0.1 ? pal.gridAxis : pal.gridLine;
                    ctx.beginPath();
                    ctx.moveTo(pa.x, pa.y);
                    ctx.lineTo(pb.x, pb.y);
                    ctx.stroke();
                }
            }
            for (let gz = -3.2; gz <= 3.2; gz += 0.8) {
                const a = rotatePoint(-4, gridY, gz, yaw, pitch);
                const b = rotatePoint(4, gridY, gz, yaw, pitch);
                const pa = projectPoint(a.x, a.y, a.z, cam);
                const pb = projectPoint(b.x, b.y, b.z, cam);
                if (pa && pb) {
                    ctx.strokeStyle = Math.abs(gz) < 0.1 ? pal.gridAxis : pal.gridLine;
                    ctx.beginPath();
                    ctx.moveTo(pa.x, pa.y);
                    ctx.lineTo(pb.x, pb.y);
                    ctx.stroke();
                }
            }

            // 2. ETL Bezier Splines (backdrop conduits)
            for (let lane = 0; lane < 3; lane++) {
                ctx.strokeStyle = pal.spline;
                ctx.lineWidth = 1.6;
                ctx.beginPath();
                let started = false;
                for (let s = 0; s <= 28; s++) {
                    const pt = evalPipelineSpline(s / 28, lane, phase);
                    const r = rotatePoint(pt.x, pt.y, pt.z, yaw, pitch);
                    const p = projectPoint(r.x, r.y, r.z, cam);
                    if (!p) continue;
                    if (!started) {
                        ctx.moveTo(p.x, p.y);
                        started = true;
                    } else {
                        ctx.lineTo(p.x, p.y);
                    }
                }
                ctx.stroke();
            }

            // 3. Collect all depth-sorted primitives (3D solids, packets, rings)
            const queue = [];

            // Stage A (-X): Raw Messy Ingestion Spreadsheet Cubes
            const rawSpecs = [
                { x: -3.25, y: 0.45, z: -0.65, w: 0.54, h: 0.54, d: 0.54, shade: pal.raw, spd: 0.55 },
                { x: -2.95, y: -0.32, z: 0.72, w: 0.46, h: 0.46, d: 0.46, shade: pal.rose, spd: -0.7 },
                { x: -2.55, y: 0.78, z: 0.25, w: 0.40, h: 0.40, d: 0.40, shade: pal.raw, spd: 0.85 },
            ];
            rawSpecs.forEach((c, idx) => {
                const floatY = c.y + Math.sin(phase * 1.4 + idx * 1.3) * 0.12;
                const faces = buildBoxFaces(
                    c.x, floatY, c.z, c.w, c.h, c.d, c.shade, yaw, pitch, cam,
                    phase * c.spd + idx
                );
                queue.push(...faces);
            });

            // Stage B (Center): Counter-Rotating Self-Healing ETL Octagonal Rings
            const ringConfigs = [
                { radius: 1.12, tilt: 0.28, dir: 1, color: pal.ringStroke, x: -0.35 },
                { radius: 0.84, tilt: -0.35, dir: -1.4, color: pal.ringAlt, x: -0.35 },
            ];
            ringConfigs.forEach((rc) => {
                const segs = 16;
                const pts = [];
                let depthSum = 0;
                for (let i = 0; i <= segs; i++) {
                    const ang = (i / segs) * Math.PI * 2 + phase * 0.65 * rc.dir;
                    const ly = Math.cos(ang) * rc.radius;
                    const lz = Math.sin(ang) * rc.radius;
                    const wx = rc.x + Math.sin(ang + rc.tilt) * 0.25;
                    const r = rotatePoint(wx, ly + 0.15, lz, yaw, pitch);
                    const p = projectPoint(r.x, r.y, r.z, cam);
                    if (p) {
                        pts.push(p);
                        depthSum += p.z;
                    }
                }
                if (pts.length > 2) {
                    queue.push({
                        kind: 'ring',
                        pts,
                        color: rc.color,
                        depth: depthSum / pts.length,
                    });
                }
            });

            // Flowing Data Packets (transforming dirty -> clean across x = -0.35)
            packets.forEach((pk) => {
                const prog = (pk.offset + phase * pk.speed * 18) % 1;
                const pt = evalPipelineSpline(prog, pk.lane, phase);
                const r = rotatePoint(pt.x, pt.y, pt.z, yaw, pitch);
                const p = projectPoint(r.x, r.y, r.z, cam);
                if (!p) return;
                const healed = prog > 0.52;
                queue.push({
                    kind: 'dot',
                    x: p.x,
                    y: p.y,
                    radius: Math.max(2.6, p.s * 0.065),
                    color: healed ? (pk.lane === 1 ? pal.emerald.top : pal.etl.top) : pal.raw.top,
                    depth: p.z,
                });
            });

            // Stage C (+X): 3D Animated Analytics Bar Cluster (6 KPI Prisms on platform)
            const baseHeights = [0.85, 1.38, 1.12, 1.85, 1.56, 2.24];
            const barShades = [pal.indigo, pal.cyan, pal.indigo, pal.emerald, pal.cyan, pal.emerald];
            // Platform slab under bars
            queue.push(...buildBoxFaces(2.15, -1.04, 0.0, 2.55, 0.18, 1.75, pal.indigo, yaw, pitch, cam, 0));

            for (let bi = 0; bi < baseHeights.length; bi++) {
                const col = bi % 3;
                const row = Math.floor(bi / 3);
                const bx = 1.45 + col * 0.68;
                const bz = (row - 0.5) * 0.68;
                const wave = prefersReducedMotion ? 1 : (0.88 + 0.14 * Math.sin(phase * 1.9 + bi * 0.85));
                const bh = baseHeights[bi] * wave;
                const by = -0.95 + bh / 2;
                queue.push(...buildBoxFaces(bx, by, bz, 0.44, bh, 0.44, barShades[bi], yaw, pitch, cam, 0));
            }

            // Orbiting Star Schema Dimension Satellites around the BI Core
            const satCoords = [];
            const factPos = rotatePoint(0.75, 1.38 + Math.sin(phase) * 0.08, 0.0, yaw, pitch);
            const factProj = projectPoint(factPos.x, factPos.y, factPos.z, cam);
            queue.push(
                ...buildBoxFaces(0.75, 1.38 + Math.sin(phase) * 0.08, 0.0, 0.56, 0.56, 0.56, pal.emerald, yaw, pitch, cam, phase * 0.7)
            );
            for (let si = 0; si < 3; si++) {
                const sa = phase * 0.55 + (si * Math.PI * 2) / 3;
                const sx = 0.75 + Math.cos(sa) * 1.18;
                const sy = 1.55 + Math.sin(phase * 1.2 + si) * 0.12;
                const sz = Math.sin(sa) * 0.95;
                const sr = rotatePoint(sx, sy, sz, yaw, pitch);
                const sp = projectPoint(sr.x, sr.y, sr.z, cam);
                if (sp && factProj) {
                    satCoords.push({ a: factProj, b: sp, depth: (factProj.z + sp.z) * 0.5 });
                }
                queue.push(
                    ...buildBoxFaces(sx, sy, sz, 0.30, 0.30, 0.30, si === 0 ? pal.cyan : pal.indigo, yaw, pitch, cam, -phase * 0.9 + si)
                );
            }
            satCoords.forEach((edge) => {
                queue.push({ kind: 'edge', a: edge.a, b: edge.b, color: pal.beam, depth: edge.depth });
            });

            // Painter's depth sort (furthest first)
            queue.sort((a, b) => b.depth - a.depth);

            for (let i = 0; i < queue.length; i++) {
                const item = queue[i];
                if (item.kind === 'poly') {
                    ctx.beginPath();
                    ctx.moveTo(item.pts[0].x, item.pts[0].y);
                    ctx.lineTo(item.pts[1].x, item.pts[1].y);
                    ctx.lineTo(item.pts[2].x, item.pts[2].y);
                    ctx.lineTo(item.pts[3].x, item.pts[3].y);
                    ctx.closePath();
                    ctx.fillStyle = item.fill;
                    ctx.fill();
                    ctx.strokeStyle = item.stroke;
                    ctx.lineWidth = 0.9;
                    ctx.stroke();
                } else if (item.kind === 'ring') {
                    ctx.beginPath();
                    ctx.moveTo(item.pts[0].x, item.pts[0].y);
                    for (let j = 1; j < item.pts.length; j++) {
                        ctx.lineTo(item.pts[j].x, item.pts[j].y);
                    }
                    ctx.strokeStyle = item.color;
                    ctx.lineWidth = 2.2;
                    ctx.stroke();
                } else if (item.kind === 'edge') {
                    ctx.save();
                    ctx.setLineDash([4, 4]);
                    ctx.strokeStyle = item.color;
                    ctx.lineWidth = 1.4;
                    ctx.beginPath();
                    ctx.moveTo(item.a.x, item.a.y);
                    ctx.lineTo(item.b.x, item.b.y);
                    ctx.stroke();
                    ctx.restore();
                } else if (item.kind === 'dot') {
                    ctx.beginPath();
                    ctx.arc(item.x, item.y, item.radius, 0, Math.PI * 2);
                    ctx.fillStyle = item.color;
                    ctx.fill();
                }
            }

            // Floating Stage Telemetry Labels anchored in 3D space
            const anchors = [
                { wx: -2.9, wy: 1.25, wz: 0.0, key: 'viz_node_ingest' },
                { wx: -0.35, wy: -1.0, wz: 0.9, key: 'viz_node_etl' },
                { wx: 2.1, wy: 1.85, wz: -0.1, key: 'viz_node_warehouse' },
            ];
            anchors.forEach((anc) => {
                const r = rotatePoint(anc.wx, anc.wy, anc.wz, yaw, pitch);
                const p = projectPoint(r.x, r.y, r.z, cam);
                if (p && p.x > 60 && p.x < width - 60 && p.y > 30 && p.y < height - 24) {
                    drawRoundedTag(ctx, p.x, p.y, t(anc.key), pal);
                }
            });

            ctx.restore();
        }

        let lastTime = performance.now();
        function loop(now) {
            const dt = Math.min((now - lastTime) / 16.67, 2.5);
            lastTime = now;
            if (isVisible && document.visibilityState !== 'hidden') {
                renderFrame(dt);
                if (!prefersReducedMotion) {
                    rafId = requestAnimationFrame(loop);
                }
            } else {
                rafId = null;
            }
        }

        function startLoop() {
            if (prefersReducedMotion) {
                renderFrame(0);
                return;
            }
            if (!rafId) {
                lastTime = performance.now();
                rafId = requestAnimationFrame(loop);
            }
        }

        if ('IntersectionObserver' in window) {
            const obs = new IntersectionObserver((entries) => {
                isVisible = entries[0] ? entries[0].isIntersecting : true;
                if (isVisible) startLoop();
            }, { threshold: 0.05 });
            obs.observe(canvas);
        }

        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible' && isVisible) startLoop();
        });

        window.addEventListener('resize', () => renderFrame(0));
        if (window.autobiTheme && typeof window.autobiTheme.onChange === 'function') {
            window.autobiTheme.onChange(() => renderFrame(0));
        }
        if (window.autobiI18n && typeof window.autobiI18n.onChange === 'function') {
            window.autobiI18n.onChange(() => renderFrame(0));
        }

        startLoop();
    }

    // =========================================================================
    // 2. Interactive 3D Star Schema Topology Canvas (#schema3dCanvas)
    // =========================================================================
    function initSchema3D() {
        const canvas = document.getElementById('schema3dCanvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        let activeStep = 0;
        let phase = 0;
        let isVisible = true;
        let rafId = null;

        const stepBtns = document.querySelectorAll('.pipeline-stage-card[data-stage]');
        stepBtns.forEach((card) => {
            const stageIdx = Number(card.getAttribute('data-stage') || '0');
            const activate = () => {
                activeStep = stageIdx;
                stepBtns.forEach((c) => c.classList.toggle('active', c === card));
                if (prefersReducedMotion) renderFrame(0);
            };
            card.addEventListener('mouseenter', activate);
            card.addEventListener('click', activate);
            card.addEventListener('focus', activate);
        });

        const dimNodes = [
            { label: 'Raw_Staging', angle: 0, y: 0.35 },
            { label: 'Audit_3σ', angle: Math.PI * 0.5, y: -0.25 },
            { label: 'CBU_FX_Rate', angle: Math.PI, y: 0.30 },
            { label: 'Dim_Date (.pbip)', angle: Math.PI * 1.5, y: -0.20 },
        ];

        function renderFrame(dt) {
            const dims = sizeCanvas(canvas);
            if (!dims) return;
            const { width, height, dpr } = dims;
            const pal = getPalettes(getThemeMode());
            if (!prefersReducedMotion) phase += dt * 0.014;

            ctx.save();
            ctx.scale(dpr, dpr);
            drawBackground(ctx, width, height, pal);

            const yaw = phase * 0.38;
            const pitch = 0.36;
            const cam = {
                cx: width * 0.5,
                cy: height * 0.52,
                fov: 7.2,
                dist: 8.2,
                scale: Math.min(width, height) * 0.145,
                panX: 0,
                panY: 0,
            };

            // Central Fact Core
            const queue = [];
            queue.push(...buildBoxFaces(0, 0, 0, 1.05, 1.05, 1.05, pal.indigo, yaw, pitch, cam, phase * 0.45));

            const fRot = rotatePoint(0, 0, 0, yaw, pitch);
            const fProj = projectPoint(fRot.x, fRot.y, fRot.z, cam);

            const labelSpots = [];
            if (fProj) labelSpots.push({ x: fProj.x, y: fProj.y + 46, text: t('schema_hud_fact'), depth: fProj.z });

            dimNodes.forEach((dn, idx) => {
                const isSelected = idx === activeStep;
                const radius = isSelected ? 2.15 : 2.35;
                const nx = Math.cos(dn.angle) * radius;
                const nz = Math.sin(dn.angle) * radius;
                const ny = dn.y + Math.sin(phase * 1.4 + idx) * 0.14;
                const sz = isSelected ? 0.68 : 0.48;
                const shade = isSelected ? pal.emerald : (idx % 2 === 0 ? pal.cyan : pal.raw);

                queue.push(...buildBoxFaces(nx, ny, nz, sz, sz, sz, shade, yaw, pitch, cam, -phase * 0.6 + idx));

                const nr = rotatePoint(nx, ny, nz, yaw, pitch);
                const np = projectPoint(nr.x, nr.y, nr.z, cam);
                if (np && fProj) {
                    queue.push({
                        kind: 'edge',
                        a: fProj,
                        b: np,
                        color: isSelected ? pal.emerald.top : pal.spline,
                        width: isSelected ? 2.6 : 1.3,
                        depth: (fProj.z + np.z) * 0.5,
                    });
                    labelSpots.push({ x: np.x, y: np.y - (isSelected ? 34 : 26), text: dn.label, depth: np.z });
                }
            });

            queue.sort((a, b) => b.depth - a.depth);
            for (let i = 0; i < queue.length; i++) {
                const item = queue[i];
                if (item.kind === 'poly') {
                    ctx.beginPath();
                    ctx.moveTo(item.pts[0].x, item.pts[0].y);
                    ctx.lineTo(item.pts[1].x, item.pts[1].y);
                    ctx.lineTo(item.pts[2].x, item.pts[2].y);
                    ctx.lineTo(item.pts[3].x, item.pts[3].y);
                    ctx.closePath();
                    ctx.fillStyle = item.fill;
                    ctx.fill();
                    ctx.strokeStyle = item.stroke;
                    ctx.lineWidth = 1;
                    ctx.stroke();
                } else if (item.kind === 'edge') {
                    ctx.save();
                    ctx.setLineDash([5, 4]);
                    ctx.strokeStyle = item.color;
                    ctx.lineWidth = item.width || 1.4;
                    ctx.beginPath();
                    ctx.moveTo(item.a.x, item.a.y);
                    ctx.lineTo(item.b.x, item.b.y);
                    ctx.stroke();
                    ctx.restore();
                }
            }

            labelSpots.sort((a, b) => b.depth - a.depth);
            labelSpots.forEach((lbl) => drawRoundedTag(ctx, lbl.x, lbl.y, lbl.text, pal));
            ctx.restore();
        }

        let lastTime = performance.now();
        function loop(now) {
            const dt = Math.min((now - lastTime) / 16.67, 2.5);
            lastTime = now;
            if (isVisible && document.visibilityState !== 'hidden') {
                renderFrame(dt);
                if (!prefersReducedMotion) rafId = requestAnimationFrame(loop);
            } else {
                rafId = null;
            }
        }

        function startLoop() {
            if (prefersReducedMotion) {
                renderFrame(0);
                return;
            }
            if (!rafId) {
                lastTime = performance.now();
                rafId = requestAnimationFrame(loop);
            }
        }

        if ('IntersectionObserver' in window) {
            const obs = new IntersectionObserver((entries) => {
                isVisible = entries[0] ? entries[0].isIntersecting : true;
                if (isVisible) startLoop();
            }, { threshold: 0.05 });
            obs.observe(canvas);
        }

        window.addEventListener('resize', () => renderFrame(0));
        if (window.autobiTheme && typeof window.autobiTheme.onChange === 'function') {
            window.autobiTheme.onChange(() => renderFrame(0));
        }
        if (window.autobiI18n && typeof window.autobiI18n.onChange === 'function') {
            window.autobiI18n.onChange(() => renderFrame(0));
        }
        startLoop();
    }

    // =========================================================================
    // 3. Multi-Domain Morphing 3D KPI Cube (#domain3dCanvas) + Domain Switcher
    // =========================================================================
    const DOMAIN_DATA = {
        sales: {
            bars: [1.1, 1.5, 1.35, 1.95, 2.25],
            labels: ['Q1', 'Q2', 'Q3', 'Q4', 'YTD'],
            dax: "Net Revenue (USD) =\nSUMX(Fact_Sales, Fact_Sales[revenue_usd])\n// + CBU.uz UZS/USD Dual Measure & YoY%",
        },
        marketing: {
            bars: [0.95, 1.75, 2.1, 1.45, 1.85],
            labels: ['Search', 'Social', 'Video', 'Email', 'Blended'],
            dax: "Blended ROAS =\nDIVIDE([Attributed Revenue], [Ad Spend USD], 0)\n// Auto-tagged CAC efficiency tiers",
        },
        hr: {
            bars: [1.8, 1.6, 1.25, 0.9, 2.05],
            labels: ['Eng', 'Sales', 'Ops', 'Finance', 'Retain'],
            dax: "Retention Rate % =\n1 - DIVIDE([Voluntary Exits], [Avg Headcount], 0)\n// Department tenure & payroll index",
        },
        inventory: {
            bars: [1.55, 2.15, 0.75, 1.9, 1.35],
            labels: ['SKU-A', 'SKU-B', 'Low', 'Fast', 'Turn'],
            dax: "Inventory Turnover =\nDIVIDE([COGS USD], [Avg Stock Valuation], 0)\n// Pareto ABC + Reorder Threshold Flags",
        },
        finance: {
            bars: [1.95, 1.3, 1.65, 2.2, 1.85],
            labels: ['Rev', 'COGS', 'OpEx', 'EBITDA', 'Cash'],
            dax: "Operating EBITDA Margin =\nDIVIDE([EBITDA USD], [Gross Revenue USD], 0)\n// 3σ Anomaly Guard & Duplicate Check",
        },
    };

    function initDomainShowcase() {
        const canvas = document.getElementById('domain3dCanvas');
        const tabBtns = document.querySelectorAll('.domain-showcase-tab[data-domain]');
        if (!tabBtns.length) return;

        let activeDomain = 'sales';
        let curBars = [...DOMAIN_DATA.sales.bars];
        let targetBars = [...DOMAIN_DATA.sales.bars];
        let phase = 0;
        let isVisible = true;
        let rafId = null;

        const titleEl = document.getElementById('domShowcaseTitle');
        const subEl = document.getElementById('domShowcaseSub');
        const daxEl = document.getElementById('domShowcaseDax');
        const ctaEl = document.getElementById('domShowcaseCta');
        const m1Lbl = document.getElementById('domM1Lbl');
        const m1Val = document.getElementById('domM1Val');
        const m2Lbl = document.getElementById('domM2Lbl');
        const m2Val = document.getElementById('domM2Val');
        const m3Lbl = document.getElementById('domM3Lbl');
        const m3Val = document.getElementById('domM3Val');

        function updateText() {
            const dName = t(`dom_${activeDomain}_name`);
            if (titleEl) titleEl.textContent = dName;
            if (subEl) subEl.textContent = t(`dom_${activeDomain}_sub`);
            if (daxEl) daxEl.textContent = DOMAIN_DATA[activeDomain].dax;
            if (ctaEl) {
                ctaEl.href = `/studio?demo=${activeDomain}`;
                ctaEl.textContent = t('dom_cta_btn', { domain: dName });
            }
            if (m1Lbl) m1Lbl.textContent = t(`dom_${activeDomain}_m1_lbl`);
            if (m1Val) m1Val.textContent = t(`dom_${activeDomain}_m1_val`);
            if (m2Lbl) m2Lbl.textContent = t(`dom_${activeDomain}_m2_lbl`);
            if (m2Val) m2Val.textContent = t(`dom_${activeDomain}_m2_val`);
            if (m3Lbl) m3Lbl.textContent = t(`dom_${activeDomain}_m3_lbl`);
            if (m3Val) m3Val.textContent = t(`dom_${activeDomain}_m3_val`);
        }

        tabBtns.forEach((btn) => {
            btn.addEventListener('click', () => {
                const dom = btn.getAttribute('data-domain');
                if (!DOMAIN_DATA[dom]) return;
                activeDomain = dom;
                targetBars = [...DOMAIN_DATA[dom].bars];
                tabBtns.forEach((b) => {
                    const on = b === btn;
                    b.classList.toggle('active', on);
                    b.setAttribute('aria-pressed', on ? 'true' : 'false');
                });
                updateText();
                if (prefersReducedMotion && canvas) renderFrame(0);
            });
        });

        function renderFrame(dt) {
            if (!canvas) return;
            const ctx = canvas.getContext('2d');
            if (!ctx) return;
            const dims = sizeCanvas(canvas);
            if (!dims) return;
            const { width, height, dpr } = dims;
            const pal = getPalettes(getThemeMode());
            if (!prefersReducedMotion) phase += dt * 0.015;

            for (let i = 0; i < curBars.length; i++) {
                curBars[i] = lerp(curBars[i], targetBars[i], prefersReducedMotion ? 1 : 0.12);
            }

            ctx.save();
            ctx.scale(dpr, dpr);
            drawBackground(ctx, width, height, pal);

            const yaw = 0.42 + (prefersReducedMotion ? 0 : Math.sin(phase * 0.45) * 0.14);
            const pitch = 0.34;
            const cam = {
                cx: width * 0.5,
                cy: height * 0.58,
                fov: 7.4,
                dist: 7.8,
                scale: Math.min(width, height) * 0.155,
                panX: 0,
                panY: 0.1,
            };

            const queue = [];
            queue.push(...buildBoxFaces(0, -1.02, 0, 3.6, 0.16, 1.35, pal.indigo, yaw, pitch, cam, 0));

            const shades = [pal.indigo, pal.cyan, pal.emerald, pal.indigo, pal.emerald];
            const labels = DOMAIN_DATA[activeDomain].labels;
            const labelCoords = [];

            for (let i = 0; i < curBars.length; i++) {
                const bx = (i - 2) * 0.68;
                const breath = prefersReducedMotion ? 1 : (0.94 + 0.06 * Math.sin(phase * 1.8 + i));
                const bh = curBars[i] * breath;
                const by = -0.94 + bh / 2;
                queue.push(...buildBoxFaces(bx, by, 0, 0.42, bh, 0.42, shades[i], yaw, pitch, cam, 0));

                const tr = rotatePoint(bx, by + bh / 2 + 0.28, 0, yaw, pitch);
                const tp = projectPoint(tr.x, tr.y, tr.z, cam);
                if (tp) labelCoords.push({ x: tp.x, y: tp.y, text: labels[i] });
            }

            queue.sort((a, b) => b.depth - a.depth);
            for (let i = 0; i < queue.length; i++) {
                const item = queue[i];
                ctx.beginPath();
                ctx.moveTo(item.pts[0].x, item.pts[0].y);
                ctx.lineTo(item.pts[1].x, item.pts[1].y);
                ctx.lineTo(item.pts[2].x, item.pts[2].y);
                ctx.lineTo(item.pts[3].x, item.pts[3].y);
                ctx.closePath();
                ctx.fillStyle = item.fill;
                ctx.fill();
                ctx.strokeStyle = item.stroke;
                ctx.lineWidth = 0.9;
                ctx.stroke();
            }

            labelCoords.forEach((lbl) => drawRoundedTag(ctx, lbl.x, lbl.y, lbl.text, pal));
            ctx.restore();
        }

        let lastTime = performance.now();
        function loop(now) {
            const dt = Math.min((now - lastTime) / 16.67, 2.5);
            lastTime = now;
            if (isVisible && document.visibilityState !== 'hidden') {
                renderFrame(dt);
                if (!prefersReducedMotion) rafId = requestAnimationFrame(loop);
            } else {
                rafId = null;
            }
        }

        function startLoop() {
            if (prefersReducedMotion) {
                renderFrame(0);
                return;
            }
            if (!rafId && canvas) {
                lastTime = performance.now();
                rafId = requestAnimationFrame(loop);
            }
        }

        if (canvas && 'IntersectionObserver' in window) {
            const obs = new IntersectionObserver((entries) => {
                isVisible = entries[0] ? entries[0].isIntersecting : true;
                if (isVisible) startLoop();
            }, { threshold: 0.05 });
            obs.observe(canvas);
        }

        window.addEventListener('resize', () => renderFrame(0));
        if (window.autobiTheme && typeof window.autobiTheme.onChange === 'function') {
            window.autobiTheme.onChange(() => renderFrame(0));
        }
        if (window.autobiI18n && typeof window.autobiI18n.onChange === 'function') {
            window.autobiI18n.onChange(() => {
                updateText();
                renderFrame(0);
            });
        }

        updateText();
        startLoop();
    }

    // =========================================================================
    // 4. Bootstrap on DOMContentLoaded
    // =========================================================================
    document.addEventListener('DOMContentLoaded', () => {
        if (window.autobiI18n) {
            window.autobiI18n.applyTranslations();
            document.querySelectorAll('.lang-btn[data-lang]').forEach((btn) => {
                btn.addEventListener('click', () => {
                    window.autobiI18n.setLang(btn.getAttribute('data-lang'));
                });
            });
        }

        initHero3D();
        initSchema3D();
        initDomainShowcase();
    });
})();
