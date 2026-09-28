"""接続テスト（診断）。「2_接続テスト」をダブルクリックすると起動します。

楽天API・Gemini・GitHub・公開サイトに正しくつながるかを1つずつ確認し、
うまくいかない項目には「どうすれば直るか」を表示します。LPは作りません。
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_DIR = REPO_ROOT / "tools" / "rakuten-lp"
sys.path.insert(0, str(TOOL_DIR))

results = []


def mark(ok, name, detail="", fix=""):
    results.append(ok)
    print(("  ✅ " if ok else "  ❌ ") + name + (f"：{detail}" if detail else ""), flush=True)
    if not ok and fix:
        for line in fix.splitlines():
            print(f"     → {line}", flush=True)


def main() -> int:
    if os.name == "nt":
        os.system("")
    print("=" * 56)
    print("  接続テスト（LPは作りません）")
    print("=" * 56)
    try:
        import requests
    except ImportError:
        print("  … 通信用の部品(requests)をインストールしています", flush=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "--user", "--disable-pip-version-check", "requests"])
        try:
            import site
            import importlib
            sys.path.append(site.getusersitepackages())
            importlib.invalidate_caches()
            import requests  # noqa: F401
        except ImportError:
            mark(False, "requests", "インストールできませんでした", "インターネット接続を確認し、もう一度実行してください")
            return 1
    from common import load_config, load_env_files
    config = load_config()
    load_env_files(config)

    # 1. 設定
    ai_key = {"openai": "OPENAI_API_KEY", "claude": "ANTHROPIC_API_KEY"}.get(str(config.get("ai_provider", "gemini")).lower(), "GEMINI_API_KEY")
    missing = [k for k in ("RAKUTEN_APPLICATION_ID", "RAKUTEN_ACCESS_KEY", "RAKUTEN_AFFILIATE_ID", ai_key) if not os.getenv(k)]
    mark(not missing, "APIキーの設定", "OK" if not missing else "未入力: " + ", ".join(missing), "「1_初回セットアップ」をもう一度実行して入力してください")

    # 2. IPアドレス
    import rakuten_api
    ip = rakuten_api.current_ip()
    print(f"\n  ■ このパソコンのIPアドレス: {ip}")
    print("    （楽天ウェブサービスの「許可されたIPアドレス」に、この数字が登録されている必要があります）\n")

    # 3. 楽天API
    try:
        items = rakuten_api.ranking(page=1, interval=1.0)
        ok = bool(items)
        sample = (items[0].get("itemName") or "")[:30] if items else ""
        aff_ok = bool(items and str(items[0].get("affiliateUrl", "")).startswith("https://hb.afl.rakuten.co.jp"))
        mark(ok, "楽天API（ランキング取得）", f"{len(items)}件取得 例:「{sample}…」" if ok else "0件")
        mark(aff_ok, "アフィリエイトリンクの発行", "OK" if aff_ok else "アフィリエイトURLが返ってきません",
             "楽天 アフィリエイトID が正しいか確認してください（xxxxxxxx.xxxxxxxx.xxxxxxxx.xxxxxxxx の形）")
    except Exception as e:
        msg = str(e)
        fix = "アプリケーションID・アクセスキーをコピーし直して「1_初回セットアップ」で入力し直してください"
        if "IPアドレス" in msg or "CLIENT_IP" in msg:
            fix = (f"楽天ウェブサービス → アプリ情報の確認 → 編集 →「許可されたIPアドレス」に {ip} を追加して保存\n"
                   "保存後、反映まで数分待ってからもう一度テストしてください（マニュアル第12章 No.2）")
        elif "403" in msg:
            fix = ("アプリケーションタイプが「API/バックエンドサービス」になっているか、APIアクセススコープで「楽天市場API」に"
                   f"チェックが入っているか確認してください。許可IPに {ip} が入っているかも確認（マニュアル第7章）")
        mark(False, "楽天API", msg[:160], fix)

    # 4. 文章作成AI
    import gemini
    gemini.configure(1.0, 3)
    gemini.set_models(config.get("gemini_model"), config.get("gemini_fallback_models"))
    try:
        name = gemini.set_provider(config)
    except gemini.GeminiError as e:
        mark(False, "文章作成AI", str(e), "config.json の ai_provider を gemini / openai / claude のどれかにしてください")
        name = None
    if name:
        chapter = {"Gemini": "8-2", "ChatGPT": "8-3", "Claude": "8-4"}[name]
        try:
            r = gemini.call('次のJSONだけを返してください: {"ok": true, "message": "こんにちは"}', temperature=0)
            mark(bool(r.get("ok")), f"文章作成AI（{name}）", f"応答: {r.get('message', '')}")
        except Exception as e:
            msg = str(e)
            fix = f"{name}のAPIキーをコピーし直して「1_初回セットアップ」で入力し直してください（マニュアル第8章 {chapter}）"
            if "404" in msg or "モデル名" in msg:
                fix = "モデル名が変わった可能性があります。config.json のモデル名を変更してください（マニュアル第12章 No.5）"
            elif "残高" in msg:
                fix = f"{name}の管理画面でクレジットをチャージしてください（マニュアル第8章 {chapter}）"
            elif "上限" in msg or "429" in msg:
                fix = "無料枠・利用上限に達しています。時間をおいて試してください（キー自体は正しく動いています）"
            mark(False, f"文章作成AI（{name}）", msg[:160], fix)

    # 5. GitHub
    try:
        r = subprocess.run(["git", "-C", str(REPO_ROOT), "ls-remote", "--heads", "origin"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=60)
        ok = r.returncode == 0
        mark(ok, "GitHub（アップロード先）", "接続OK" if ok else r.stderr.strip()[:160],
             "「1_初回セットアップ」の最後のアップロードが成功しているか確認してください（マニュアル第9章）")
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        mark(False, "GitHub", type(e).__name__, "Git がインストールされているか確認してください（マニュアル第5章）")

    # 6. 公開サイト
    url = config["site_base_url"].rstrip("/") + "/"
    try:
        r = requests.get(url, timeout=20)
        mark(r.status_code == 200, "公開サイト", f"{url} → {r.status_code}",
             "GitHubの Settings → Pages で公開をONにしてから数分待ってください（マニュアル第10章）")
    except requests.RequestException as e:
        mark(False, "公開サイト", type(e).__name__, "インターネット接続を確認してください")

    print()
    if all(results):
        print("🎉 すべてOKです！ 次は「3_お試し実行」で、LPを1本だけ作ってみましょう。")
    else:
        print("❌ の項目を、→ の説明に沿って直してから、もう一度このテストを実行してください。")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
