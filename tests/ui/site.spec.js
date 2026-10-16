import { test, expect } from "@playwright/test";

// 페이지마다 콘솔 에러·JS 예외를 모아 두고, 테스트 끝에 없어야 한다.
const pageErrors = new WeakMap();
test.beforeEach(async ({ page }) => {
  const errs = [];
  pageErrors.set(page, errs);
  page.on("pageerror", (e) => {
    // 페이지 전환 효과(View Transition)를 빠른 이동이 중단시킬 때 브라우저가 남기는 무해한 메시지
    if (/Transition was aborted|ViewTransition/.test(e.message)) return;
    errs.push("pageerror: " + e.message);
  });
  page.on("console", (m) => {
    // 외부 이미지(유튜브 썸네일 등) 차단 같은 네트워크 오류는 제외
    if (m.type() === "error" && !/Failed to load resource|net::ERR/.test(m.text())) errs.push(m.text());
  });
});
test.afterEach(async ({ page }) => {
  expect(pageErrors.get(page) || [], "콘솔 에러가 없어야 해요").toEqual([]);
});

const isMobile = (p) => p !== "desktop-chrome";

test.describe("검색", () => {
  test("히어로 검색을 누르면 바로 열리고 입력칸에 포커스가 간다", async ({ page }) => {
    await page.goto("/");
    const btn = page.locator(".hero-search");
    await btn.waitFor();
    // 클릭 이벤트가 들어간 순간부터 검색창이 보이고 포커스될 때까지의 시간 (브라우저 안에서 측정)
    const ms = await page.evaluate(() => new Promise((res) => {
      const t0 = performance.now();
      document.querySelector(".hero-search").click();
      const tick = () => {
        const layer = document.getElementById("search");
        if (!layer.hidden && document.activeElement && document.activeElement.id === "q") res(performance.now() - t0);
        else requestAnimationFrame(tick);
      };
      tick();
    }));
    expect(ms, "누르자마자(0.3초 안에) 열려야 해요").toBeLessThan(300);
    await expect(page.locator("#search .search-panel")).toBeVisible();
  });

  test("입력하면 결과가 나오고, 누르면 상세로 간다", async ({ page }) => {
    await page.goto("/");
    await page.locator(".hero-search").click();
    await page.locator("#q").fill("첫만남");
    const first = page.locator("#search-results a").first();
    await expect(first).toContainText("첫만남이용권");
    await first.click();
    await expect(page).toHaveURL(/\/s\/\d+\/$/);
    await expect(page.locator("h1")).toContainText("첫만남이용권");
  });

  test("초성 검색 (ㅊㅁㄴ)", async ({ page }) => {
    await page.goto("/");
    await page.locator(".hero-search").click();
    await page.locator("#q").fill("ㅊㅁㄴ");
    await expect(page.locator("#search-results")).toContainText("첫만남이용권");
  });

  test("자주 찾는 검색어 칩, Enter 로 첫 결과 이동", async ({ page }) => {
    await page.goto("/");
    await page.locator(".hero-search").click();
    await page.locator('#search [data-q="아동수당"]').click();
    await expect(page.locator("#search-results a").first()).toBeVisible();
    await page.locator("#q").press("Enter");
    await expect(page).toHaveURL(/\/s\//);
  });

  test("헤더 검색 버튼 · Esc 로 닫기", async ({ page }) => {
    await page.goto("/ranking/");
    await page.locator(".search-btn").click();
    await expect(page.locator("#search")).toBeVisible();
    await expect(page.locator("#q")).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(page.locator("#search")).toBeHidden();
  });

  test("바깥을 누르면 닫힌다", async ({ page }) => {
    await page.goto("/");
    await page.locator(".hero-search").click();
    await page.mouse.click(5, 600);
    await expect(page.locator("#search")).toBeHidden();
  });
});

test.describe("메뉴·탭", () => {
  test("전체 메뉴 열기 → 링크 이동", async ({ page }) => {
    await page.goto("/");
    await page.locator(".menu-btn").click();
    await expect(page.locator("#menu")).toBeVisible();
    await page.locator("#menu").getByRole("link", { name: /유튜브/ }).click();
    await expect(page).toHaveURL(/\/youtube\/$/);
  });

  test("메뉴에서 검색 열기 (포커스 유지)", async ({ page }) => {
    await page.goto("/");
    await page.locator(".menu-btn").click();
    await page.locator("#menu").getByRole("link", { name: "혜택 검색" }).click();
    await expect(page.locator("#menu")).toBeHidden();
    await expect(page.locator("#search")).toBeVisible();
    await expect(page.locator("#q")).toBeFocused();
  });

  test("랭킹 탭 전환", async ({ page }) => {
    await page.goto("/");
    const tabs = page.locator("[data-tabs]").first();
    await tabs.getByRole("tab", { name: /신규|최근/ }).click();
    await expect(page.locator("#home-new")).toBeVisible();
    await expect(page.locator("#home-popular")).toBeHidden();
  });

  test("모바일 하단 탭바", async ({ page }, info) => {
    test.skip(!isMobile(info.project.name), "모바일 전용");
    await page.goto("/");
    const bar = page.locator(".tabbar");
    await expect(bar).toBeVisible();
    await bar.getByRole("link", { name: "소아과" }).click();
    await expect(page).toHaveURL(/\/clinic\/$/);
    await page.locator(".tabbar").getByRole("button", { name: /메뉴/ }).click();
    await expect(page.locator("#menu")).toBeVisible();
  });
});

test.describe("기능", () => {
  test("맞춤 찾기 결과가 나온다", async ({ page }) => {
    await page.goto("/find/");
    await page.locator('label.pill:has(input[value="birth"])').click();
    await page.locator('select[name="sido"]').selectOption("경기도");
    await page.getByRole("button", { name: "우리 집 혜택 찾기" }).click();
    await expect(page.locator("#results .card").first()).toBeVisible();
    await expect(page.locator("#status")).toContainText("건");
  });

  test("체크리스트는 새로고침해도 유지된다", async ({ page }) => {
    await page.goto("/stage/birth/");
    const first = page.locator(".checklist input[type=checkbox]").first();
    await first.check({ force: true });
    await page.reload();
    await expect(page.locator(".checklist input[type=checkbox]").first()).toBeChecked();
  });

  test("상세 페이지: 후기·영상 섹션과 신청 버튼", async ({ page }) => {
    await page.goto("/");
    await page.locator(".hero-search").click();
    await page.locator("#q").fill("첫만남이용권");
    await page.locator("#search-results a").first().click();
    await expect(page.locator("#reviews")).toBeVisible();
    await expect(page.locator("#videos")).toBeVisible();
    await expect(page.locator(".keybox .cta .btn").first()).toBeVisible();
  });
});

test.describe("레이아웃", () => {
  for (const path of ["/", "/find/", "/ranking/", "/youtube/", "/clinic/", "/trend/", "/stage/birth/", "/trend/birth-bonus/"]) {
    test(`가로 넘침 없음 ${path}`, async ({ page }) => {
      await page.goto(path);
      const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(over, "가로 스크롤이 생기면 안 돼요").toBeLessThanOrEqual(1);
      await expect(page.locator("h1").first()).toBeVisible();
    });
  }
});

test.describe("여정 지도·광고", () => {
  test("육아 여정 지도 스테이지로 이동", async ({ page }) => {
    await page.goto("/");
    await page.locator(".jnode").filter({ hasText: "출산" }).first().click();
    await expect(page).toHaveURL(/\/stage\/birth\/$/);
  });

  test("광고 설정이 없으면 광고 자리를 만들지 않는다", async ({ page }) => {
    for (const path of ["/", "/stage/birth/", "/trend/zero-won/"]) {
      await page.goto(path);
      await expect(page.locator("aside.ad")).toHaveCount(0);
    }
  });
});

test.describe("좁은 화면 (360px)", () => {
  test.use({ viewport: { width: 360, height: 740 } });
  for (const path of ["/", "/find/", "/ranking/", "/youtube/", "/clinic/", "/stage/infant/"]) {
    test(`가로 넘침 없음 360px ${path}`, async ({ page }) => {
      await page.goto(path);
      const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(over).toBeLessThanOrEqual(1);
    });
  }
});
