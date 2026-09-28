"""初回セットアップ（対話式）。「1_初回セットアップ」をダブルクリックすると起動します。

やること:
  1. 必要なもの（Python・requests・Git）の確認と自動インストール
  2. サイト名・GitHub・楽天・Gemini の情報を質問して保存
       - APIキーなどの秘密情報 → tools/rakuten-lp/secrets.env（ネットには公開されません）
       - サイト名などの設定     → tools/rakuten-lp/config.json
  3. トップページ・プライバシーポリシーなどの固定ページを作成
  4. GitHubへ最初のアップロード（初回だけブラウザでGitHubのログインが開きます）
何度実行してもOK。Enterだけ押すと、前回入力した値のまま進みます。
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_DIR = REPO_ROOT / "tools" / "rakuten-lp"
CONFIG_PATH = TOOL_DIR / "config.json"
SECRETS_PATH = TOOL_DIR / "secrets.env"

THEMES = [
    ("ブルー（信頼感・家電やガジェット向き）", "#2563eb", "#1d4ed8"),
    ("グリーン（ナチュラル・食品や暮らし向き）", "#15803d", "#166534"),
    ("ピンク（やさしい・美容やベビー向き）", "#db2777", "#be185d"),
    ("オレンジ（元気・セールやキッチン向き）", "#ea580c", "#c2410c"),
    ("ネイビー（落ち着き・大人向け）", "#1e3a8a", "#172554"),
    ("ブラウン（温かみ・インテリア向き）", "#92400e", "#78350f"),
]


def say(msg=""):
    print(msg, flush=True)


def title(msg):
    say()
    say("━" * 56)
    say(f"  {msg}")
    say("━" * 56)


def ask(label, current="", required=True, secret=False, pattern=None, hint=""):
    """質問して答えを返す。Enterだけなら current を使う。"""
    while True:
        shown = ("（入力済み：" + (current[:4] + "…" if secret and len(current) > 6 else current) + "／Enterでそのまま）") if current else ""
        if hint:
            say(f"  ヒント: {hint}")
        v = input(f"▶ {label}{shown}: ").strip().strip('"').strip("'")
        if not v:
            v = current
        if not v and not required:
            return ""
        if not v:
            say("  ⚠ 入力が必要です。")
            continue
        if pattern and not re.fullmatch(pattern, v):
            say("  ⚠ 形式が正しくないようです。コピーし直して、前後に余計な空白や文字が入っていないか確認してください。")
            continue
        return v


def yesno(label, default=True):
    d = "Y/n" if default else "y/N"
    v = input(f"▶ {label} [{d}]: ").strip().lower()
    if not v:
        return default
    return v in ("y", "yes", "はい", "ｙ")


def read_secrets() -> dict:
    out = {}
    if SECRETS_PATH.exists():
        for line in SECRETS_PATH.read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                out[k.strip()] = v.strip()
    return out


def write_secrets(d: dict) -> None:
    lines = ["# ★このファイルはAPIキー（パスワードのようなもの）です。人に見せたり、SNSに載せたりしないでください。",
             "# ★.gitignore によりGitHubには公開されません。",
             ""]
    for k in ("RAKUTEN_APPLICATION_ID", "RAKUTEN_ACCESS_KEY", "RAKUTEN_AFFILIATE_ID", "GEMINI_API_KEY",
              "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LINE_CHANNEL_ACCESS_TOKEN", "LINE_USER_ID"):
        lines.append(f"{k}={d.get(k, '')}")
    SECRETS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(cmd, check=False, capture=True):
    try:
        r = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=capture, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return None
    if check and r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "").strip()[:500])
    return r


# ------------------------------------------------------------------ steps
def step_requirements() -> bool:
    title("STEP 1 / 5  必要なソフトの確認")
    ok = True
    v = sys.version_info
    if v < (3, 10):
        say(f"  ❌ Python {v.major}.{v.minor} は古すぎます。マニュアル第4章の手順で Python 3.12 以降を入れ直してください。")
        return False
    say(f"  ✅ Python {v.major}.{v.minor}.{v.micro}")
    try:
        import requests  # noqa: F401
        say("  ✅ requests（通信用の部品）")
    except ImportError:
        say("  … requests（通信用の部品）をインストールします（1分ほどかかります）")
        r = run([sys.executable, "-m", "pip", "install", "--user", "--disable-pip-version-check", "requests"])
        if r is None or r.returncode != 0:
            say("  ❌ requests のインストールに失敗しました。インターネット接続を確認して、もう一度実行してください。")
            say("     " + ((r.stderr if r else "") or "")[-300:])
            ok = False
        else:
            say("  ✅ requests をインストールしました")
    g = run(["git", "--version"])
    if g is None or g.returncode != 0:
        say("  ❌ Git が見つかりません。マニュアル第5章の手順で Git をインストールしてから、もう一度実行してください。")
        ok = False
    else:
        say(f"  ✅ {g.stdout.strip()}")
    return ok


def step_site(config: dict) -> None:
    title("STEP 2 / 5  サイトの情報")
    say("  あなたの商品ガイドサイトの名前などを決めます（あとから何度でも変更できます）。")
    config["site_name"] = ask("サイト名（例: ママの暮らし商品ガイド）", config.get("site_name", "") if config.get("site_name") != "マイ商品ガイド" else "")
    default_logo = config.get("logo_text") if config.get("logo_text") not in ("", "マ") else config["site_name"][:1]
    config["logo_text"] = ask("ロゴの文字（1〜2文字。例: マ）", default_logo, pattern=r".{1,2}")
    say("  テーマ色を選んでください:")
    for i, (label, _, _) in enumerate(THEMES, 1):
        say(f"    {i}. {label}")
    cur = next((str(i) for i, t in enumerate(THEMES, 1) if t[1] == config.get("theme_color")), "1")
    n = int(ask("番号", cur, pattern=r"[1-6]"))
    config["theme_color"], config["theme_color_dark"] = THEMES[n - 1][1], THEMES[n - 1][2]
    config["operator_name"] = ask("運営者名（ニックネームでOK。サイトについてのページに表示）", config.get("operator_name", "") if config.get("operator_name") != "運営者" else "")
    config["contact"] = ask("お問い合わせ先（任意：Googleフォームのリンク、メールアドレス、XのURLなど。無ければEnter）",
                            config.get("contact", ""), required=False)


def step_github(config: dict) -> None:
    title("STEP 3 / 5  GitHub（サイトの公開先）")
    say("  マニュアル第6章で作った GitHub のユーザー名と、リポジトリ名を入力します。")
    m = re.match(r"https://([^.]+)\.github\.io/([^/]+)", config.get("site_base_url", ""))
    cur_user, cur_repo = (m.group(1), m.group(2)) if m and m.group(1) != "YOUR-GITHUB-NAME" else ("", "")
    user = ask("GitHubのユーザー名（例: mama-guide）", cur_user, pattern=r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})",
               hint="GitHub右上の丸いアイコンを押すと表示される名前です")
    repo = ask("リポジトリ名（例: shop-guide）", cur_repo, pattern=r"[A-Za-z0-9._-]{1,100}")
    config["site_base_url"] = f"https://{user.lower()}.github.io/{repo}"
    config["_github_user"], config["_github_repo"] = user, repo
    if not config.get("site_base_url_custom"):
        say(f"  → あなたのサイトのURLは {config['site_base_url']}/ になります")
    else:
        config["site_base_url"] = config["site_base_url_custom"]
        say(f"  → 独自の公開先URL {config['site_base_url']} を使います（site_base_url_custom が設定されています）")


AIS = [
    ("gemini", "Gemini（Google）…… 無料枠で0円運用（おすすめ）", "GEMINI_API_KEY", "Gemini APIキー（AIza で始まる）",
     r"[A-Za-z0-9_\-.]{20,200}", "Google AI Studio → API キー で作ったキー（マニュアル第8章 8-2）"),
    ("openai", "ChatGPT（OpenAI API）…… 従量課金・1本あたり約1〜2円の目安", "OPENAI_API_KEY", "OpenAI APIキー（sk- で始まる）",
     r"sk-[A-Za-z0-9_\-]{20,300}", "OpenAI Platform → API keys で作ったキー（マニュアル第8章 8-3）"),
    ("claude", "Claude（Anthropic API）…… 従量課金・1本あたり約10円の目安", "ANTHROPIC_API_KEY", "Claude APIキー（sk-ant- で始まる）",
     r"sk-ant-[A-Za-z0-9_\-]{20,300}", "Claude Console → API Keys で作ったキー（マニュアル第8章 8-4）"),
]


def step_keys(secrets: dict, config: dict) -> None:
    title("STEP 4 / 5  APIキー（楽天・文章作成AI）")
    say("  マニュアル第7章・第8章でメモした値を、コピー＆貼り付けしてください。")
    say("  （Windowsの黒い画面は右クリック、Macのターミナルは ⌘+V で貼り付けできます）")
    say()
    secrets["RAKUTEN_APPLICATION_ID"] = ask("楽天 アプリケーションID", secrets.get("RAKUTEN_APPLICATION_ID", ""), secret=True,
                                            pattern=r"[A-Za-z0-9-]{8,80}", hint="楽天ウェブサービス → アプリ情報の確認 → アプリケーションID")
    secrets["RAKUTEN_ACCESS_KEY"] = ask("楽天 アクセスキー", secrets.get("RAKUTEN_ACCESS_KEY", ""), secret=True,
                                        pattern=r"[A-Za-z0-9_\-]{8,120}", hint="同じ画面の「アクセスキー」（目のマークで表示）")
    secrets["RAKUTEN_AFFILIATE_ID"] = ask("楽天 アフィリエイトID", secrets.get("RAKUTEN_AFFILIATE_ID", ""), secret=True,
                                          pattern=r"[0-9a-f]{8}\.[0-9a-f]{8}\.[0-9a-f]{8}\.[0-9a-f]{8}",
                                          hint="「xxxxxxxx.xxxxxxxx.xxxxxxxx.xxxxxxxx」の形の文字列")
    say()
    say("  文章を書くAIを選んでください（あとから変更できます）:")
    for i, a in enumerate(AIS, 1):
        say(f"    {i}. {a[1]}")
    cur = next((str(i) for i, a in enumerate(AIS, 1) if a[0] == config.get("ai_provider", "gemini")), "1")
    ai = AIS[int(ask("番号", cur, pattern=r"[1-3]")) - 1]
    config["ai_provider"] = ai[0]
    secrets[ai[2]] = ask(ai[3], secrets.get(ai[2], ""), secret=True, pattern=ai[4], hint=ai[5])
    if ai[0] != "gemini":
        say("  ※ 有料のAIです。使いすぎ防止のため、管理画面で「月の上限金額」も設定しておいてください（マニュアル第8章）。")
    if yesno("LINEに実行結果を通知しますか？（任意・付録Bの設定が必要）", default=bool(secrets.get("LINE_USER_ID"))):
        secrets["LINE_CHANNEL_ACCESS_TOKEN"] = ask("LINE チャネルアクセストークン", secrets.get("LINE_CHANNEL_ACCESS_TOKEN", ""), secret=True)
        secrets["LINE_USER_ID"] = ask("LINE あなたのユーザーID（Uから始まる）", secrets.get("LINE_USER_ID", ""), pattern=r"U[0-9a-f]{32}")
    write_secrets(secrets)
    say("  ✅ secrets.env に保存しました（GitHubには公開されません）")


def build_site(config: dict) -> None:
    sys.path.insert(0, str(TOOL_DIR))
    sys.path.insert(0, str(REPO_ROOT / "tools" / "kit"))
    sys.path.insert(0, str(REPO_ROOT / "tools" / "sitemap"))
    import listing  # noqa: E402
    import rebuild_sitemap  # noqa: E402
    import site_pages  # noqa: E402
    from common import DB_PATH, read_json  # noqa: E402
    db = read_json(DB_PATH, {"products": {}})
    listing.build_listings(db, config)
    site_pages.build_all(config)
    rebuild_sitemap.main()


def step_publish(config: dict) -> None:
    title("STEP 5 / 5  GitHubへアップロード")
    user, repo = config.get("_github_user"), config.get("_github_repo")
    remote = f"https://github.com/{user}/{repo}.git"
    if not (REPO_ROOT / ".git").exists():
        run(["git", "init"], check=True)
        run(["git", "checkout", "-B", "main"], check=True)
    run(["git", "config", "user.name", user], check=True)
    run(["git", "config", "user.email", f"{user}@users.noreply.github.com"], check=True)
    run(["git", "config", "core.quotepath", "false"])
    r = run(["git", "remote", "get-url", "origin"])
    if r.returncode != 0:
        run(["git", "remote", "add", "origin", remote], check=True)
    elif r.stdout.strip() != remote:
        run(["git", "remote", "set-url", "origin", remote], check=True)

    ignored = run(["git", "check-ignore", "tools/rakuten-lp/secrets.env"])
    if not ignored or ignored.returncode != 0:
        say("  ❌ secrets.env が公開対象になっています。.gitignore ファイルを消していないか確認してください。中止します。")
        return
    run(["git", "add", "-A"], check=True)
    staged = run(["git", "diff", "--cached", "--name-only"]).stdout
    if "secrets.env" in staged:
        run(["git", "reset"])
        say("  ❌ secrets.env が公開対象になっています。中止しました。")
        return
    if staged.strip():
        run(["git", "commit", "-m", "サイトの初期設定"], check=True)
    say("  GitHubへアップロードします。初回はブラウザ（またはウィンドウ）が開いて")
    say("  GitHubへのログインを求められます →「Sign in with your browser」→「Authorize」を押してください。")
    r = run(["git", "push", "-u", "origin", "main"], capture=False)
    if r is not None and r.returncode == 0:
        say("  ✅ アップロード完了！")
        say("  次は GitHub の Settings → Pages で公開をONにします（マニュアル第10章）。")
        say(f"  数分後に {config['site_base_url']}/ でサイトが見られるようになります。")
    else:
        say("  ❌ アップロードに失敗しました。よくある原因:")
        say(f"     ・GitHubにリポジトリ「{repo}」を作っていない／名前が違う（大文字小文字も区別されます）")
        say("     ・リポジトリ作成時に README を追加してしまった → マニュアル第12章「トラブル解決」の No.6 を参照")
        say("     ・ログイン画面で別のアカウントを選んだ")


def main() -> int:
    if os.name == "nt":
        os.system("")  # Windowsの画面で色・記号を正しく出すため
    say("=" * 56)
    say("  楽天LP自動作成キット  初回セットアップ")
    say("=" * 56)
    if not step_requirements():
        return 1
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    secrets = read_secrets()
    step_site(config)
    step_github(config)
    step_keys(secrets, config)
    gh = (config.pop("_github_user"), config.pop("_github_repo"))
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    say("  ✅ config.json に保存しました")
    build_site(config)
    say("  ✅ トップページ・サイトについて・お問い合わせ・プライバシーポリシーを作成しました")
    config["_github_user"], config["_github_repo"] = gh
    if yesno("GitHubへアップロードしますか？（初回は必ず Y）", True):
        step_publish(config)
    say()
    say("セットアップは以上です。次は「2_接続テスト」をダブルクリックして、楽天とGeminiにつながるか確認しましょう。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        say("\n中断しました。もう一度「1_初回セットアップ」を実行すれば続きからやり直せます。")
        sys.exit(1)
