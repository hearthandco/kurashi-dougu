"""公開したLPを取り下げる（削除する）。「7_ページを取り下げる」から起動します。

取り下げたいページのURL（またはURLの一部）を貼り付けると、そのページを削除し、
一覧・トップページ・サイトマップを作り直して、GitHubへ反映します。
一度取り下げた商品は、今後自動で作られることもありません。
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "tools" / "rakuten-lp"))
sys.path.insert(0, str(REPO_ROOT / "tools" / "kit"))
sys.path.insert(0, str(REPO_ROOT / "tools" / "sitemap"))


def main() -> int:
    if os.name == "nt":
        os.system("")
    import listing
    import rebuild_sitemap
    import run_daily
    import site_pages
    from common import load_config
    config = load_config()
    db = run_daily.load_db()
    print("取り下げたいページのURLを貼り付けて Enter（例: https://…/products/kitchen/xxxx-10000000/）")
    key = input("▶ URL: ").strip().rstrip("/").split("/")[-1]
    if not key:
        print("URLが入力されませんでした。")
        return 1
    hits = [(code, r) for code, r in db["products"].items() if r.get("status") == "published" and r.get("slug") == key]
    if not hits:
        print(f"「{key}」に当たる公開中のページが見つかりませんでした。URLを確認してください。")
        return 1
    code, rec = hits[0]
    print(f"対象: {rec.get('display_name')}")
    if input("このページを取り下げますか？ (y/N): ").strip().lower() != "y":
        print("中止しました。")
        return 0
    reason = input("理由のメモ（任意・Enterで省略）: ").strip() or "手動で取り下げ"
    run_daily.retract(db, code, reason)
    rec["manual_block"] = True  # 60日後の再挑戦の対象にもしない
    rec["updated_at"] = "9999-12-31T00:00:00+09:00"
    run_daily.save_db(db)
    listing.build_listings(db, config)
    run_daily.refresh_related(db, config)
    run_daily.save_db(db)
    site_pages.build_all(config)
    rebuild_sitemap.main()
    if (REPO_ROOT / ".git").exists():
        try:
            run_daily.publish(0)
            print("✅ 取り下げて、GitHubへ反映しました（数分後にサイトから消えます）")
        except Exception as e:
            print(f"⚠ ページは削除しましたが、GitHubへの反映に失敗しました: {e}")
            print("  次回の「4_本番実行」または自動実行のときに反映されます。")
    else:
        print("✅ 取り下げました")
    return 0


if __name__ == "__main__":
    sys.exit(main())
