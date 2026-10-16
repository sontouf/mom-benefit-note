// 엄마혜택노트 인터랙션: motion 애니메이션, 검색(초성 지원), 랭킹 탭, 카운트업, 방문자 카운터.
// 모든 기능은 점진적 향상 — JS나 motion 이 없어도 내용은 그대로 보인다.
(function () {
  "use strict";
  var M = window.Motion || null;
  var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var animOK = !!(M && M.animate && !reduce);
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var EASE = [0.22, 1, 0.36, 1];

  // ---------- 숫자 카운트업 ----------
  function countUp(el) {
    var to = parseInt(el.getAttribute("data-count"), 10);
    if (!animOK || !isFinite(to) || to < 10) return;
    M.animate(0, to, {
      duration: Math.min(1.6, 0.6 + to / 4000), ease: EASE,
      onUpdate: function (v) { el.textContent = Math.round(v).toLocaleString("ko-KR"); },
    });
  }

  // ---------- 스크롤 등장 애니메이션 ----------
  // 안전장치: 숨겨 둔 요소는 애니메이션이 끝나면 인라인 스타일을 지우고,
  // 2.5초 안에 시작되지 않으면(검색 로봇·저사양 기기) 그냥 보이게 한다.
  var pending = [];
  function hide(el) { el.style.opacity = "0"; el.__mbPending = true; pending.push(el); }
  function show(els, kf, opts) {
    els.forEach(function (e) { e.__mbPending = false; });
    var a = M.animate(els, kf, opts);
    var done = function () { els.forEach(function (e) { e.style.opacity = ""; e.style.transform = ""; }); };
    if (a && a.finished) a.finished.then(done, done); else setTimeout(done, 1500);
  }
  setTimeout(function () {
    pending.forEach(function (el) {
      var r = el.getBoundingClientRect();
      if (el.__mbPending && r.top < window.innerHeight * 1.5) { el.style.opacity = ""; el.__mbPending = false; }
    });
  }, 2500);

  function reveal() {
    if (!animOK || !M.inView) return;
    var vh = window.innerHeight;
    var groups = $$(".grid, .tgrid, .tiles, .rank-list, .checklist, .rank, .chips, [data-stagger]");
    groups.forEach(function (g) {
      var kids = Array.prototype.slice.call(g.children).filter(function (k) { return k.tagName !== "SPAN"; });
      if (!kids.length || g.getBoundingClientRect().top < vh * 0.9) return; // 첫 화면은 손대지 않는다
      kids.forEach(hide);
      M.inView(g, function () {
        show(kids, { opacity: [0, 1], transform: ["translateY(14px)", "none"] },
          { duration: 0.5, ease: EASE, delay: M.stagger(0.04, { startDelay: 0.05 }) });
      }, { amount: 0.1 });
    });
    $$("[data-reveal]").forEach(function (el, i) {
      if (el.getBoundingClientRect().top < vh) {
        // 첫 화면: 투명도는 그대로 두고 살짝 떠오르는 움직임만
        M.animate(el, { transform: ["translateY(8px)", "none"] }, { duration: 0.6, ease: EASE, delay: 0.05 * i });
      } else {
        hide(el);
        M.inView(el, function () {
          show([el], { opacity: [0, 1], transform: ["translateY(16px)", "none"] }, { duration: 0.6, ease: EASE });
        });
      }
    });
    // 랭킹 막대가 0에서 자라도록 (bklit 차트 느낌)
    $$("[data-bar]").forEach(function (b) {
      var w = b.style.width;
      M.inView(b, function () {
        M.animate(b, { width: ["0%", w] }, { duration: 0.9, ease: EASE, delay: 0.1 });
      });
    });
    $$("[data-count]").forEach(function (el) { M.inView(el, function () { countUp(el); }); });
  }

  // ---------- 랭킹 탭 ----------
  function tabs() {
    $$("[data-tabs]").forEach(function (bar) {
      var btns = $$("[role=tab]", bar), ink = $(".tab-ink", bar);
      function moveInk(btn, instant) {
        if (!ink) return;
        var x = btn.offsetLeft, w = btn.offsetWidth;
        if (animOK && !instant) M.animate(ink, { transform: "translateX(" + x + "px)", width: w + "px" }, { type: "spring", stiffness: 400, damping: 34 });
        else { ink.style.transform = "translateX(" + x + "px)"; ink.style.width = w + "px"; }
      }
      btns.forEach(function (btn, i) {
        btn.addEventListener("click", function () {
          btns.forEach(function (b) {
            var on = b === btn, panel = document.getElementById(b.getAttribute("aria-controls"));
            b.setAttribute("aria-selected", on ? "true" : "false");
            b.tabIndex = on ? 0 : -1;
            if (panel) panel.hidden = !on;
            if (on && panel && animOK) {
              M.animate($$("li, .empty", panel), { opacity: [0, 1], transform: ["translateX(8px)", "none"] },
                { duration: 0.35, ease: EASE, delay: M.stagger(0.025) });
              $$("[data-bar]", panel).forEach(function (b2) {
                var w = b2.style.width;
                M.animate(b2, { width: ["0%", w] }, { duration: 0.7, ease: EASE });
              });
            }
          });
          moveInk(btn);
        });
        btn.addEventListener("keydown", function (e) {
          var d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
          if (!d) return;
          var nb = btns[(i + d + btns.length) % btns.length];
          nb.focus(); nb.click();
        });
      });
      requestAnimationFrame(function () { moveInk(btns[0], true); });
      window.addEventListener("resize", function () {
        moveInk(btns.filter(function (b) { return b.getAttribute("aria-selected") === "true"; })[0] || btns[0], true);
      });
    });
  }

  // ---------- 검색 (초성 검색 지원) ----------
  var CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ";
  function chosung(s) {
    var out = "";
    for (var i = 0; i < s.length; i++) {
      var c = s.charCodeAt(i) - 0xac00;
      out += c >= 0 && c < 11172 ? CHO[Math.floor(c / 588)] : s[i];
    }
    return out;
  }
  function isChosungOnly(q) { return /^[ㄱ-ㅎ\s]+$/.test(q); }

  var rows = null;
  function loadRows() {
    if (rows) return Promise.resolve(rows);
    return fetch(MB.data).then(function (r) { return r.json(); }).then(function (d) {
      rows = d.map(function (r) { return { r: r, n: r[1].replace(/\s/g, ""), c: chosung(r[1].replace(/\s/g, "")) }; });
      return rows;
    });
  }

  function search() {
    var layer = $("#search"), input = $("#q"), list = $("#search-results");
    if (!layer) return;
    var lastFocus = null;
    function open() {
      lastFocus = document.activeElement;
      layer.hidden = false;
      document.body.classList.add("no-scroll");
      if (animOK) {
        M.animate(layer, { opacity: [0, 1] }, { duration: 0.2 });
        M.animate($(".search-panel", layer), { transform: ["translateY(-12px) scale(.98)", "none"], opacity: [0, 1] },
          { type: "spring", stiffness: 420, damping: 32 });
      }
      setTimeout(function () { input.focus(); }, 30);
      loadRows();
    }
    function close() {
      layer.hidden = true;
      document.body.classList.remove("no-scroll");
      if (lastFocus) lastFocus.focus();
    }
    function render(q) {
      list.innerHTML = "";
      q = q.trim().replace(/\s/g, "");
      if (!q) return;
      loadRows().then(function (rs) {
        var cho = isChosungOnly(q);
        var hits = rs.filter(function (x) { return cho ? x.c.indexOf(q) >= 0 : x.n.indexOf(q) >= 0; })
          .sort(function (a, b) {
            var pa = (cho ? a.c : a.n).indexOf(q), pb = (cho ? b.c : b.n).indexOf(q);
            return (pa === 0 ? 0 : 1) - (pb === 0 ? 0 : 1) || (a.r[2] ? 1 : 0) - (b.r[2] ? 1 : 0) || b.r[6] - a.r[6];
          }).slice(0, 30);
        if (!hits.length) {
          var li = document.createElement("li");
          li.className = "none";
          li.textContent = "검색 결과가 없어요. 다른 단어로 찾아보세요.";
          list.appendChild(li);
          return;
        }
        hits.forEach(function (h) {
          var r = h.r, li = document.createElement("li"), a = document.createElement("a");
          a.href = MB.svc + encodeURIComponent(r[0]) + "/";
          var t = document.createElement("strong"); t.textContent = r[1];
          var m = document.createElement("span");
          m.textContent = (r[5] ? r[5] + " · " : "") + (r[3] || r[2] || "전국");
          a.appendChild(t); a.appendChild(m); li.appendChild(a); list.appendChild(li);
        });
        if (animOK) M.animate($$("li", list).slice(0, 12), { opacity: [0, 1], transform: ["translateY(6px)", "none"] },
          { duration: 0.25, delay: M.stagger(0.02) });
      });
    }
    var timer;
    input.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(function () { render(input.value); }, 120); });
    $$("[data-search-open]").forEach(function (b) { b.addEventListener("click", open); });
    $$("[data-search-close]").forEach(function (b) { b.addEventListener("click", close); });
    $$("[data-q]", layer).forEach(function (b) {
      b.addEventListener("click", function () { input.value = b.getAttribute("data-q"); render(input.value); input.focus(); });
    });
    layer.addEventListener("click", function (e) { if (e.target === layer) close(); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !layer.hidden) close();
      if ((e.key === "/" || (e.key === "k" && (e.metaKey || e.ctrlKey))) && layer.hidden &&
          !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) { e.preventDefault(); open(); }
    });
  }

  // ---------- 상세 페이지 하단 고정 신청 버튼 ----------
  function stickyCta() {
    var bar = $("[data-sticky-cta]"), anchor = $(".keybox .cta");
    if (!bar || !anchor || !("IntersectionObserver" in window)) return;
    new IntersectionObserver(function (es) {
      var show = !es[0].isIntersecting && es[0].boundingClientRect.top < 0;
      if (show === bar.classList.contains("show")) return;
      bar.classList.toggle("show", show);
      if (animOK) M.animate(bar, { transform: show ? ["translateY(110%)", "none"] : ["none", "translateY(110%)"] },
        { type: "spring", stiffness: 380, damping: 34 });
    }).observe(anchor);
  }

  // ---------- 방문자 카운터 (COUNTER_URL 이 설정됐을 때만) ----------
  function counter() {
    if (!MB.counter) return;
    var sid;
    try { sid = sessionStorage.getItem("mb-sid"); } catch (e) { sid = null; }
    if (!sid) {
      sid = Math.random().toString(36).slice(2) + Date.now().toString(36);
      try { sessionStorage.setItem("mb-sid", sid); } catch (e) { /* 무시 */ }
    }
    function show(d) {
      if (!d) return;
      $$("[data-live]").forEach(function (el) {
        if (d.live > 0) { el.hidden = false; var b = $("[data-live-now]", el); if (b) b.textContent = d.live.toLocaleString("ko-KR"); }
      });
      var pv = $("[data-page-views]");
      if (pv && d.page_today > 0) { pv.hidden = false; $("b", pv).textContent = d.page_today.toLocaleString("ko-KR"); }
    }
    function send(kind) {
      return fetch(MB.counter + "/" + kind, {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ path: MB.path, sid: sid }), keepalive: true,
      }).then(function (r) { return r.ok ? r.json() : null; }).then(show).catch(function () { /* 카운터 장애는 무시 */ });
    }
    send("hit");
    setInterval(function () { if (document.visibilityState === "visible") send("ping"); }, 60000);
  }

  // ---------- 유튜브 lite embed: 누를 때만 플레이어를 불러온다 ----------
  function youtube() {
    $$("[data-yt]").forEach(function (b) {
      b.addEventListener("click", function () {
        var f = document.createElement("iframe");
        f.src = "https://www.youtube-nocookie.com/embed/" + encodeURIComponent(b.getAttribute("data-yt")) + "?autoplay=1&rel=0";
        f.title = b.getAttribute("aria-label") || "YouTube";
        f.allow = "accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture";
        f.allowFullscreen = true;
        b.replaceWith(f);
      });
    });
  }


  // ---------- 전체 메뉴 ----------
  function menu() {
    var layer = $("#menu");
    if (!layer) return;
    var sheet = $(".menu-sheet", layer), last = null;
    function open() {
      last = document.activeElement;
      layer.hidden = false;
      document.body.classList.add("no-scroll");
      $$("[data-menu-open]").forEach(function (b) { b.setAttribute("aria-expanded", "true"); });
      if (animOK) {
        M.animate(layer, { opacity: [0, 1] }, { duration: 0.2 });
        M.animate(sheet, { transform: ["translateX(100%)", "none"] }, { type: "spring", stiffness: 380, damping: 36 });
        M.animate($$(".menu-sec > a, .menu-grid a", sheet), { transform: ["translateX(24px)", "none"] },
          { duration: 0.35, delay: M.stagger(0.02, { startDelay: 0.08 }) });
      }
      setTimeout(function () { var x = $(".menu-x", layer); if (x) x.focus(); }, 30);
    }
    function close() {
      var done = function () { layer.hidden = true; document.body.classList.remove("no-scroll"); };
      $$("[data-menu-open]").forEach(function (b) { b.setAttribute("aria-expanded", "false"); });
      if (animOK) {
        M.animate(sheet, { transform: "translateX(100%)" }, { duration: 0.25, ease: EASE });
        var a = M.animate(layer, { opacity: 0 }, { duration: 0.25 });
        (a.finished || Promise.resolve()).then(function () { done(); layer.style.opacity = ""; sheet.style.transform = ""; });
      } else done();
      if (last && last.focus) last.focus();
    }
    $$("[data-menu-open]").forEach(function (b) { b.addEventListener("click", open); });
    $$("[data-menu-close]").forEach(function (b) { b.addEventListener("click", function (e) { if (b.tagName === "A" && b.getAttribute("href") === "#") e.preventDefault(); close(); }); });
    layer.addEventListener("click", function (e) { if (e.target === layer) close(); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !layer.hidden) close(); });
  }

  // ---------- 하트·별 파티클 ----------
  var PARTS = ["heart", "pink-heart", "star", "sparkle-heart", "ribbon-heart"];
  function burst(x, y, n) {
    if (!animOK) return;
    n = n || 12;
    for (var i = 0; i < n; i++) {
      var img = document.createElement("img");
      img.src = MB.base + "/static/emoji/" + PARTS[i % PARTS.length] + ".png";
      img.className = "particle"; img.alt = "";
      document.body.appendChild(img);
      var ang = (Math.PI * 2 * i) / n + Math.random() * 0.6, dist = 60 + Math.random() * 70, size = 0.6 + Math.random() * 0.7;
      var dx = Math.cos(ang) * dist, dy = Math.sin(ang) * dist - 40;
      (function (el) {
        var a = M.animate(el, {
          transform: ["translate(" + (x - 14) + "px," + (y - 14) + "px) scale(.2)",
                      "translate(" + (x - 14 + dx) + "px," + (y - 14 + dy) + "px) scale(" + size + ") rotate(" + (Math.random() * 60 - 30) + "deg)",
                      "translate(" + (x - 14 + dx * 1.1) + "px," + (y - 14 + dy + 60) + "px) scale(" + size * 0.8 + ")"],
          opacity: [1, 1, 0],
        }, { duration: 1.1 + Math.random() * 0.4, ease: EASE });
        (a.finished || Promise.resolve()).then(function () { el.remove(); });
      })(img);
    }
  }
  function burstAt(el, n) { var r = el.getBoundingClientRect(); burst(r.left + r.width / 2, r.top + r.height / 2, n); }
  function joy() {
    document.addEventListener("change", function (e) {
      if (e.target.matches(".checklist input[type=checkbox]") && e.target.checked) {
        burstAt(e.target.closest(".ck") || e.target, 10);
        var list = e.target.closest(".checklist");
        if (list && $$("input:not(:checked)", list).length === 0) setTimeout(function () { burstAt(list, 24); }, 250);
      }
    });
    $$("[data-share]").forEach(function (b) { b.addEventListener("click", function () { burstAt(b, 14); }); });
    $$("[data-burst]").forEach(function (st) {
      st.addEventListener("click", function () {
        burstAt(st, 10);
        if (animOK) M.animate(st, { scale: [1, 1.25, 1], rotate: [0, -12, 0] }, { duration: 0.5 });
      });
    });
  }

  // ---------- 히어로 스티커 패럴랙스 (마우스·스크롤) ----------
  function parallax() {
    var box = $("[data-parallax]");
    if (!box || !animOK) return;
    var sts = $$("[data-depth]", box), mx = 0, my = 0, sy = 0, raf = null;
    function apply() {
      raf = null;
      sts.forEach(function (s) {
        var d = parseFloat(s.getAttribute("data-depth")) || 10;
        s.style.transform = "translate(" + (mx * d).toFixed(1) + "px," + (my * d - sy * d * 0.02).toFixed(1) + "px)";
      });
    }
    function req() { if (!raf) raf = requestAnimationFrame(apply); }
    if (matchMedia("(hover: hover)").matches) {
      window.addEventListener("pointermove", function (e) { mx = e.clientX / innerWidth - 0.5; my = e.clientY / innerHeight - 0.5; req(); });
    }
    window.addEventListener("scroll", function () { sy = Math.min(scrollY, 600); req(); }, { passive: true });
    M.animate(sts, { scale: [0.6, 1] }, { type: "spring", stiffness: 260, damping: 14, delay: M.stagger(0.08, { startDelay: 0.2 }) });
  }

  // ---------- 카드 기울기 (데스크톱) ----------
  function tilt() {
    if (!animOK || !matchMedia("(hover: hover) and (pointer: fine)").matches) return;
    $$(".card, .tcard, .chcard, .gcard, .tile").forEach(function (c) {
      c.classList.add("tiltable");
      c.addEventListener("pointermove", function (e) {
        var r = c.getBoundingClientRect(), px = (e.clientX - r.left) / r.width - 0.5, py = (e.clientY - r.top) / r.height - 0.5;
        c.style.transform = "perspective(700px) rotateX(" + (-py * 6).toFixed(2) + "deg) rotateY(" + (px * 6).toFixed(2) + "deg) translateY(-3px)";
      });
      c.addEventListener("pointerleave", function () {
        M.animate(c, { transform: "perspective(700px) rotateX(0deg) rotateY(0deg) translateY(0px)" }, { type: "spring", stiffness: 300, damping: 20 });
      });
    });
  }

  // ---------- 버튼 물결 ----------
  function ripple() {
    document.addEventListener("pointerdown", function (e) {
      var b = e.target.closest(".btn");
      if (!b || !animOK) return;
      var r = b.getBoundingClientRect(), d = Math.max(r.width, r.height) * 2, s = document.createElement("span");
      s.className = "ripple";
      s.style.width = s.style.height = d + "px";
      s.style.left = (e.clientX - r.left - d / 2) + "px"; s.style.top = (e.clientY - r.top - d / 2) + "px";
      b.appendChild(s);
      var a = M.animate(s, { transform: ["scale(0)", "scale(1)"], opacity: [0.3, 0] }, { duration: 0.6, ease: EASE });
      (a.finished || Promise.resolve()).then(function () { s.remove(); });
    });
  }

  // ---------- 스크롤 진행바 · 맨 위로 ----------
  function scrollUi() {
    var bar = $("[data-progress]"), top = $("[data-to-top]");
    function on() {
      var h = document.documentElement.scrollHeight - innerHeight, p = h > 0 ? scrollY / h : 0;
      if (bar) bar.style.transform = "scaleX(" + p.toFixed(4) + ")";
      if (top) {
        var show = scrollY > 900;
        if (show && top.hidden) { top.hidden = false; if (animOK) M.animate(top, { scale: [0.4, 1], opacity: [0, 1] }, { type: "spring", stiffness: 400, damping: 18 }); }
        else if (!show && !top.hidden) top.hidden = true;
      }
    }
    window.addEventListener("scroll", on, { passive: true }); on();
    if (top) top.addEventListener("click", function () { scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" }); });
  }

  // ---------- 섹션 제목 아이콘 통통 ----------
  function hops() {
    if (!animOK) return;
    $$("h2.ih .ico3d").forEach(function (ic) {
      M.inView(ic, function () { M.animate(ic, { scale: [0.3, 1.15, 1], rotate: [-20, 8, 0] }, { duration: 0.7, ease: EASE }); });
    });
  }

  function ready(fn) { if (document.readyState !== "loading") fn(); else document.addEventListener("DOMContentLoaded", fn); }
  ready(function () {
    animOK = !!(window.Motion && window.Motion.animate && !reduce);
    M = window.Motion || null;
    tabs(); search(); stickyCta(); counter(); youtube(); menu(); joy(); parallax(); tilt(); ripple(); scrollUi(); hops(); reveal();
  });
})();
