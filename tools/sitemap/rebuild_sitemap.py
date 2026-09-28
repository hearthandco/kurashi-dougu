#!/usr/bin/env python3
"""sitemap.xml と robots.txt を作り直す（検索エンジンにページの場所を知らせるファイル）。

対象: トップ・固定ページ（about/contact/privacy）・/products/ 以下の各ページ。
URLは tools/rakuten-lp/config.json の site_base_url から作る。
"""

import datetime
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG = REPO_ROOT / "tools" / "rakuten-lp" / "config.json"


def site_base_url() -> str:
    return json.loads(CONFIG.read_text(encoding="utf-8"))["site_base_url"].rstrip("/")


def extract(html: str, pattern: str) -> str:
    m = re.search(pattern, html, re.I | re.S)
    return m.group(1).strip() if m else ""


def product_guide_urls(base: str) -> list:
    root = REPO_ROOT / "products"
    if not (root / "index.html").is_file():
        return []
    urls = [f"{base}/products/"]
    for depth in ("*/index.html", "*/*/index.html"):
        for f in sorted(root.glob(depth)):
            canonical = extract(f.read_text(encoding="utf-8"), r'<link rel="canonical" href="([^"]+)"')
            if canonical and canonical.startswith(base):
                urls.append(canonical)
    return urls


def main() -> None:
    base = site_base_url()
    today = datetime.date.today().isoformat()
    urls = [f"{base}/"] + [f"{base}/{p}" for p in ("about.html", "contact.html", "privacy.html") if (REPO_ROOT / p).exists()]
    urls += product_guide_urls(base)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    lines += [f"  <url><loc>{u}</loc><lastmod>{today}</lastmod></url>" for u in dict.fromkeys(urls)]
    lines.append("</urlset>")
    (REPO_ROOT / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (REPO_ROOT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n", encoding="utf-8")
    print(f"sitemap.xml を更新しました（{len(urls)}ページ）")


if __name__ == "__main__":
    main()
