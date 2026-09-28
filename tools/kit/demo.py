"""デモ（APIキー・ネット接続なしで動作確認）。「0_まずはデモを見る」から起動します。

同梱のサンプル商品データで、LP作成の流れを最初から最後まで実行し、できあがったページをブラウザで開きます。
本物のサイトを汚さないよう、パソコンの一時フォルダにキットのコピーを作ってその中で動かします。
"""

import os
import shutil
import subprocess
import sys
import tempfile
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    if os.name == "nt":
        os.system("")
    try:
        import requests  # noqa: F401
    except ImportError:
        print("通信用の部品(requests)をインストールしています…", flush=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "--user", "--disable-pip-version-check", "requests"])
    work = Path(tempfile.gettempdir()) / "rakuten-lp-kit-demo"
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    print("デモ用のコピーを作成しています…", flush=True)
    for rel in ("tools", "css", "js", "products/assets"):
        shutil.copytree(REPO_ROOT / rel, work / rel, ignore=shutil.ignore_patterns("logs", "secrets.env", "__pycache__", "database.json", "content"))
    cfg = work / "tools" / "rakuten-lp" / "config.json"
    import json
    c = json.loads(cfg.read_text(encoding="utf-8"))
    c.update({"site_name": c.get("site_name") or "デモ商品ガイド", "audit_per_day": 0, "gemini_interval_sec": 0, "rakuten_interval_sec": 0})
    cfg.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.path.insert(0, str(work / "tools" / "kit"))
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, "-c", "import site_pages; site_pages.build_all()"], cwd=work / "tools" / "kit", env=env)
    r = subprocess.run([sys.executable, str(work / "tools" / "rakuten-lp" / "run_daily.py"), "--mock", "--no-push", "--limit", "3",
                        "--categories", "beauty,living,appliances"], cwd=work, env=env)
    subprocess.run([sys.executable, "-c", "import site_pages; site_pages.build_all()"], cwd=work / "tools" / "kit", env=env)
    page = work / "index.html"
    made = list((work / "products").glob("*/*/index.html"))
    if r.returncode == 0 and page.exists() and made:
        print(f"\n✅ デモ完了！ サンプル商品で {len(made)} ページ作成しました。ブラウザでデモサイトを開きます。", flush=True)
        print("   ※ サンプルデータのため、画像が表示されない・文章が短いことがあります。本番では楽天の実データで作られます。")
        webbrowser.open(page.as_uri())
        return 0
    print("\n❌ デモの実行に失敗しました。上に表示されたメッセージをマニュアル第12章と照らし合わせてください。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
