/**
 * AutoBI Landing Storyboard & Interactive 3D Data Visualizations
 * - Hero Storyboard: 60fps GPU-composited workflow packets (Staff -> AutoBI ETL -> Manager BI)
 * - Schema Topology Canvas: Isometric 3D Database Cylinders & Star Schema Tables
 * - Domain Analytics Canvas: Isometric 3D Paired Comparison Bars with % Deltas & Trend Spline
 * Supports Dark & Light themes via window.autobiTheme and EN / RU / UZ via window.autobiI18n.
 */
(function () {
  "use strict";

  var REDUCED_MOTION =
    typeof window !== "undefined" &&
    window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function t(key, fallback) {
    if (window.autobiI18n && typeof window.autobiI18n.t === "function") {
      var val = window.autobiI18n.t(key);
      if (val && val !== key) return val;
    }
    return fallback || key;
  }

  function isLightMode() {
    if (window.autobiTheme && typeof window.autobiTheme.getTheme === "function") {
      return window.autobiTheme.getTheme() === "light";
    }
    return document.documentElement.getAttribute("data-theme") === "light";
  }

  function getPalette() {
    var light = isLightMode();
    return light
      ? {
          bg: "#F6F8FC",
          grid: "rgba(15, 23, 42, 0.06)",
          cardBg: "#FFFFFF",
          cardBorder: "rgba(15, 23, 42, 0.14)",
          text: "#0F172A",
          muted: "#475569",
          accent: "#D97706",
          accentSoft: "rgba(217, 119, 6, 0.14)",
          teal: "#059669",
          tealSoft: "rgba(5, 150, 105, 0.14)",
          blue: "#2563EB",
          blueSoft: "rgba(37, 99, 235, 0.14)",
          purple: "#7C3AED",
          rose: "#E11D48",
          prevTop: "#CBD5E1",
          prevFront: "#94A3B8",
          prevSide: "#64748B",
          beam: "rgba(37, 99, 235, 0.36)",
          shadow: "rgba(15, 23, 42, 0.12)"
        }
      : {
          bg: "#0B1020",
          grid: "rgba(148, 163, 184, 0.08)",
          cardBg: "#131C31",
          cardBorder: "rgba(148, 163, 184, 0.22)",
          text: "#F8FAFC",
          muted: "#94A3B8",
          accent: "#F59E0B",
          accentSoft: "rgba(245, 158, 11, 0.16)",
          teal: "#10B981",
          tealSoft: "rgba(16, 185, 129, 0.16)",
          blue: "#38BDF8",
          blueSoft: "rgba(56, 189, 248, 0.16)",
          purple: "#A78BFA",
          rose: "#FB7185",
          prevTop: "#475569",
          prevFront: "#334155",
          prevSide: "#1E293B",
          beam: "rgba(56, 189, 248, 0.36)",
          shadow: "rgba(2, 6, 23, 0.52)"
        };
  }

  function cubicBezier(p0, p1, p2, p3, u) {
    var inv = 1 - u;
    return (
      inv * inv * inv * p0 +
      3 * inv * inv * u * p1 +
      3 * inv * u * u * p2 +
      u * u * u * p3
    );
  }

  function clamp(v, min, max) {
    return v < min ? min : v > max ? max : v;
  }

  function lerp(a, b, k) {
    return a + (b - a) * k;
  }

  function drawRoundedRect(ctx, x, y, w, h, r) {
    var rad = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + rad, y);
    ctx.lineTo(x + w - rad, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + rad);
    ctx.lineTo(x + w, y + h - rad);
    ctx.quadraticCurveTo(x + w, y + h, x + w - rad, y + h);
    ctx.lineTo(x + rad, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - rad);
    ctx.lineTo(x, y + rad);
    ctx.quadraticCurveTo(x, y, x + rad, y);
    ctx.closePath();
  }

  /**
   * Solid isometric column/bar with unambiguous front, right-side, and top faces.
   * Zero screen-space winding culling, so faces never drop out or look hollow.
   */
  function drawIsoBar(ctx, cx, baseY, w, h, dx, dy, colors) {
    if (h < 2) h = 2;
    var left = cx - w / 2;
    var right = cx + w / 2;
    var topY = baseY - h;

    // Ground drop shadow
    ctx.fillStyle = colors.shadow;
    ctx.beginPath();
    ctx.ellipse(cx + dx * 0.45, baseY + 3, w * 0.65, 5, 0, 0, Math.PI * 2);
    ctx.fill();

    // Right extruded side face
    ctx.fillStyle = colors.side;
    ctx.beginPath();
    ctx.moveTo(right, topY);
    ctx.lineTo(right + dx, topY + dy);
    ctx.lineTo(right + dx, baseY + dy);
    ctx.lineTo(right, baseY);
    ctx.closePath();
    ctx.fill();

    // Front face
    ctx.fillStyle = colors.front;
    ctx.beginPath();
    ctx.moveTo(left, topY);
    ctx.lineTo(right, topY);
    ctx.lineTo(right, baseY);
    ctx.lineTo(left, baseY);
    ctx.closePath();
    ctx.fill();

    // Top parallelogram face
    ctx.fillStyle = colors.top;
    ctx.beginPath();
    ctx.moveTo(left, topY);
    ctx.lineTo(left + dx, topY + dy);
    ctx.lineTo(right + dx, topY + dy);
    ctx.lineTo(right, topY);
    ctx.closePath();
    ctx.fill();

    // Subtle crisp edge highlight on front-top rim
    ctx.strokeStyle = "rgba(255, 255, 255, 0.28)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(left, topY);
    ctx.lineTo(right, topY);
    ctx.lineTo(right + dx, topY + dy);
    ctx.stroke();
  }

  /**
   * Draw an isometric 3D database cylinder stack (e.g. Fact_Model warehouse).
   */
  function drawIsoCylinderStack(ctx, cx, cy, rx, ry, tierHeight, tiers, colors) {
    var totalH = tierHeight * tiers;
    // Soft ambient shadow
    ctx.fillStyle = colors.shadow;
    ctx.beginPath();
    ctx.ellipse(cx, cy + totalH * 0.45 + 10, rx * 1.15, ry * 1.25, 0, 0, Math.PI * 2);
    ctx.fill();

    var topStart = cy - totalH * 0.5;
    for (var i = tiers - 1; i >= 0; i--) {
      var yTop = topStart + i * tierHeight;
      var yBot = yTop + tierHeight - 3;

      // Cylinder body gradient
      var grad = ctx.createLinearGradient(cx - rx, 0, cx + rx, 0);
      grad.addColorStop(0, colors.left);
      grad.addColorStop(0.55, colors.front);
      grad.addColorStop(1, colors.right);

      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.moveTo(cx - rx, yTop);
      ctx.lineTo(cx - rx, yBot);
      ctx.ellipse(cx, yBot, rx, ry, 0, Math.PI, 0, true);
      ctx.lineTo(cx + rx, yTop);
      ctx.closePath();
      ctx.fill();

      // Tier ring top ellipse
      ctx.fillStyle = i === 0 ? colors.top : colors.seam;
      ctx.beginPath();
      ctx.ellipse(cx, yTop, rx, ry, 0, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = colors.stroke;
      ctx.lineWidth = 1.2;
      ctx.stroke();
    }
  }

  function observeVisibility(el, onVisibleChange) {
    if (!el || typeof IntersectionObserver === "undefined") {
      onVisibleChange(true);
      return;
    }
    var obs = new IntersectionObserver(
      function (entries) {
        for (var i = 0; i < entries.length; i++) {
          if (entries[i].target === el) {
            onVisibleChange(entries[i].isIntersecting);
          }
        }
      },
      { threshold: 0.05 }
    );
    obs.observe(el);
  }

  /* =========================================================
     1. HERO STORYBOARD: Staff -> AutoBI ETL -> Manager BI
     ========================================================= */
  function initHeroStoryMotion() {
    var stage = document.getElementById("heroStoryStage");
    var scene = document.getElementById("heroStoryScene");
    var packetLayer = document.getElementById("storyPacketLayer");
    if (!stage || !scene || !packetLayer) return;

    var staffNode = stage.querySelector(".story-node-staff");
    var coreNode = stage.querySelector(".story-node-core");
    var biNode = stage.querySelector(".story-node-bi");
    var camBtns = stage.querySelectorAll(".cam-preset-btn[data-cam]");
    var zoneNodes = stage.querySelectorAll(".story-node[data-stage-zone]");

    function setFocus(focus) {
      var mode = focus || "all";
      scene.setAttribute("data-focus", mode);
      for (var i = 0; i < camBtns.length; i++) {
        var btn = camBtns[i];
        btn.classList.toggle("active", btn.getAttribute("data-cam") === mode);
      }
    }

    for (var b = 0; b < camBtns.length; b++) {
      camBtns[b].addEventListener("click", function () {
        setFocus(this.getAttribute("data-cam"));
      });
    }

    for (var z = 0; z < zoneNodes.length; z++) {
      zoneNodes[z].addEventListener("click", function () {
        var zone = this.getAttribute("data-stage-zone");
        var current = scene.getAttribute("data-focus");
        setFocus(current === zone ? "all" : zone);
      });
    }

    // Damped mouse 3D tilt (zero jitter)
    var targetTiltX = 0;
    var targetTiltY = 0;
    var curTiltX = 0;
    var curTiltY = 0;

    stage.addEventListener("pointermove", function (e) {
      if (REDUCED_MOTION) return;
      var rect = stage.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      var nx = (e.clientX - rect.left) / rect.width - 0.5;
      var ny = (e.clientY - rect.top) / rect.height - 0.5;
      targetTiltY = clamp(nx * 5.5, -3.5, 3.5);
      targetTiltX = clamp(-ny * 4.5, -3, 3);
    });

    stage.addEventListener("pointerleave", function () {
      targetTiltX = 0;
      targetTiltY = 0;
    });

    // Flying packet descriptors: 2 raw spreadsheets (Left->Core) & 3 BI cards (Core->Manager)
    var packetSpecs = [
      { kind: "raw", key: "story_raw_file1", fallback: "Sales_Q4_1C.xlsx", lane: -1, phase: 0.0, speed: 0.25 },
      { kind: "raw", key: "story_raw_file2", fallback: "ERP_Mixed_FX.csv", lane: 1, phase: 0.48, speed: 0.25 },
      { kind: "clean", key: "story_clean_1", fallback: "+24.8% YoY", lane: -1, phase: 0.14, speed: 0.26 },
      { kind: "clean", key: "story_clean_2", fallback: "FX · 12,840", lane: 0, phase: 0.47, speed: 0.26 },
      { kind: "clean", key: "story_clean_3", fallback: "Class A · 80%", lane: 1, phase: 0.80, speed: 0.26 }
    ];

    var packets = [];
    for (var p = 0; p < packetSpecs.length; p++) {
      var spec = packetSpecs[p];
      var el = document.createElement("div");
      el.className = "story-flying-item " + spec.kind;
      el.textContent = t(spec.key, spec.fallback);
      packetLayer.appendChild(el);
      packets.push({ el: el, spec: spec, u: spec.phase });
    }

    function refreshPacketLabels() {
      for (var i = 0; i < packets.length; i++) {
        packets[i].el.textContent = t(packets[i].spec.key, packets[i].spec.fallback);
      }
    }

    if (window.autobiI18n && typeof window.autobiI18n.onChange === "function") {
      window.autobiI18n.onChange(refreshPacketLabels);
    }

    var anchors = null;
    function measureAnchors() {
      var sRect = scene.getBoundingClientRect();
      if (!sRect.width || !sRect.height || !staffNode || !coreNode || !biNode) {
        anchors = null;
        return;
      }
      var rStaff = staffNode.getBoundingClientRect();
      var rCore = coreNode.getBoundingClientRect();
      var rBi = biNode.getBoundingClientRect();

      anchors = {
        w: sRect.width,
        h: sRect.height,
        staffRightX: rStaff.right - sRect.left - 18,
        staffMidY: rStaff.top + rStaff.height * 0.52 - sRect.top,
        coreLeftX: rCore.left - sRect.left + 20,
        coreRightX: rCore.right - sRect.left - 20,
        coreMidY: rCore.top + rCore.height * 0.5 - sRect.top,
        biLeftX: rBi.left - sRect.left + 16,
        biMidY: rBi.top + rBi.height * 0.5 - sRect.top,
        verticalStack: rCore.top > rStaff.bottom - 10
      };
    }

    measureAnchors();
    if (typeof ResizeObserver !== "undefined") {
      var ro = new ResizeObserver(measureAnchors);
      ro.observe(scene);
    } else {
      window.addEventListener("resize", measureAnchors);
    }

    var inView = true;
    observeVisibility(stage, function (v) {
      inView = v;
    });

    var lastTs = performance.now();
    function tick(ts) {
      var dt = Math.min((ts - lastTs) / 1000, 0.05);
      lastTs = ts;

      if (inView && !document.hidden) {
        // Smooth damped 3D scene tilt
        curTiltX = lerp(curTiltX, targetTiltX, 0.09);
        curTiltY = lerp(curTiltY, targetTiltY, 0.09);
        scene.style.setProperty("--story-rx", curTiltX.toFixed(2) + "deg");
        scene.style.setProperty("--story-ry", curTiltY.toFixed(2) + "deg");

        if (!anchors) measureAnchors();

        if (anchors && !REDUCED_MOTION) {
          for (var i = 0; i < packets.length; i++) {
            var pkt = packets[i];
            pkt.u = (pkt.u + dt * pkt.spec.speed) % 1;
            var u = pkt.u;
            var x, y, rot;
            var laneOffset = pkt.spec.lane * 26;

            if (anchors.verticalStack) {
              // Compact mobile vertical flow
              var vx = anchors.w * 0.5 + pkt.spec.lane * 42;
              var vyStart = pkt.spec.kind === "raw" ? anchors.staffMidY + 30 : anchors.coreMidY + 30;
              var vyEnd = pkt.spec.kind === "raw" ? anchors.coreMidY - 30 : anchors.biMidY - 30;
              x = vx + Math.sin(u * Math.PI) * pkt.spec.lane * 14;
              y = lerp(vyStart, vyEnd, u);
              rot = 0;
            } else if (pkt.spec.kind === "raw") {
              var sx = anchors.staffRightX;
              var sy = anchors.staffMidY + laneOffset;
              var ex = anchors.coreLeftX;
              var ey = anchors.coreMidY + laneOffset * 0.35;
              var arc = pkt.spec.lane * -22;
              x = cubicBezier(sx, lerp(sx, ex, 0.35), lerp(sx, ex, 0.68), ex, u);
              y = cubicBezier(sy, sy + arc, ey - arc * 0.5, ey, u);
              rot = (1 - u) * (pkt.spec.lane * -4);
            } else {
              var cx0 = anchors.coreRightX;
              var cy0 = anchors.coreMidY + laneOffset * 0.35;
              var bx1 = anchors.biLeftX;
              var by1 = anchors.biMidY + laneOffset;
              var cArc = pkt.spec.lane * 20;
              x = cubicBezier(cx0, lerp(cx0, bx1, 0.35), lerp(cx0, bx1, 0.7), bx1, u);
              y = cubicBezier(cy0, cy0 - cArc, by1 + cArc * 0.5, by1, u);
              rot = (1 - u) * (pkt.spec.lane * 2.5);
            }

            // Smooth alpha fade at start and core/manager handoff + scale pop in middle
            var alpha = Math.sin(Math.PI * u);
            alpha = clamp(alpha * 1.45, 0, 0.98);
            var scale = 0.86 + Math.sin(Math.PI * u) * 0.16;

            pkt.el.style.opacity = alpha.toFixed(3);
            pkt.el.style.transform =
              "translate3d(" +
              (x - pkt.el.offsetWidth * 0.5).toFixed(1) +
              "px, " +
              (y - pkt.el.offsetHeight * 0.5).toFixed(1) +
              "px, 0) scale(" +
              scale.toFixed(3) +
              ") rotate(" +
              rot.toFixed(2) +
              "deg)";
          }
        } else if (REDUCED_MOTION) {
          for (var r = 0; r < packets.length; r++) {
            packets[r].el.style.opacity = "0";
          }
        }
      }

      requestAnimationFrame(tick);
    }

    requestAnimationFrame(tick);
  }

  /* =========================================================
     2. 3D STAR SCHEMA TOPOLOGY CANVAS (Cylinders + Dim Cards)
     ========================================================= */
  function initSchema3D() {
    var canvas = document.getElementById("schema3dCanvas");
    if (!canvas) return;
    var ctx = canvas.getContext("2d");
    var stageCards = document.querySelectorAll(".pipeline-stage-card[data-stage]");
    var activeStage = 0;

    for (var s = 0; s < stageCards.length; s++) {
      stageCards[s].addEventListener("mouseenter", function () {
        activeStage = parseInt(this.getAttribute("data-stage") || "0", 10);
      });
      stageCards[s].addEventListener("click", function () {
        activeStage = parseInt(this.getAttribute("data-stage") || "0", 10);
      });
    }

    var width = 0;
    var height = 0;
    var dpr = 1;
    function resize() {
      var rect = canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = rect.width;
      height = rect.height;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    resize();
    if (typeof ResizeObserver !== "undefined") {
      new ResizeObserver(resize).observe(canvas);
    } else {
      window.addEventListener("resize", resize);
    }

    var dragAngle = 0;
    var targetAngle = 0;
    var dragging = false;
    var lastX = 0;

    canvas.addEventListener("pointerdown", function (e) {
      dragging = true;
      lastX = e.clientX;
    });
    window.addEventListener("pointermove", function (e) {
      if (!dragging) return;
      targetAngle += (e.clientX - lastX) * 0.008;
      lastX = e.clientX;
    });
    window.addEventListener("pointerup", function () {
      dragging = false;
    });

    var dims = [
      { id: "Dim_Date", badge: "1 -> *", sub: "Calendar & YoY", stage: 0 },
      { id: "Dim_FX_CBU", badge: "UZS / USD", sub: "12,840 Live", stage: 1 },
      { id: "Dim_Audit_3s", badge: "3σ Check", sub: "0 Broken Rows", stage: 2 },
      { id: "Dim_KPI_DAX", badge: "DAX Engine", sub: ".pbip Ready", stage: 3 }
    ];

    var inView = true;
    observeVisibility(canvas, function (v) {
      inView = v;
    });

    var angle = 0;
    var lastTs = performance.now();

    function draw(ts) {
      var dt = Math.min((ts - lastTs) / 1000, 0.05);
      lastTs = ts;

      if (inView && !document.hidden && width > 10 && height > 10) {
        if (!REDUCED_MOTION && !dragging) {
          targetAngle += dt * 0.22;
        }
        dragAngle = lerp(dragAngle, targetAngle, 0.08);
        angle = dragAngle;

        var pal = getPalette();
        ctx.clearRect(0, 0, width, height);

        // Background + subtle perspective grid
        ctx.fillStyle = pal.bg;
        ctx.fillRect(0, 0, width, height);

        ctx.strokeStyle = pal.grid;
        ctx.lineWidth = 1;
        var step = 28;
        for (var gx = 0; gx < width; gx += step) {
          ctx.beginPath();
          ctx.moveTo(gx, 0);
          ctx.lineTo(gx, height);
          ctx.stroke();
        }
        for (var gy = 0; gy < height; gy += step) {
          ctx.beginPath();
          ctx.moveTo(0, gy);
          ctx.lineTo(width, gy);
          ctx.stroke();
        }

        var cx = width * 0.5;
        var cy = height * 0.52;
        var rxOrbit = Math.min(width * 0.34, 210);
        var ryOrbit = Math.min(height * 0.26, 108);

        // Faint isometric orbital ring
        ctx.strokeStyle = pal.cardBorder;
        ctx.setLineDash([4, 5]);
        ctx.beginPath();
        ctx.ellipse(cx, cy + 6, rxOrbit, ryOrbit, 0, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);

        // Compute orbiting node positions for painter ordering
        var nodes = [];
        for (var i = 0; i < dims.length; i++) {
          var theta = angle + (i * Math.PI) / 2;
          var nx = cx + Math.cos(theta) * rxOrbit;
          var ny = cy + Math.sin(theta) * ryOrbit;
          var depth = Math.sin(theta); // -1 back, +1 front
          nodes.push({
            idx: i,
            dim: dims[i],
            x: nx,
            y: ny,
            depth: depth,
            scale: 0.88 + (depth + 1) * 0.1
          });
        }

        // Draw relationship beams + moving ETL packets behind/around center
        for (var k = 0; k < nodes.length; k++) {
          var nd = nodes[k];
          var isHi = nd.dim.stage === activeStage;
          ctx.strokeStyle = isHi ? pal.accent : pal.beam;
          ctx.lineWidth = isHi ? 2.2 : 1.4;
          ctx.beginPath();
          ctx.moveTo(nd.x, nd.y);
          ctx.lineTo(cx, cy - 4);
          ctx.stroke();

          // Smooth flowing packet along beam from dim card -> Fact cylinder
          var pulseU = REDUCED_MOTION ? 0.5 : ((ts * 0.00055 + k * 0.25) % 1);
          var px = lerp(nd.x, cx, pulseU);
          var py = lerp(nd.y, cy - 4, pulseU);
          ctx.fillStyle = isHi ? pal.accent : pal.teal;
          ctx.beginPath();
          ctx.arc(px, py, isHi ? 4.2 : 3.2, 0, Math.PI * 2);
          ctx.fill();
        }

        // Depth-sort nodes + center cylinder together (center depth = 0)
        var renderList = nodes.map(function (n) {
          return { type: "dim", depth: n.depth, node: n };
        });
        renderList.push({ type: "center", depth: 0.02 });
        renderList.sort(function (a, b) {
          return a.depth - b.depth;
        });

        for (var r = 0; r < renderList.length; r++) {
          var item = renderList[r];
          if (item.type === "center") {
            drawIsoCylinderStack(ctx, cx, cy - 4, 48, 16, 17, 3, {
              left: isLightMode() ? "#1D4ED8" : "#0284C7",
              front: pal.blue,
              right: isLightMode() ? "#1E40AF" : "#0369A1",
              top: isLightMode() ? "#60A5FA" : "#7DD3FC",
              seam: isLightMode() ? "#3B82F6" : "#38BDF8",
              stroke: "rgba(255,255,255,0.45)",
              shadow: pal.shadow
            });

            // Central Fact label pill
            var factText = t("schema_hud_fact", "Fact_Model ★");
            ctx.font = "700 11.5px Inter, system-ui, sans-serif";
            var fw = ctx.measureText(factText).width + 20;
            drawRoundedRect(ctx, cx - fw / 2, cy - 52, fw, 24, 12);
            ctx.fillStyle = pal.cardBg;
            ctx.fill();
            ctx.strokeStyle = pal.accent;
            ctx.lineWidth = 1.4;
            ctx.stroke();
            ctx.fillStyle = pal.text;
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(factText, cx, cy - 40);
          } else {
            var dn = item.node;
            var cw = 112 * dn.scale;
            var ch = 50 * dn.scale;
            var x0 = dn.x - cw / 2;
            var y0 = dn.y - ch / 2;
            var hi = dn.dim.stage === activeStage;

            // Isometric 3D bottom thickness lip on schema card
            drawRoundedRect(ctx, x0, y0 + 5, cw, ch, 10);
            ctx.fillStyle = pal.shadow;
            ctx.fill();

            drawRoundedRect(ctx, x0, y0, cw, ch, 10);
            ctx.fillStyle = pal.cardBg;
            ctx.fill();
            ctx.strokeStyle = hi ? pal.accent : pal.cardBorder;
            ctx.lineWidth = hi ? 1.8 : 1.2;
            ctx.stroke();

            // Header bar accent
            drawRoundedRect(ctx, x0 + 1, y0 + 1, cw - 2, 16 * dn.scale, 8);
            ctx.fillStyle = hi ? pal.accentSoft : pal.blueSoft;
            ctx.fill();

            ctx.textAlign = "left";
            ctx.textBaseline = "middle";
            ctx.font = "700 " + (10.5 * dn.scale).toFixed(1) + "px Inter, sans-serif";
            ctx.fillStyle = pal.text;
            ctx.fillText(dn.dim.id, x0 + 8, y0 + 9 * dn.scale);

            ctx.font = "600 " + (9.5 * dn.scale).toFixed(1) + "px Inter, sans-serif";
            ctx.fillStyle = hi ? pal.accent : pal.teal;
            ctx.fillText(dn.dim.badge, x0 + 8, y0 + 27 * dn.scale);

            ctx.font = "500 " + (9 * dn.scale).toFixed(1) + "px Inter, sans-serif";
            ctx.fillStyle = pal.muted;
            ctx.fillText(dn.dim.sub, x0 + 8, y0 + 40 * dn.scale);
          }
        }
      }

      requestAnimationFrame(draw);
    }

    requestAnimationFrame(draw);
  }

  /* =========================================================
     3. DOMAIN COMPARISON ANALYTICS (Paired 3D Bars + % Deltas)
     ========================================================= */
  function initDomainShowcase() {
    var canvas = document.getElementById("domain3dCanvas");
    var tabs = document.querySelectorAll(".domain-showcase-tab[data-domain]");
    if (!canvas) return;
    var ctx = canvas.getContext("2d");

    var domTitle = document.getElementById("domShowcaseTitle");
    var domSub = document.getElementById("domShowcaseSub");
    var domDax = document.getElementById("domShowcaseDax");
    var domCta = document.getElementById("domShowcaseCta");
    var m1Lbl = document.getElementById("domM1Lbl");
    var m1Val = document.getElementById("domM1Val");
    var m2Lbl = document.getElementById("domM2Lbl");
    var m2Val = document.getElementById("domM2Val");
    var m3Lbl = document.getElementById("domM3Lbl");
    var m3Val = document.getElementById("domM3Val");

    var domainConfig = {
      sales: {
        dax: "YoY_Growth % = DIVIDE([Net_Sales] - [LY_Sales], [LY_Sales])",
        labels: ["Q1", "Q2", "Q3", "Q4", "Forecast"],
        prev: [0.42, 0.50, 0.56, 0.68, 0.72],
        curr: [0.51, 0.61, 0.70, 0.88, 0.94],
        deltas: ["+21.4%", "+22.0%", "+25.0%", "+29.4%", "+30.5%"]
      },
      marketing: {
        dax: "ROAS_Ratio = DIVIDE([Attributed_Rev], [Ad_Spend])",
        labels: ["Search", "Social", "CRM", "Video", "Affil"],
        prev: [0.38, 0.45, 0.54, 0.36, 0.48],
        curr: [0.52, 0.60, 0.76, 0.49, 0.64],
        deltas: ["+36.8%", "+33.3%", "+40.7%", "+36.1%", "+33.3%"]
      },
      hr: {
        dax: "Retention_Rate = 1 - DIVIDE([Voluntary_Exits], [Avg_HC])",
        labels: ["Eng", "Sales", "Ops", "Fin", "Supp"],
        prev: [0.74, 0.62, 0.70, 0.80, 0.65],
        curr: [0.89, 0.78, 0.84, 0.92, 0.81],
        deltas: ["+15.0%", "+16.0%", "+14.0%", "+12.0%", "+16.0%"]
      },
      inventory: {
        dax: "Class_A_Share = CALCULATE([SKU_Rev], [ABC] = \"Class A\")",
        labels: ["SKU-A", "SKU-B", "SKU-C", "WH-1", "WH-2"],
        prev: [0.68, 0.46, 0.28, 0.58, 0.50],
        curr: [0.86, 0.59, 0.34, 0.74, 0.66],
        deltas: ["+26.5%", "+28.3%", "+21.4%", "+27.6%", "+32.0%"]
      },
      finance: {
        dax: "EBITDA_Margin % = DIVIDE([Gross_Profit] - [OpEx], [Rev_UZS])",
        labels: ["Rev", "COGS", "Gross", "OpEx", "EBITDA"],
        prev: [0.64, 0.44, 0.52, 0.34, 0.46],
        curr: [0.82, 0.40, 0.74, 0.29, 0.68],
        deltas: ["+28.1%", "-9.1%", "+42.3%", "-14.7%", "+47.8%"]
      }
    };

    var currentDomain = "sales";
    var curPrev = domainConfig.sales.prev.slice();
    var curCurr = domainConfig.sales.curr.slice();

    function syncShowcaseText(dom) {
      var cfg = domainConfig[dom] || domainConfig.sales;
      if (domTitle) domTitle.textContent = t("dom_" + dom + "_name", dom);
      if (domSub) domSub.textContent = t("dom_" + dom + "_sub", "");
      if (domDax) domDax.textContent = cfg.dax;
      if (domCta) domCta.textContent = t("dom_cta_btn", "Launch AutoBI Studio →");
      if (m1Lbl) m1Lbl.textContent = t("dom_" + dom + "_m1_lbl", "");
      if (m1Val) m1Val.textContent = t("dom_" + dom + "_m1_val", "");
      if (m2Lbl) m2Lbl.textContent = t("dom_" + dom + "_m2_lbl", "");
      if (m2Val) m2Val.textContent = t("dom_" + dom + "_m2_val", "");
      if (m3Lbl) m3Lbl.textContent = t("dom_" + dom + "_m3_lbl", "");
      if (m3Val) m3Val.textContent = t("dom_" + dom + "_m3_val", "");
    }

    function selectDomain(dom) {
      if (!domainConfig[dom]) return;
      currentDomain = dom;
      for (var i = 0; i < tabs.length; i++) {
        tabs[i].classList.toggle("active", tabs[i].getAttribute("data-domain") === dom);
      }
      syncShowcaseText(dom);
    }

    for (var i = 0; i < tabs.length; i++) {
      tabs[i].addEventListener("click", function () {
        selectDomain(this.getAttribute("data-domain"));
      });
    }

    if (window.autobiI18n && typeof window.autobiI18n.onChange === "function") {
      window.autobiI18n.onChange(function () {
        syncShowcaseText(currentDomain);
      });
    }

    syncShowcaseText(currentDomain);

    var width = 0;
    var height = 0;
    var dpr = 1;
    function resize() {
      var rect = canvas.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      width = rect.width;
      height = rect.height;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    resize();
    if (typeof ResizeObserver !== "undefined") {
      new ResizeObserver(resize).observe(canvas);
    } else {
      window.addEventListener("resize", resize);
    }

    var inView = true;
    observeVisibility(canvas, function (v) {
      inView = v;
    });

    function draw(ts) {
      if (inView && !document.hidden && width > 10 && height > 10) {
        var pal = getPalette();
        var cfg = domainConfig[currentDomain];

        // Smooth morph interpolation toward active domain values
        for (var j = 0; j < 5; j++) {
          curPrev[j] = lerp(curPrev[j], cfg.prev[j], 0.1);
          curCurr[j] = lerp(curCurr[j], cfg.curr[j], 0.1);
        }

        ctx.clearRect(0, 0, width, height);
        ctx.fillStyle = pal.bg;
        ctx.fillRect(0, 0, width, height);

        // Floor baseline & subtle percentage guide lines
        var padX = 44;
        var baseY = height - 42;
        var maxH = height - 104;

        ctx.strokeStyle = pal.grid;
        ctx.lineWidth = 1;
        for (var g = 0; g <= 4; g++) {
          var gy = baseY - (maxH * g) / 4;
          ctx.beginPath();
          ctx.moveTo(padX - 10, gy);
          ctx.lineTo(width - padX + 10, gy);
          ctx.stroke();

          ctx.fillStyle = pal.muted;
          ctx.font = "600 9.5px Inter, sans-serif";
          ctx.textAlign = "right";
          ctx.textBaseline = "middle";
          ctx.fillText(g * 25 + "%", padX - 14, gy);
        }

        // Draw 5 paired isometric comparison bars (Prev Period vs Current Period)
        var usableW = width - padX * 2;
        var slotW = usableW / 5;
        var barW = Math.min(20, Math.max(12, slotW * 0.24));
        var trendPts = [];

        for (var b = 0; b < 5; b++) {
          var cx = padX + slotW * (b + 0.5);
          var breathe = REDUCED_MOTION ? 0 : Math.sin(ts * 0.002 + b * 0.9) * 2.2;
          var prevH = curPrev[b] * maxH;
          var currH = curCurr[b] * maxH + breathe;

          // Back/left bar: Previous period baseline
          drawIsoBar(ctx, cx - barW * 0.62, baseY, barW, prevH, 7, -5, {
            top: pal.prevTop,
            front: pal.prevFront,
            side: pal.prevSide,
            shadow: pal.shadow
          });

          // Front/right bar: Current period AutoBI result
          var positive = cfg.deltas[b].indexOf("-") !== 0;
          var barColors = positive
            ? {
                top: isLightMode() ? "#34D399" : "#6EE7B7",
                front: pal.teal,
                side: isLightMode() ? "#047857" : "#059669",
                shadow: pal.shadow
              }
            : {
                top: isLightMode() ? "#FBBF24" : "#FCD34D",
                front: pal.accent,
                side: isLightMode() ? "#B45309" : "#D97706",
                shadow: pal.shadow
              };

          drawIsoBar(ctx, cx + barW * 0.62, baseY, barW, currH, 7, -5, barColors);
          trendPts.push({ x: cx + barW * 0.62 + 3, y: baseY - currH - 8 });

          // Category X-axis label
          ctx.fillStyle = pal.muted;
          ctx.font = "600 11px Inter, sans-serif";
          ctx.textAlign = "center";
          ctx.textBaseline = "top";
          ctx.fillText(cfg.labels[b], cx, baseY + 11);

          // Percentage comparison badge above bar pair
          var badgeTxt = cfg.deltas[b];
          ctx.font = "700 10px Inter, sans-serif";
          var bw = ctx.measureText(badgeTxt).width + 12;
          var badgeY = baseY - Math.max(prevH, currH) - 32;
          drawRoundedRect(ctx, cx - bw / 2, badgeY, bw, 18, 9);
          ctx.fillStyle = positive ? pal.tealSoft : pal.accentSoft;
          ctx.fill();
          ctx.fillStyle = positive ? pal.teal : pal.accent;
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(badgeTxt, cx, badgeY + 9);
        }

        // Smooth trend spline linking bar tops
        if (trendPts.length >= 2) {
          ctx.strokeStyle = pal.blue;
          ctx.lineWidth = 2.2;
          ctx.beginPath();
          ctx.moveTo(trendPts[0].x, trendPts[0].y);
          for (var p = 1; p < trendPts.length; p++) {
            var midX = (trendPts[p - 1].x + trendPts[p].x) / 2;
            var midY = (trendPts[p - 1].y + trendPts[p].y) / 2;
            ctx.quadraticCurveTo(trendPts[p - 1].x, trendPts[p - 1].y, midX, midY);
          }
          ctx.lineTo(trendPts[trendPts.length - 1].x, trendPts[trendPts.length - 1].y);
          ctx.stroke();

          for (var d = 0; d < trendPts.length; d++) {
            ctx.fillStyle = pal.cardBg;
            ctx.beginPath();
            ctx.arc(trendPts[d].x, trendPts[d].y, 3.6, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = pal.blue;
            ctx.lineWidth = 1.8;
            ctx.stroke();
          }
        }
      }

      requestAnimationFrame(draw);
    }

    requestAnimationFrame(draw);
  }

  function boot() {
    initHeroStoryMotion();
    initSchema3D();
    initDomainShowcase();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
