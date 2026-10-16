"""링크 미리보기 이미지(static/og.png, 1200×630)를 다시 만든다. 디자인을 바꿨을 때만 실행."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jinja2 import Environment, FileSystemLoader  # noqa: E402

from hyetaek.threads import find_chrome  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
chrome = find_chrome() or sys.exit("Chrome 을 찾을 수 없습니다 (CHROME_BIN 설정).")
html = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=True).get_template("og.html").render(
    site_name=os.environ.get("SITE_NAME", "엄마혜택노트"), emoji=(ROOT / "static" / "emoji").as_uri())
with tempfile.TemporaryDirectory() as d:
    src = Path(d) / "og.html"
    src.write_text(html, encoding="utf-8")
    out = ROOT / "static" / "og.png"
    subprocess.run([chrome, "--headless", "--no-sandbox", "--hide-scrollbars", "--window-size=1200,630",
                    "--force-device-scale-factor=1", "--virtual-time-budget=5000", f"--screenshot={out}", src.as_uri()],
                   check=True, capture_output=True)
print(f"저장 → {out}")
