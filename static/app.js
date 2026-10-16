// 공유 버튼, 체크리스트 저장 (이 브라우저에만).
(function () {
  "use strict";

  function toast(msg) {
    var t = document.createElement("div");
    t.className = "toast";
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function () { t.remove(); }, 2200);
  }

  document.querySelectorAll("[data-share]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var data = { title: btn.dataset.title, text: btn.dataset.title + " — 신청 안 하면 0원이래요", url: location.href };
      if (navigator.share) {
        navigator.share(data).catch(function () {});
      } else if (navigator.clipboard) {
        navigator.clipboard.writeText(data.text + "\n" + data.url)
          .then(function () { toast("링크를 복사했어요. 단톡방에 붙여넣기 하세요"); });
      }
    });
  });

  document.querySelectorAll(".checklist").forEach(function (list) {
    var key = "ck:" + list.dataset.key, done = {};
    try { done = JSON.parse(localStorage.getItem(key) || "{}"); } catch (e) { done = {}; }
    list.querySelectorAll("input[type=checkbox]").forEach(function (cb) {
      var li = cb.closest("li");
      cb.checked = !!done[cb.value];
      li.classList.toggle("done", cb.checked);
      cb.addEventListener("change", function () {
        done[cb.value] = cb.checked;
        li.classList.toggle("done", cb.checked);
        try {
          localStorage.setItem(key, JSON.stringify(done));
        } catch (e) { /* 저장 불가 환경 */ }
      });
    });
  });
})();
