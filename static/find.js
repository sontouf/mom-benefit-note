// 맞춤 찾기: find.json 을 받아 브라우저 안에서만 필터링한다 (입력값 전송·저장 없음).
// 행 형식: [id, name, sido, sigungu, stages[], amountLabel, views, deadlineEnd, summary, incomeCodes[]]
(function () {
  "use strict";
  var PAGE = 24;
  var rows = null, hits = [], shown = 0;
  var $ = function (id) { return document.getElementById(id); };
  var form = $("f");

  function load() {
    if (rows) return Promise.resolve(rows);
    return fetch(HT.data).then(function (r) { return r.json(); }).then(function (d) { rows = d; return d; });
  }

  // 시도를 고르면 시군구 목록 채우기
  form.sido.addEventListener("change", function () {
    var sel = form.sigungu, sido = form.sido.value;
    sel.innerHTML = '<option value="">시군구 전체</option>';
    sel.disabled = !sido;
    if (!sido) return;
    load().then(function (data) {
      var seen = {};
      data.forEach(function (r) { if (r[2] === sido && r[3]) seen[r[3]] = 1; });
      Object.keys(seen).sort().forEach(function (sg) {
        var o = document.createElement("option");
        o.value = o.textContent = sg;
        sel.appendChild(o);
      });
    });
  });

  function score(r, q) {
    if (r[2]) {
      if (!q.sido || r[2] !== q.sido) return -1;
      if (q.sigungu && r[3] && r[3] !== q.sigungu) return -1;
    }
    if (q.income && r[9].length && r[9].indexOf(q.income) < 0) return -1;
    var hit = q.stages.length ? r[4].filter(function (s) { return q.stages.indexOf(s) >= 0; }).length : 1;
    if (!hit) return -1;
    return hit * 400 + (r[3] ? 300 : r[2] ? 150 : 0) + (r[5] ? 200 : 0) + Math.log(1 + r[6]) * 40;
  }

  function dday(end) {
    if (!end) return null;
    var today = new Date(); today.setHours(0, 0, 0, 0);
    var days = Math.round((new Date(end + "T00:00:00") - today) / 864e5);
    if (days < 0) return null;
    return { label: days === 0 ? "오늘 마감" : "D-" + days, hot: days <= 7 };
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  }

  function render() {
    var box = $("results");
    hits.slice(shown, shown + PAGE).forEach(function (h) {
      var r = h.r, a = el("a", "card");
      a.href = HT.svc + encodeURIComponent(r[0]) + "/";
      if (r[5]) a.appendChild(el("p", "amt", r[5]));
      a.appendChild(el("h3", null, r[1]));
      a.appendChild(el("p", "sum", r[8]));
      var foot = el("div", "card-foot"), d = dday(r[7]);
      if (d) foot.appendChild(el("span", "badge" + (d.hot ? " hot" : ""), d.label));
      foot.appendChild(el("span", "where", r[3] || r[2] || "전국"));
      a.appendChild(foot);
      box.appendChild(a);
    });
    shown += PAGE;
    $("more").hidden = shown >= hits.length;
  }

  form.addEventListener("submit", function (ev) {
    ev.preventDefault();
    var fd = new FormData(form);
    var q = { stages: fd.getAll("stage"), sido: fd.get("sido"), sigungu: fd.get("sigungu") || "", income: fd.get("income") };
    $("status").textContent = "찾는 중…";
    load().then(function (data) {
      hits = [];
      data.forEach(function (r) { var s = score(r, q); if (s >= 0) hits.push({ r: r, s: s }); });
      hits.sort(function (a, b) { return b.s - a.s; });
      $("results").innerHTML = "";
      shown = 0;
      $("status").textContent = hits.length
        ? "받을 수 있을지도 모르는 혜택 " + hits.length.toLocaleString() + "건 (우리 동네·금액 확인되는 순)"
        : "조건에 맞는 혜택이 없어요. 상황을 더 골라 보세요.";
      render();
      $("status").scrollIntoView({ behavior: "smooth", block: "start" });
    }).catch(function () { $("status").textContent = "데이터를 불러오지 못했어요. 새로고침 해주세요."; });
  });
  $("more").addEventListener("click", render);
})();
