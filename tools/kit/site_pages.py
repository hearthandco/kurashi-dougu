"""サイトの固定ページ（トップ・サイトについて・お問い合わせ・プライバシーポリシー）とテーマ色CSSを作る。

- セットアップ時（setup_wizard.py）に1回
- 毎日の実行の最後（run_daily.py）にも呼ばれ、トップページの「新着の商品ガイド」を更新する
内容は tools/rakuten-lp/config.json（サイト名・運営者名・お問い合わせ先・テーマ色）から作る。
"""

import html
import json
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "tools" / "rakuten-lp" / "config.json"
DB_PATH = REPO_ROOT / "tools" / "rakuten-lp" / "data" / "database.json"


def e(s) -> str:
    return html.escape(str(s or ""), quote=True)


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def _favicon(config: dict) -> str:
    import sys
    sys.path.insert(0, str(REPO_ROOT / "tools" / "rakuten-lp"))
    from listing import favicon_for  # noqa: E402
    return favicon_for(config)


def _logo(config: dict) -> str:
    return (config.get("logo_text") or config.get("site_name") or "S").strip()[:2]


def _layout(config: dict, page: str, title: str, desc: str, body: str) -> str:
    base = config["site_base_url"].rstrip("/")
    name = config["site_name"]
    url = f"{base}/" if page == "index.html" else f"{base}/{page}"
    full_title = f"{name}｜{title}" if page == "index.html" else f"{title} | {name}"

    def nav_item(href, label):
        cur = ' aria-current="page"' if href == page else ""
        return f'<li><a href="{href}"{cur}>{label}</a></li>'

    nav = "".join(nav_item(h, l) for h, l in (("index.html", "ホーム"), ("products/", "商品ガイド"), ("about.html", "サイトについて"), ("contact.html", "お問い合わせ")))
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{e(full_title)}</title>
  <meta name="description" content="{e(desc)}">
  <meta name="robots" content="index,follow">
  <link rel="canonical" href="{e(url)}">
  <link rel="icon" type="image/svg+xml" href="{_favicon(config)}">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="{e(name)}">
  <meta property="og:title" content="{e(full_title)}">
  <meta property="og:description" content="{e(desc)}">
  <meta property="og:url" content="{e(url)}">
  <meta property="og:image" content="{e(base)}/products/assets/og-default.png">
  <meta property="og:locale" content="ja_JP">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="stylesheet" href="css/style.css">
  <link rel="stylesheet" href="css/theme.css">
  <link rel="stylesheet" href="products/assets/lp.css">
</head>
<body>
  <a class="skip-link" href="#main-content">メインコンテンツへスキップ</a>
  <header class="site-header">
    <div class="container header-inner">
      <a class="site-logo" href="index.html"><span class="site-logo-mark" aria-hidden="true">{e(_logo(config))}</span>{e(name)}</a>
      <button type="button" class="nav-toggle" aria-expanded="false" aria-controls="primary-nav" aria-label="メニューを開閉する"><span></span><span></span><span></span></button>
      <nav id="primary-nav" class="site-nav" aria-label="メインナビゲーション"><ul>{nav}</ul></nav>
    </div>
  </header>
  <div class="lp-pr" role="note"><div class="container"><span class="lp-pr-badge">PR</span>当サイトの商品ガイドには、楽天アフィリエイトの広告リンクが含まれます。</div></div>
  <main id="main-content">
{body}
  </main>
  <footer class="site-footer">
    <div class="container footer-inner">
      <p class="site-logo"><span class="site-logo-mark" aria-hidden="true">{e(_logo(config))}</span>{e(name)}</p>
      <nav class="footer-nav" aria-label="フッターナビゲーション"><ul>
        <li><a href="about.html">サイトについて</a></li><li><a href="products/">商品ガイド</a></li>
        <li><a href="contact.html">お問い合わせ</a></li><li><a href="privacy.html">プライバシーポリシー</a></li></ul></nav>
      <p class="footer-copyright">&copy; <span data-current-year>{date.today().year}</span> {e(name)}</p>
    </div>
  </footer>
  <script src="js/main.js" defer></script>
</body>
</html>
"""


def _latest_cards(limit: int = 12) -> str:
    try:
        db = json.loads(DB_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    recs = [r for r in db.get("products", {}).values()
            if r.get("status") == "published" and (REPO_ROOT / r.get("lp_path", "_")).exists() and r.get("images")]
    recs.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    cards = []
    for r in recs[:limit]:
        img = r["images"][0].split("?")[0]
        if "thumbnail.image.rakuten.co.jp" in img:
            img += "?_ex=300x300"
        href = r["lp_path"].replace("index.html", "")
        cards.append(f'<li class="lp-related-card"><a href="{e(href)}"><img src="{e(img)}" width="300" height="300" alt="{e(r.get("display_name"))}" loading="lazy" decoding="async">'
                     f'<span class="lp-related-cat">{e(r.get("category_label"))}</span><span class="lp-related-name">{e(r.get("title") or r.get("display_name"))}</span></a></li>')
    return "".join(cards)


def build_index(config: dict) -> str:
    name = config["site_name"]
    cards = _latest_cards()
    latest = (f'<ul class="lp-related lp-related--grid">{cards}</ul>' if cards
              else '<p class="notice">商品ガイドは準備中です。公開されるとここに新着順で表示されます。</p>')
    body = f"""    <section class="hero container">
      <h1>{e(config.get("tagline") or "自分に合う商品か、買う前にサッと確認。")}</h1>
      <p class="lead">{e(name)}は、楽天市場で人気の商品について「どんな人に向いているか」「購入前に確認したい点」を、商品情報をもとに1商品ずつ整理している商品ガイドです。</p>
      <div class="hero-actions"><a class="btn btn-primary" href="products/">商品ガイドを見る</a><a class="btn btn-secondary" href="about.html">サイトについて</a></div>
    </section>
    <section class="section section--muted"><div class="container">
      <h2 class="section-title">新着の商品ガイド</h2>
      {latest}
      <p class="text-center"><a class="btn btn-primary" href="products/">すべての商品ガイドを見る</a></p>
    </div></section>
    <section class="section"><div class="container container--narrow">
      <h2 class="section-title">このサイトの使い方</h2>
      <ol class="step-list"><li>気になる商品を選ぶ</li><li>向いている人・注意点を確認</li><li>楽天市場で最新の価格を確認</li></ol>
      <p class="notice">価格・在庫・ポイントは変動します。購入前に必ず楽天市場の商品ページで最新情報をご確認ください。</p>
    </div></section>"""
    return _layout(config, "index.html", "楽天市場の人気商品ガイド", f"{name}は、楽天市場の人気商品を「自分に合うか」の視点で整理した商品ガイドです。", body)


def build_about(config: dict) -> str:
    name, op = config["site_name"], config.get("operator_name") or "運営者"
    body = f"""    <section class="section container container--narrow">
      <h1>サイトについて</h1>
      <h2>{e(name)}とは</h2>
      <p>{e(name)}は、楽天市場で売れている・話題になっている商品について、商品情報（商品説明・価格・レビュー件数など）をもとに「どんな人に向いているか」「購入前にどこを確認すべきか」を整理して紹介するサイトです。</p>
      <h2>情報の作り方</h2>
      <p>掲載している商品情報は、楽天ウェブサービスが提供する公式の商品データを使い、AI（文章作成支援ツール）を活用して整理しています。実際に使った感想や、確認できない効果・性能は記載しない方針です。価格やレビューは記載時点のもので、変動することがあります。</p>
      <h2>広告について</h2>
      <p>当サイトは楽天アフィリエイトに参加しており、商品ページへのリンクには広告（アフィリエイトリンク）が含まれます。広告を含むページには「PR」と表示しています。</p>
      <h2>運営者</h2>
      <p>{e(op)}</p>
    </section>"""
    return _layout(config, "about.html", "サイトについて", f"{name}の運営方針・情報の作り方・広告についての説明です。", body)


def build_contact(config: dict) -> str:
    name, contact = config["site_name"], (config.get("contact") or "").strip()
    if contact.startswith("http"):
        how = f'<p>お問い合わせは、以下のページからお願いいたします。</p><p><a class="btn btn-primary" href="{e(contact)}" rel="nofollow noopener" target="_blank">お問い合わせページを開く</a></p>'
    elif "@" in contact:
        how = f'<p>お問い合わせは、以下のメールアドレスまでお願いいたします（@を半角に変えてください）。</p><p class="notice">{e(contact.replace("@", "＠"))}</p>'
    elif contact:
        how = f'<p>お問い合わせは、以下までお願いいたします。</p><p class="notice">{e(contact)}</p>'
    else:
        how = '<p class="notice">お問い合わせ窓口は現在準備中です。</p>'
    body = f"""    <section class="section container container--narrow">
      <h1>お問い合わせ</h1>
      {how}
      <p>商品の在庫・配送・返品などのご質問は、各商品ページ（楽天市場）の販売ショップへ直接お問い合わせください。</p>
    </section>"""
    return _layout(config, "contact.html", "お問い合わせ", f"{name}へのお問い合わせについてのページです。", body)


def build_privacy(config: dict) -> str:
    name = config["site_name"]
    body = f"""    <section class="section container container--narrow">
      <h1>プライバシーポリシー</h1>
      <h2>広告（アフィリエイトプログラム）について</h2>
      <p>当サイトは、楽天アフィリエイトに参加しています。当サイトのリンクを経由して商品が購入された場合、運営者に報酬が支払われることがあります。広告を含むページには「PR」の表記を行っています。</p>
      <p>アフィリエイトプログラムの提供事業者は、リンクのクリックや購入の計測のためにCookieを使用する場合があります。Cookieはブラウザの設定で無効にできます。</p>
      <p>商品の価格・在庫・仕様などは変動します。購入の際は、リンク先の販売ページで最新の情報をご確認ください。商品の購入や配送・返品に関するお問い合わせは、各販売ショップとお客様との間で行われます。</p>
      <h2>アクセス解析について</h2>
      <p>当サイトでは、現時点でアクセス解析ツールを導入していません。導入する場合は、本ページを更新してお知らせします。</p>
      <h2>個人情報の取り扱いについて</h2>
      <p>お問い合わせなどを通じてご提供いただいた情報は、お問い合わせへの回答の目的の範囲内で適切に取り扱います。</p>
      <h2>著作権について</h2>
      <p>当サイトに掲載する文章の著作権は運営者に帰属します。商品画像は楽天アフィリエイトを通じて提供されている画像であり、著作権は各ショップ・権利者に帰属します。</p>
      <h2>免責事項</h2>
      <p>当サイトの情報は正確性の確保に努めていますが、内容を保証するものではありません。当サイトの利用によって生じた損害について、運営者は責任を負いかねます。</p>
      <h2>本ポリシーの変更について</h2>
      <p>法令の変更やサイト運営方針の変更に応じて、本ポリシーの内容を変更することがあります。</p>
    </section>"""
    return _layout(config, "privacy.html", "プライバシーポリシー", f"{name}のプライバシーポリシー・広告・免責事項について。", body)


def _tint(hex_color: str, ratio: float) -> str:
    """色を白に近づけた淡い色を作る（ratio=0.9 → 90%白）。"""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    mix = lambda v: round(v + (255 - v) * ratio)  # noqa: E731
    return "#{:02x}{:02x}{:02x}".format(mix(r), mix(g), mix(b))


def build_theme_css(config: dict) -> str:
    c = config.get("theme_color") or "#2563eb"
    d = config.get("theme_color_dark") or c
    return (f"/* テーマ色（config.json の theme_color / theme_color_dark から自動生成。直接編集しても次回上書きされます） */\n"
            f":root {{ --color-primary: {c}; --color-primary-dark: {d}; }}\n"
            f".lp-body {{ --lp-accent: {c}; --lp-accent-soft: {_tint(c, 0.92)}; }}\n"
            f".lp-eyebrow {{ border-color: {_tint(c, 0.75)}; }}\n")


def build_all(config: dict = None) -> list:
    config = config or load_config()
    out = {
        "index.html": build_index(config), "about.html": build_about(config),
        "contact.html": build_contact(config), "privacy.html": build_privacy(config),
        "css/theme.css": build_theme_css(config),
    }
    written = []
    for rel, text in out.items():
        p = REPO_ROOT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        written.append(rel)
    return written


if __name__ == "__main__":
    print("作成:", ", ".join(build_all()))
