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

  function ready(fn) { if (document.readyState !== "loading") fn(); else document.addEventListener("DOMContentLoaded", fn); }
  ready(function () {
    animOK = !!(window.Motion && window.Motion.animate && !reduce);
    M = window.Motion || null;
    tabs(); search(); stickyCta(); counter(); youtube(); reveal();
  });
})();
