"""50 benchmark tasks: 10 categories × 5. Each task has a request (goal + inputs) and a deterministic grader that scores
the published artifacts without a model. Expected values are computed here from the same inputs, so graders cannot
drift from the data. Graders never see the run; they only read the latest artifact revisions.

A task's grade is a list of (check_name, passed, detail). `correct` = all checks passed. Programmatic checks are
deliberately strict on file names so that "the agent chose another name" counts as a miss — the request names the files.
"""
from __future__ import annotations

import csv
import io
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Callable

Check = tuple[str, bool, str]
Artifacts = dict[str, str]  # logical_path -> text content (latest revision)


# ----------------------------------------------------------------------------- helpers
def find(arts: Artifacts, name: str) -> str | None:
    """Artifact whose logical path equals `name` or ends with `/name`."""
    if name in arts:
        return arts[name]
    for p, c in arts.items():
        if p.endswith("/" + name):
            return c
    return None


def exists(arts: Artifacts, name: str) -> Check:
    return (f"exists:{name}", find(arts, name) is not None, "")


def regex(arts: Artifacts, name: str, pat: str, min_count: int = 1, flags: int = re.I | re.S) -> Check:
    c = find(arts, name)
    if c is None:
        return (f"regex:{name}:{pat[:30]}", False, "missing file")
    n = len(re.findall(pat, c, flags))
    return (f"regex:{name}:{pat[:30]}", n >= min_count, f"{n} matches")


def not_regex(arts: Artifacts, name: str, pat: str, flags: int = re.I) -> Check:
    c = find(arts, name)
    if c is None:
        return (f"not_regex:{name}:{pat[:30]}", False, "missing file")
    return (f"not_regex:{name}:{pat[:30]}", re.search(pat, c, flags) is None, "")


def load_json(arts: Artifacts, name: str) -> Any:
    c = find(arts, name)
    if c is None:
        return None
    c = c.strip()
    if c.startswith("```"):
        c = re.sub(r"^```[a-z]*\n|\n```$", "", c, flags=re.S)
    try:
        return json.loads(c)
    except json.JSONDecodeError:
        return None


def json_equals(arts: Artifacts, name: str, expected: Any, key: str | None = None) -> Check:
    got = load_json(arts, name)
    if got is None:
        return (f"json:{name}", False, "missing or invalid JSON")
    if key is not None:
        got = got.get(key) if isinstance(got, dict) else None
    ok = _norm(got) == _norm(expected)
    return (f"json:{name}" + (f".{key}" if key else ""), ok, "" if ok else f"got {json.dumps(got, ensure_ascii=False)[:300]}")


def _norm(v: Any) -> Any:
    if isinstance(v, float):
        return round(v, 2)
    if isinstance(v, dict):
        return {str(k): _norm(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_norm(x) for x in v]
    return v


def load_csv(arts: Artifacts, name: str) -> list[dict[str, str]] | None:
    c = find(arts, name)
    if c is None:
        return None
    try:
        return list(csv.DictReader(io.StringIO(c.strip())))
    except csv.Error:
        return None


def unittest_against(arts: Artifacts, module_file: str, test_source: str, extra_files: dict[str, str] | None = None) -> Check:
    """Run hidden unit tests (test_source) against the published module in a temp dir, 60 s limit."""
    src = find(arts, module_file)
    if src is None:
        return (f"hidden_tests:{module_file}", False, "missing module")
    with tempfile.TemporaryDirectory() as d:
        Path(d, module_file).write_text(src, encoding="utf-8")
        Path(d, "test_hidden.py").write_text(test_source, encoding="utf-8")
        for k, v in (extra_files or {}).items():
            Path(d, k).write_text(v, encoding="utf-8")
        try:
            r = subprocess.run([sys.executable, "-m", "unittest", "-q", "test_hidden"], cwd=d, capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            return (f"hidden_tests:{module_file}", False, "timeout")
        tail = (r.stderr or r.stdout).strip().splitlines()[-1:] or [""]
        return (f"hidden_tests:{module_file}", r.returncode == 0, tail[0][:200])


def html_checks(arts: Artifacts, name: str) -> list[Check]:
    c = find(arts, name)
    if c is None:
        return [(f"html:{name}", False, "missing")]
    return [(f"html:{name}:title", bool(re.search(r"<title>[^<]+</title>", c, re.I)), ""),
            (f"html:{name}:viewport", "viewport" in c, ""),
            (f"html:{name}:no_external_url", re.search(r"https?://", c) is None, "")]


def internal_links_ok(arts: Artifacts, pages: list[str]) -> Check:
    import posixpath
    names = set()
    for p in arts:
        names.add(p)
    broken = []
    for page in pages:
        c = find(arts, page)
        if c is None:
            broken.append(f"{page}: missing")
            continue
        base = posixpath.dirname(page)
        for href in re.findall(r'(?:href|src)="([^"#]+)"', c):
            if href.startswith(("http://", "https://", "mailto:", "data:")):
                continue
            target = posixpath.normpath(posixpath.join(base, href))
            if find(arts, target) is None and find(arts, target.lstrip("./")) is None:
                broken.append(f"{page} -> {href}")
    return ("internal_links", not broken, "; ".join(broken)[:300])


def to_csv(rows: list[dict[str, Any]], cols: list[str]) -> str:
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=cols)
    w.writeheader()
    for r in rows:
        w.writerow({c: r[c] for c in cols})
    return out.getvalue()


# ----------------------------------------------------------------------------- data (deterministic literals)
SALES = [{"region": r, "month": m, "amount": a} for r, m, a in [
    ("east", "2026-01", 1200), ("east", "2026-02", 1350), ("east", "2026-03", 990), ("west", "2026-01", 800), ("west", "2026-02", 1120),
    ("west", "2026-03", 1430), ("north", "2026-01", 450), ("north", "2026-02", 610), ("north", "2026-03", 720), ("south", "2026-01", 1500),
    ("south", "2026-02", 1480), ("south", "2026-03", 1610)]]
SALES_TOTALS = {r: sum(x["amount"] for x in SALES if x["region"] == r) for r in ("east", "west", "north", "south")}

CONTACTS = [{"name": n, "email": e, "company": c} for n, e, c in [
    ("Aoki Rin", "rin@example.com", "Aoki LLC"), ("Baba Ken", "ken@example.org", "Baba Inc"), ("Aoki Rin", "RIN@example.com", "Aoki LLC"),
    ("Chiba Yui", "yui@example.net", "Chiba Co"), ("Doi Sho", "sho@example.com", "Doi KK"), ("Baba Ken", "ken@example.org", "Baba Inc"),
    ("Endo Mai", "mai@example.com", "Endo Ltd"), ("Chiba Yui", "Yui@Example.net", "Chiba Co"), ("Fuji Taro", "taro@example.com", "Fuji Corp"),
    ("Goto Ai", "ai@example.jp", "Goto Inc")]]
CONTACTS_UNIQUE = 7

ATTENDANCE = [{"person": p, "date": d, "status": s} for p, d, s in [
    ("sato", "2026-09-01", "present"), ("sato", "2026-09-02", "present"), ("sato", "2026-09-03", "absent"), ("sato", "2026-09-04", "present"),
    ("suzuki", "2026-09-01", "absent"), ("suzuki", "2026-09-02", "present"), ("suzuki", "2026-09-03", "present"), ("suzuki", "2026-09-04", "absent"),
    ("takahashi", "2026-09-01", "present"), ("takahashi", "2026-09-02", "present"), ("takahashi", "2026-09-03", "present"), ("takahashi", "2026-09-04", "present"),
    ("tanaka", "2026-09-01", "absent"), ("tanaka", "2026-09-02", "absent"), ("tanaka", "2026-09-03", "present"), ("tanaka", "2026-09-04", "absent")]]
ATTENDANCE_COUNTS = dict(Counter(r["person"] for r in ATTENDANCE if r["status"] == "present"))
ATTENDANCE_COUNTS.setdefault("tanaka", 1)

ORDERS = [{"order_id": o, "customer_id": c, "total": t} for o, c, t in [
    ("O-1", "C-2", 120), ("O-2", "C-1", 80), ("O-3", "C-3", 300), ("O-4", "C-2", 45), ("O-5", "C-1", 210), ("O-6", "C-4", 99)]]
CUSTOMERS = [{"customer_id": c, "customer_name": n} for c, n in [("C-1", "Hoshino"), ("C-2", "Ikeda"), ("C-3", "Jinno"), ("C-4", "Kudo")]]
CUSTOMER_NAME = {c["customer_id"]: c["customer_name"] for c in CUSTOMERS}

PRODUCTS = [{"sku": s, "name": n, "price": p, "stock": q} for s, n, p, q in [
    ("P1", "Desk", 32000, 3), ("P2", "Chair", 18000, 0), ("P3", "Lamp", 6500, 12), ("P4", "Monitor", 41000, 2), ("P5", "Cable", 900, 100),
    ("P6", "Stand", 12000, 0), ("P7", "Keyboard", 15000, 5)]]
TOP3_IN_STOCK = [p["sku"] for p in sorted([p for p in PRODUCTS if p["stock"] > 0], key=lambda p: -p["price"])[:3]]

DAILY = [{"date": f"2026-08-{d:02d}", "visits": v} for d, v in [
    (1, 320), (2, 410), (3, 295), (4, 512), (5, 488), (6, 377), (7, 640), (8, 601), (9, 355), (10, 402)]]
DAILY_MAX_DATE = max(DAILY, key=lambda r: r["visits"])["date"]
DAILY_AVG = round(sum(r["visits"] for r in DAILY) / len(DAILY), 1)

SURVEY = ["A", "B", "A", "C", "B", "A", "D", "A", "C", "B", "B", "A", "C", "A", "B", "D", "A", "B", "C", "A"]
SURVEY_COUNTS = dict(Counter(SURVEY))

LOGS = [(s, l) for s, l in [
    ("api", "INFO"), ("api", "ERROR"), ("api", "INFO"), ("api", "INFO"), ("api", "ERROR"), ("web", "INFO"), ("web", "INFO"), ("web", "INFO"),
    ("web", "ERROR"), ("web", "INFO"), ("worker", "ERROR"), ("worker", "ERROR"), ("worker", "INFO"), ("worker", "INFO"), ("worker", "INFO"),
    ("worker", "INFO"), ("worker", "INFO"), ("worker", "INFO"), ("worker", "ERROR"), ("worker", "INFO")]]
LOG_LINES = "\n".join(f"2026-09-01T10:{i:02d}:00Z {s} {l} request handled" for i, (s, l) in enumerate(LOGS))
LOG_RATES = {}
for s in ("api", "web", "worker"):
    tot = sum(1 for x, _ in LOGS if x == s)
    err = sum(1 for x, l in LOGS if x == s and l == "ERROR")
    LOG_RATES[s] = round(err / tot, 2)

AB = {"A": {"users": 2500, "conversions": 115}, "B": {"users": 2480, "conversions": 141}}
AB_RATES = {k: round(v["conversions"] / v["users"] * 100, 2) for k, v in AB.items()}
AB_WINNER = max(AB_RATES, key=lambda k: AB_RATES[k])

SIGNUPS = {"u1": "2026-07", "u2": "2026-07", "u3": "2026-07", "u4": "2026-08", "u5": "2026-08", "u6": "2026-08", "u7": "2026-08", "u8": "2026-09"}
ACTIVITY = [("u1", "2026-08"), ("u1", "2026-09"), ("u2", "2026-08"), ("u3", "2026-09"), ("u4", "2026-09"), ("u6", "2026-09"), ("u7", "2026-09"), ("u8", "2026-09")]
COHORT_M1 = {}
for month in ("2026-07", "2026-08"):
    users = [u for u, m in SIGNUPS.items() if m == month]
    nxt = {"2026-07": "2026-08", "2026-08": "2026-09"}[month]
    active = [u for u in users if (u, nxt) in ACTIVITY]
    COHORT_M1[month] = {"signups": len(users), "active_next_month": len(active), "retention_pct": round(len(active) / len(users) * 100, 1)}

PEOPLE_JSON = [{"id": 1, "name": "Mori", "dept": "sales", "age": 34, "active": True}, {"id": 2, "name": "Nakamura", "dept": "eng", "age": 29, "active": False},
               {"id": 3, "name": "Ono", "dept": "eng", "age": 41, "active": True}, {"id": 4, "name": "Saito", "dept": "hr", "age": 38, "active": True}]
PEOPLE_CSV_EXPECTED = to_csv([{"id": p["id"], "name": p["name"], "dept": p["dept"]} for p in PEOPLE_JSON], ["id", "name", "dept"])

INVENTORY_CSV = "sku,qty,unit_price,discontinued\nA-1,10,2.5,false\nA-2,0,19.99,true\nA-3,7,120,false\n"
INVENTORY_JSON_EXPECTED = [{"sku": "A-1", "qty": 10, "unit_price": 2.5, "discontinued": False}, {"sku": "A-2", "qty": 0, "unit_price": 19.99, "discontinued": True},
                           {"sku": "A-3", "qty": 7, "unit_price": 120, "discontinued": False}]

MD_TABLE = "| city | population | country |\n| --- | --- | --- |\n| Tokyo | 13960000 | Japan |\n| Osaka | 2750000 | Japan |\n| Seoul | 9700000 | Korea |\n"
MD_TABLE_JSON = [{"city": "Tokyo", "population": 13960000, "country": "Japan"}, {"city": "Osaka", "population": 2750000, "country": "Japan"},
                 {"city": "Seoul", "population": 9700000, "country": "Korea"}]

DATES_RAW = ["2026/03/05", "5 March 2026", "March 5, 2026", "05-03-2026", "2026-03-05", "2026年3月5日", "20260305"]
DATES_ISO = ["2026-03-05"] * 7
DATES_RAW2 = ["2025/12/31", "31 Dec 2025", "2025年12月31日"]
DATES_ISO2 = ["2025-12-31"] * 3

NESTED = {"user": {"id": 7, "profile": {"name": "Uno", "langs": ["ja", "en"]}, "address": {"city": "Kobe", "zip": "650-0001"}}, "plan": "pro"}
FLAT_EXPECTED = {"user.id": 7, "user.profile.name": "Uno", "user.profile.langs": ["ja", "en"], "user.address.city": "Kobe", "user.address.zip": "650-0001", "plan": "pro"}

MEETING_NOTES = """9/10 定例 参加: 山田(PM), 佐々木(開発), 井上(営業)
- 井上: 顧客A社から見積の再提示依頼。締切は9/18。
- 佐々木: 認証まわりの不具合#231は修正済み、9/12にリリース予定。
- 山田: 次回のデモは9/20 15:00、場所は本社3F。
- 決定: 価格改定は今期見送り。
- 決定: A社向け見積は井上が9/16までに山田へドラフト送付。
- 佐々木の懸念: ログ保持期間が未決。次回までに山田が法務に確認。
"""
COMMITS = """a1 fix: login redirect loop on expired session
b2 feat: CSV export for reports
c3 fix: timezone off-by-one in daily digest
d4 feat: dark mode toggle in settings
e5 chore: bump dependencies
f6 fix: memory leak in websocket reconnect
"""
PRODUCT_NOTES = """製品: Nocto（社内向けナレッジ検索）
- 社内ドキュメントを全文検索。対応形式: PDF, Word, Markdown。
- 検索結果に出典ページ番号を表示。
- アクセス権はSSOのグループに追従。
- 価格: 未定（社内利用のため）。
- 対応言語: 日本語と英語。
- 導入: Dockerイメージで社内サーバに配置。
"""
TICKETS = [("T-101", "先週注文した商品がまだ届きません。注文番号は 8891 です。", "配送"),
           ("T-102", "請求書の宛名が間違っています。正しい社名は『株式会社ミナト』です。", "請求"),
           ("T-103", "パスワードをリセットしてもログインできません。", "ログイン"),
           ("T-104", "解約したいのですが手順を教えてください。", "解約"),
           ("T-105", "アプリがiOS 18で起動直後に落ちます。", "不具合"),
           ("T-106", "領収書を再発行してもらえますか。", "請求"),
           ("T-107", "配送先住所を変更したい。", "配送"),
           ("T-108", "二段階認証のコードが届きません。", "ログイン"),
           ("T-109", "プランを月額から年額に変更したい。", "契約変更"),
           ("T-110", "ダークモードにするとボタンが見えません。", "不具合")]
TICKET_CATEGORIES = ["配送", "請求", "ログイン", "解約", "不具合", "契約変更"]
REFUND_POLICY = """返金ポリシー（社内文書 v3）
- 未開封の商品は到着から14日以内であれば全額返金。
- 開封済みの商品は返金不可。交換のみ受け付ける。
- 返金は元の支払い方法へ、受付から5営業日以内に処理。
- セール品は返金対象外。
"""
THREAD = """[9/1 10:02] 顧客(高橋): 先月分の請求が二重になっています。
[9/1 11:30] サポート(森): 確認します。請求ID 5521 と 5522 で相違ないですか。
[9/1 12:10] 顧客(高橋): はい、その2件です。
[9/2 09:15] サポート(森): 5522 は重複と確認。経理へ取消依頼済み。
[9/4 16:40] 顧客(高橋): まだ取消の連絡が来ていません。
[9/5 10:00] サポート(森): 経理から本日中に取消完了予定との回答。完了後にメールでお知らせします。
"""
BRIEF = """製品: Agent Team（オープンソース、MIT）
- 一度の依頼でAIチーム（Master/Researcher/Builder/Reviewer）が作業し、成果物と検証の経緯を残す。
- ローカルの Claude Code から API キー無しで使える。
- 対象: ソフトウェア開発者、個人開発者。
- 価格: 無料（OSS）。
- リンク: https://github.com/FORIFOR/Multibot
"""
PRESS_FACTS = """会社名: 株式会社ホシノ
発表日: 2026年10月1日
内容: 社内ナレッジ検索「Nocto」を自社導入。対象部門は営業とサポートの2部門、利用者は約120名。
効果の数値はまだ計測していない（発表時点で未計測）。
問い合わせ先: pr@hoshino.example
"""
PLAN_CONSTRAINTS = """プロジェクト: 社内FAQボット導入
- 開始: 2026-10-01、本番リリース期限: 2026-12-15
- メンバー: pm(田中), dev(鈴木), qa(高橋)
- 必須マイルストーン: 要件確定、プロトタイプ、社内テスト、本番リリース
"""
SCHEDULE_CONSTRAINTS = """3人（aki, ben, chie）の週次シフト（月〜金、各日 9-13 と 13-17 の2枠）。
- 各枠に必ず1人だけ入る。
- aki は水曜は終日不可。
- ben は 13-17 の枠に入れない。
- chie は週に最大5枠まで。
- 誰も同じ日に2枠連続で入らない。
"""


# ----------------------------------------------------------------------------- task table
TASKS: list[dict[str, Any]] = []


def task(id: str, category: str, goal: str, grade: Callable[[Artifacts], list[Check]], *, text: str = "", urls: list[str] | None = None,
         files: dict[str, str] | None = None, expects: list[str] | None = None) -> None:
    TASKS.append({"id": id, "category": category, "goal": goal, "text": text, "urls": urls or [],
                  "files": [{"name": k, "content": v} for k, v in (files or {}).items()], "grade": grade, "expects": expects or []})


# ---- research (needs the network; graded on structure, citations and facts that are stable on those pages)
task("research-3repos", "research",
     "次の3つの公開ページを実際に取得して読み、それぞれの「主張・対象読者・ライセンス（記載があれば）」を出典URL付きで比較した調査メモ `research.md` を日本語で作ってください。取得できなかったページは『取得不可』と明記し、本文を推測で埋めないでください。",
     lambda a: [exists(a, "research.md"), regex(a, "research.md", r"github\.com/langchain-ai/deepagents"), regex(a, "research.md", r"github\.com/bytedance/deer-flow"),
                regex(a, "research.md", r"agentskills\.io/specification"), regex(a, "research.md", r"ライセンス"), regex(a, "research.md", r"MIT")],
     urls=["https://github.com/langchain-ai/deepagents", "https://github.com/bytedance/deer-flow", "https://agentskills.io/specification"])
task("research-py313", "research",
     "次のページを実際に取得し、Python 3.13 の主要な新機能を出典URL付きで5点以上、日本語で `whatsnew.md` にまとめてください。ページに無いことは書かないでください。",
     lambda a: [exists(a, "whatsnew.md"), regex(a, "whatsnew.md", r"docs\.python\.org/3/whatsnew/3\.13"), regex(a, "whatsnew.md", r"free.threaded|フリースレッド|GIL"),
                regex(a, "whatsnew.md", r"JIT"), regex(a, "whatsnew.md", r"^\s*(?:[-*]|\d+\.)\s", 5, re.M)],
     urls=["https://docs.python.org/3/whatsnew/3.13.html"])
task("research-rfc8259", "research",
     "RFC 8259（JSON）を実際に取得し、JSON の値の種類（object/array/number/string/true/false/null）と、文字列で必ずエスケープが必要な文字を、出典URL付きで `json-spec.md` に日本語でまとめてください。",
     lambda a: [exists(a, "json-spec.md"), regex(a, "json-spec.md", r"rfc-editor\.org/rfc/rfc8259|rfc8259"), regex(a, "json-spec.md", r"\bnull\b"),
                regex(a, "json-spec.md", r"\bfalse\b"), regex(a, "json-spec.md", r"U\+0000|0x1F|制御文字|control"), regex(a, "json-spec.md", r"引用符|quotation|\"")],
     urls=["https://www.rfc-editor.org/rfc/rfc8259"])
task("research-uv", "research",
     "次のページを取得し、uv の主なコマンド（プロジェクト管理・ツール実行・pip 互換の3系統）を出典URL付きで `uv-guide.md` に日本語でまとめてください。ページに無いコマンドは書かないでください。",
     lambda a: [exists(a, "uv-guide.md"), regex(a, "uv-guide.md", r"docs\.astral\.sh/uv"), regex(a, "uv-guide.md", r"\buvx\b|uv tool run"),
                regex(a, "uv-guide.md", r"uv pip"), regex(a, "uv-guide.md", r"uv (add|sync|run|init)")],
     urls=["https://docs.astral.sh/uv/"])
task("research-changelog", "research",
     "Keep a Changelog 1.1.0 のページを取得し、変更の種類（Added など）を全て列挙し、各種類の意味を一行ずつ、出典URL付きで `changelog-types.md` に日本語でまとめてください。",
     lambda a: [exists(a, "changelog-types.md"), regex(a, "changelog-types.md", r"keepachangelog\.com")] +
               [regex(a, "changelog-types.md", rf"\b{w}\b") for w in ("Added", "Changed", "Deprecated", "Removed", "Fixed", "Security")],
     urls=["https://keepachangelog.com/en/1.1.0/"])

# ---- document
task("doc-minutes", "document",
     "添付の会議メモから議事録 `minutes.md` を日本語で作ってください。見出しは「決定事項」「TODO（担当・期限付き）」「次回」の3つ。メモに無い情報は書かないでください。",
     lambda a: [exists(a, "minutes.md"), regex(a, "minutes.md", r"決定事項"), regex(a, "minutes.md", r"TODO"), regex(a, "minutes.md", r"次回"),
                regex(a, "minutes.md", r"9/16|9月16日|2026-09-16"), regex(a, "minutes.md", r"9/20|9月20日|2026-09-20"), regex(a, "minutes.md", r"法務"),
                not_regex(a, "minutes.md", r"価格改定を実施|価格を改定する")],
     files={"notes.txt": MEETING_NOTES})
task("doc-release-notes", "document",
     "添付のコミット一覧からリリースノート `release-notes.md` を日本語で作ってください。見出しは「新機能」「修正」の2つ。chore は載せないでください。各項目は1行で、対応するコミットIDを末尾に括弧で付けてください。",
     lambda a: [exists(a, "release-notes.md"), regex(a, "release-notes.md", r"新機能"), regex(a, "release-notes.md", r"修正"),
                regex(a, "release-notes.md", r"\(a1\)"), regex(a, "release-notes.md", r"\(b2\)"), regex(a, "release-notes.md", r"\(c3\)"),
                regex(a, "release-notes.md", r"\(d4\)"), regex(a, "release-notes.md", r"\(f6\)"), not_regex(a, "release-notes.md", r"\(e5\)|依存関係.*更新|bump")],
     files={"commits.txt": COMMITS})
task("doc-faq", "document",
     "添付の製品メモから FAQ `faq.md` を日本語で作ってください。「Q: 」で始まる質問と「A: 」で始まる回答の組を5組以上。メモに無い機能や価格を書かないでください。",
     lambda a: [exists(a, "faq.md"), regex(a, "faq.md", r"^\s*(?:#+\s*)?(?:\*\*)?Q[:：]", 5, re.M), regex(a, "faq.md", r"^\s*(?:\*\*)?A[:：]", 5, re.M),
                regex(a, "faq.md", r"PDF"), regex(a, "faq.md", r"SSO"), not_regex(a, "faq.md", r"\d+\s*円|\$\d+|USD")],
     files={"product.txt": PRODUCT_NOTES})
task("doc-email", "document",
     "添付のメモをもとに、A社へ見積を再提示する日本語のビジネスメール文面 `email.md` を作ってください。1行目は「件名: 」で始めること。メモに無い金額や納期を書かないでください。",
     lambda a: [exists(a, "email.md"), regex(a, "email.md", r"\A\s*件名[:：]", 1, re.M), regex(a, "email.md", r"見積"), regex(a, "email.md", r"A社|A 社"),
                not_regex(a, "email.md", r"\d[\d,]*\s*円|¥\s*\d")],
     files={"notes.txt": MEETING_NOTES})
task("doc-jd", "document",
     "添付の製品メモを開発するバックエンドエンジニアの求人票 `jd.md` を日本語で作ってください。見出しは「業務内容」「必須要件」「歓迎要件」。給与や勤務地はメモに無いので書かないでください。",
     lambda a: [exists(a, "jd.md"), regex(a, "jd.md", r"業務内容"), regex(a, "jd.md", r"必須要件"), regex(a, "jd.md", r"歓迎要件"),
                regex(a, "jd.md", r"Docker"), not_regex(a, "jd.md", r"万円|年収|勤務地[:：]\s*\S")],
     files={"product.txt": PRODUCT_NOTES})

# ---- code (hidden unit tests)
T_WC = '''import unittest, subprocess, sys, tempfile, os
class T(unittest.TestCase):
    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.txt"); open(p, "w").write("the cat the dog\\nthe end\\n")
            r = subprocess.run([sys.executable, "wc_plus.py", p], capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = r.stdout
            self.assertIn("2", out); self.assertIn("6", out); self.assertIn("the", out)
'''
task("code-wc-plus", "code",
     "Python で CLI ツール `wc_plus.py` を作ってください: 引数のテキストファイル群について行数・単語数・文字数と、最頻出の単語トップ5を表示する。標準ライブラリのみ。`test_wc_plus.py`（unittest、最低5ケース）と `README.md`（使い方）も出力してください。",
     lambda a: [exists(a, "wc_plus.py"), exists(a, "test_wc_plus.py"), exists(a, "README.md"), unittest_against(a, "wc_plus.py", T_WC)])
T_SLUG = '''import unittest
from slugify import slugify
class T(unittest.TestCase):
    def test_basic(self): self.assertEqual(slugify("Hello World"), "hello-world")
    def test_collapse(self): self.assertEqual(slugify("  A  --  B!! "), "a-b")
    def test_unicode_kept_out(self): self.assertEqual(slugify("Café au lait"), "caf-au-lait")
    def test_numbers(self): self.assertEqual(slugify("Top 10 Tips 2026"), "top-10-tips-2026")
    def test_empty(self): self.assertEqual(slugify("!!!"), "")
'''
task("code-slugify", "code",
     "Python モジュール `slugify.py` に関数 `slugify(s: str) -> str` を実装してください。仕様: 小文字化、ASCII の英数字以外は全てハイフンに置換、連続するハイフンは1つにまとめ、先頭と末尾のハイフンは除去、非ASCII文字は削除扱い（ハイフンに置換）。標準ライブラリのみ。`test_slugify.py`（unittest 5 ケース以上）も出力してください。",
     lambda a: [exists(a, "slugify.py"), exists(a, "test_slugify.py"), unittest_against(a, "slugify.py", T_SLUG)])
T_ROMAN = '''import unittest
from roman import to_roman, from_roman
class T(unittest.TestCase):
    def test_to(self):
        for n, r in [(1, "I"), (4, "IV"), (9, "IX"), (14, "XIV"), (40, "XL"), (90, "XC"), (400, "CD"), (1994, "MCMXCIV"), (3999, "MMMCMXCIX")]:
            self.assertEqual(to_roman(n), r)
    def test_from(self):
        for n in [1, 4, 9, 58, 1994, 2026, 3999]: self.assertEqual(from_roman(to_roman(n)), n)
    def test_range(self):
        with self.assertRaises(ValueError): to_roman(0)
        with self.assertRaises(ValueError): to_roman(4000)
'''
task("code-roman", "code",
     "Python モジュール `roman.py` に `to_roman(n: int) -> str` と `from_roman(s: str) -> int` を実装してください（1〜3999、範囲外は ValueError）。標準ライブラリのみ。`test_roman.py`（unittest 5 ケース以上）も出力してください。",
     lambda a: [exists(a, "roman.py"), exists(a, "test_roman.py"), unittest_against(a, "roman.py", T_ROMAN)])
T_CSVSTATS = '''import unittest, subprocess, sys, tempfile, os, json
class T(unittest.TestCase):
    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.csv"); open(p, "w").write("name,score,age\\na,10,30\\nb,20,40\\nc,30,50\\n")
            r = subprocess.run([sys.executable, "csv_stats.py", p], capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = json.loads(r.stdout)
            self.assertAlmostEqual(out["score"]["mean"], 20.0); self.assertEqual(out["score"]["min"], 10); self.assertEqual(out["score"]["max"], 30)
            self.assertAlmostEqual(out["age"]["mean"], 40.0); self.assertNotIn("name", out)
'''
task("code-csv-stats", "code",
     "Python で CLI `csv_stats.py` を作ってください: 引数の CSV ファイルを読み、数値列ごとに mean/min/max を計算し、`{\"列名\": {\"mean\": .., \"min\": .., \"max\": ..}}` の JSON を標準出力に出す（数値でない列は含めない）。標準ライブラリのみ。`test_csv_stats.py`（unittest 5 ケース以上）も出力してください。",
     lambda a: [exists(a, "csv_stats.py"), exists(a, "test_csv_stats.py"), unittest_against(a, "csv_stats.py", T_CSVSTATS)])
T_LRU = '''import unittest
from lru_cache import LRUCache
class T(unittest.TestCase):
    def test_evict(self):
        c = LRUCache(2); c.put("a", 1); c.put("b", 2); self.assertEqual(c.get("a"), 1); c.put("c", 3)
        self.assertIsNone(c.get("b")); self.assertEqual(c.get("a"), 1); self.assertEqual(c.get("c"), 3)
    def test_update(self):
        c = LRUCache(1); c.put("a", 1); c.put("a", 2); self.assertEqual(c.get("a"), 2)
    def test_missing(self): self.assertIsNone(LRUCache(3).get("zz"))
    def test_len(self):
        c = LRUCache(2); c.put(1, 1); c.put(2, 2); c.put(3, 3); self.assertEqual(len(c), 2)
'''
task("code-lru", "code",
     "Python モジュール `lru_cache.py` にクラス `LRUCache(capacity)` を実装してください: `get(key)`（無ければ None）、`put(key, value)`、`__len__`。容量超過時は最も長く使われていないキーを追い出す。get/put は O(1)。標準ライブラリのみ。`test_lru_cache.py`（unittest 5 ケース以上）も出力してください。",
     lambda a: [exists(a, "lru_cache.py"), exists(a, "test_lru_cache.py"), unittest_against(a, "lru_cache.py", T_LRU)])

# ---- spreadsheet (CSV in, exact CSV/JSON out)
def _grade_sales(a):
    rows = load_csv(a, "summary.csv")
    if rows is None:
        return [("csv:summary.csv", False, "missing/invalid")]
    got = {}
    for r in rows:
        k = (r.get("region") or "").strip()
        try:
            got[k] = int(float((r.get("total") or "").strip()))
        except ValueError:
            pass
    return [("csv:summary.csv:totals", got == SALES_TOTALS, f"got {got}")]
task("sheet-sales-totals", "spreadsheet",
     "添付の sales.csv（region,month,amount）から、region ごとの amount 合計を `summary.csv`（列: region,total）として作ってください。",
     _grade_sales, files={"sales.csv": to_csv(SALES, ["region", "month", "amount"])})
def _grade_dedupe(a):
    rows = load_csv(a, "contacts_unique.csv")
    if rows is None:
        return [("csv:contacts_unique.csv", False, "missing/invalid")]
    emails = [r.get("email", "").strip().lower() for r in rows]
    return [("csv:contacts_unique.csv:rows", len(rows) == CONTACTS_UNIQUE and len(set(emails)) == CONTACTS_UNIQUE, f"{len(rows)} rows"),
            ("csv:contacts_unique.csv:first_kept", any(r.get("email") == "rin@example.com" for r in rows), "")]
task("sheet-dedupe", "spreadsheet",
     "添付の contacts.csv を email の大文字小文字を無視して重複排除し（最初の行を残す）、`contacts_unique.csv`（同じ列）として作ってください。",
     _grade_dedupe, files={"contacts.csv": to_csv(CONTACTS, ["name", "email", "company"])})
task("sheet-attendance", "spreadsheet",
     "添付の attendance.csv（person,date,status）から、person ごとの出席（status=present）日数を `attendance.json`（{\"person\": 日数}）として作ってください。",
     lambda a: [json_equals(a, "attendance.json", ATTENDANCE_COUNTS)], files={"attendance.csv": to_csv(ATTENDANCE, ["person", "date", "status"])})
def _grade_join(a):
    rows = load_csv(a, "orders_enriched.csv")
    if rows is None:
        return [("csv:orders_enriched.csv", False, "missing/invalid")]
    ok = len(rows) == len(ORDERS) and all(r.get("customer_name") == CUSTOMER_NAME[r.get("customer_id", "")] for r in rows if r.get("customer_id") in CUSTOMER_NAME)
    return [("csv:orders_enriched.csv:join", ok and all("customer_name" in r for r in rows), f"{len(rows)} rows")]
task("sheet-join", "spreadsheet",
     "添付の orders.csv（order_id,customer_id,total）と customers.csv（customer_id,customer_name）を結合し、`orders_enriched.csv`（列: order_id,customer_id,customer_name,total）を作ってください。",
     _grade_join, files={"orders.csv": to_csv(ORDERS, ["order_id", "customer_id", "total"]), "customers.csv": to_csv(CUSTOMERS, ["customer_id", "customer_name"])})
task("sheet-top3", "spreadsheet",
     "添付の products.csv（sku,name,price,stock）から、在庫がある（stock>0）商品のうち価格の高い順に3件の sku を `top3.json`（文字列の配列）として作ってください。",
     lambda a: [json_equals(a, "top3.json", TOP3_IN_STOCK)], files={"products.csv": to_csv(PRODUCTS, ["sku", "name", "price", "stock"])})

# ---- web
task("web-docs-site", "web",
     "小さな静的ドキュメントサイトを作ってください: `index.html`、`docs/getting-started.html`、`docs/faq.html`、`styles.css` の4ファイル。内容は添付の製品説明に基づく日本語。相互リンクが切れていないこと、各ページに title と viewport があること、外部 URL を書かないこと。",
     lambda a: html_checks(a, "index.html") + html_checks(a, "docs/getting-started.html") + html_checks(a, "docs/faq.html") +
               [exists(a, "styles.css"), internal_links_ok(a, ["index.html", "docs/getting-started.html", "docs/faq.html"])],
     text=PRODUCT_NOTES)
task("web-contact-form", "web",
     "問い合わせフォーム付きの単一ファイル LP `index.html` を日本語で作ってください（インライン CSS、外部 URL なし）。フォームには氏名・メール・本文の3項目と送信ボタン、各入力に label を付けること。",
     lambda a: html_checks(a, "index.html") + [regex(a, "index.html", r"<form"), regex(a, "index.html", r"<label", 3), regex(a, "index.html", r'type="email"'),
                                              regex(a, "index.html", r"<textarea"), regex(a, "index.html", r"<button|type=\"submit\"")])
task("web-pricing", "web",
     "添付の料金情報だけを使って料金表ページ `pricing.html` を日本語で作ってください（単一ファイル、外部 URL なし）。3プランを表または3カラムで並べ、記載の無い価格や機能を追加しないでください。",
     lambda a: html_checks(a, "pricing.html") + [regex(a, "pricing.html", r"Free"), regex(a, "pricing.html", r"Team"), regex(a, "pricing.html", r"Enterprise"),
                                                regex(a, "pricing.html", r"1,?980"), regex(a, "pricing.html", r"9,?800"), not_regex(a, "pricing.html", r"\b(?:2,?980|4,?980|19,?800)\b")],
     text="プラン: Free（0円/月、1ユーザー、検索のみ）、Team（1,980円/月/ユーザー、SSO、出典表示）、Enterprise（9,800円/月/ユーザー、監査ログ、専用サポート）")
def _grade_a11y(a):
    c = find(a, "about.html") or ""
    imgs = re.findall(r"<img\b[^>]*>", c, re.I)
    return html_checks(a, "about.html") + [("a11y:lang_ja", bool(re.search(r"<html[^>]*lang=\"ja\"", c, re.I)), ""),
                                         ("a11y:one_h1", len(re.findall(r"<h1\b", c, re.I)) == 1, ""),
                                         ("a11y:img_alt", len(imgs) >= 1 and all(re.search(r"\balt=", i, re.I) for i in imgs), f"{len(imgs)} imgs")]
task("web-a11y", "web",
     "会社紹介ページ `about.html` を日本語で作ってください（単一ファイル、外部 URL なし）。要件: `<html lang=\"ja\">`、h1 はちょうど1つ、画像（data: URI かプレースホルダ src）を1つ以上置き、全ての img に alt を付けること。内容は添付の製品説明の会社を想定。",
     _grade_a11y, text=PRESS_FACTS)
task("web-404", "web",
     "`index.html` と `404.html` の2ファイルを日本語で作ってください（共通の `styles.css` も作る、外部 URL なし）。404 ページからトップへのリンク、トップから 404 ページへのリンク（「見つからない時」の説明用）を置き、リンク切れが無いこと。",
     lambda a: html_checks(a, "index.html") + html_checks(a, "404.html") + [exists(a, "styles.css"), internal_links_ok(a, ["index.html", "404.html"]),
                                                                          regex(a, "404.html", r'href="(?:\./)?index\.html"'), regex(a, "index.html", r'href="(?:\./)?404\.html"')])

# ---- customer support
task("cs-replies", "customer_support",
     "添付の3件の問い合わせ（T-101〜T-103）への返信案を `replies.md` に日本語で作ってください。各返信は「## T-xxx」の見出しで始め、本文中で注文番号や社名など問い合わせに含まれる固有情報をそのまま使うこと。",
     lambda a: [exists(a, "replies.md"), regex(a, "replies.md", r"^##\s*T-101", 1, re.M), regex(a, "replies.md", r"^##\s*T-102", 1, re.M), regex(a, "replies.md", r"^##\s*T-103", 1, re.M),
                regex(a, "replies.md", r"8891"), regex(a, "replies.md", r"ミナト")],
     files={"tickets.txt": "\n".join(f"{i}: {t}" for i, t, _ in TICKETS[:3])})
def _grade_classify(a):
    got = load_json(a, "classification.json")
    if not isinstance(got, list):
        return [("json:classification.json", False, "missing/invalid")]
    m = {x.get("id"): x.get("category") for x in got if isinstance(x, dict)}
    correct = sum(1 for i, _, c in TICKETS if m.get(i) == c)
    return [("classify:all_ids", set(m) == {i for i, _, _ in TICKETS}, f"{len(m)} ids"), ("classify:allowed", all(v in TICKET_CATEGORIES for v in m.values()), ""),
            ("classify:accuracy>=9/10", correct >= 9, f"{correct}/10")]
task("cs-classify", "customer_support",
     "添付の10件の問い合わせを、カテゴリ一覧 [配送, 請求, ログイン, 解約, 不具合, 契約変更] のいずれか1つに分類し、`classification.json`（[{\"id\": \"T-101\", \"category\": \"...\"}, ...]）として作ってください。一覧に無いカテゴリは使わないでください。",
     _grade_classify, files={"tickets.txt": "\n".join(f"{i}: {t}" for i, t, _ in TICKETS)})
task("cs-policy-answer", "customer_support",
     "添付の返金ポリシーだけを根拠に、顧客からの質問「先週届いた未開封の商品を返品したい。返金はいつ・どこに戻りますか？」への回答 `answer.md` を日本語で作ってください。ポリシーに無いことは書かないでください。",
     lambda a: [exists(a, "answer.md"), regex(a, "answer.md", r"14\s*日"), regex(a, "answer.md", r"5\s*営業日"), regex(a, "answer.md", r"元の支払い方法|同じ支払い方法"),
                not_regex(a, "answer.md", r"30\s*日|7\s*日以内")],
     files={"policy.txt": REFUND_POLICY})
task("cs-escalation", "customer_support",
     "添付のやり取りから、上長向けのエスカレーション要約 `summary.md` を日本語で作ってください。見出しは「経緯（時系列）」「現状」「次のアクション」。請求IDを正確に書き、やり取りに無い事実は書かないでください。",
     lambda a: [exists(a, "summary.md"), regex(a, "summary.md", r"経緯"), regex(a, "summary.md", r"現状"), regex(a, "summary.md", r"次のアクション"),
                regex(a, "summary.md", r"5522"), regex(a, "summary.md", r"5521"), regex(a, "summary.md", r"経理"), not_regex(a, "summary.md", r"返金済み|取消完了しました")],
     files={"thread.txt": THREAD})
task("cs-macros", "customer_support",
     "サポート用の定型文5種（挨拶・遅延のお詫び・返金案内・解約手順・クローズ）を `macros.md` に日本語で作ってください。各定型文は「## 」見出しで始め、顧客名の差し込みは `{{name}}` を使うこと。返金案内は添付の返金ポリシーに従うこと。",
     lambda a: [exists(a, "macros.md"), regex(a, "macros.md", r"^##\s", 5, re.M), regex(a, "macros.md", r"\{\{name\}\}", 3), regex(a, "macros.md", r"14\s*日"),
                not_regex(a, "macros.md", r"30\s*日以内")],
     files={"policy.txt": REFUND_POLICY})

# ---- marketing
task("mkt-lp-posts", "marketing",
     "この製品説明をもとに、日本語の紹介LP（index.html、単一ファイル、外部 URL は GitHub リンクのみ可）とSNS投稿草案（posts.md、3案）を作ってください。不足情報は推定して前提として記録し、公開はせず草案まで。",
     lambda a: [exists(a, "index.html"), regex(a, "index.html", r"<title>"), regex(a, "index.html", r"viewport"), exists(a, "posts.md"),
                regex(a, "posts.md", r"^\s*(?:##|\d+\.|[-*])\s", 3, re.M), not_regex(a, "posts.md", r"\d+\s*円/月|月額\s*\d")],
     text=BRIEF)
def _grade_posts(a):
    got = load_json(a, "posts.json")
    if not isinstance(got, list):
        return [("json:posts.json", False, "missing/invalid")]
    return [("posts:count5", len(got) == 5, f"{len(got)}"), ("posts:len<=140", all(isinstance(p, str) and 1 <= len(p) <= 140 for p in got), str([len(p) for p in got if isinstance(p, str)])),
            ("posts:no_price", not any(re.search(r"\d+\s*円", p) for p in got if isinstance(p, str)), "")]
task("mkt-x-posts", "marketing",
     "添付のブリーフから、X（旧Twitter）向けの日本語投稿を5本、`posts.json`（文字列の配列）として作ってください。各投稿は140文字以内。ブリーフに無い価格や数値は書かないでください。",
     _grade_posts, files={"brief.txt": BRIEF})
task("mkt-newsletter", "marketing",
     "添付のブリーフから、月次ニュースレターの本文 `newsletter.md` を日本語で作ってください。1行目は「件名: 」で始め、本文中に CTA リンクは `{{CTA_URL}}` というプレースホルダで置くこと（実URLは書かない）。ブリーフに無い数値は書かないでください。",
     lambda a: [exists(a, "newsletter.md"), regex(a, "newsletter.md", r"\A\s*件名[:：]", 1, re.M), regex(a, "newsletter.md", r"\{\{CTA_URL\}\}"),
                not_regex(a, "newsletter.md", r"https?://"), not_regex(a, "newsletter.md", r"\d+\s*%|\d+\s*社が導入")],
     files={"brief.txt": BRIEF})
def _grade_ads(a):
    got = load_json(a, "ads.json")
    if not isinstance(got, list):
        return [("json:ads.json", False, "missing/invalid")]
    ok_shape = len(got) == 3 and all(isinstance(x, dict) and "headline" in x and "description" in x for x in got)
    return [("ads:3items", ok_shape, f"{len(got)}"), ("ads:headline<=30", ok_shape and all(len(x["headline"]) <= 30 for x in got), ""),
            ("ads:description<=90", ok_shape and all(len(x["description"]) <= 90 for x in got), "")]
task("mkt-ads", "marketing",
     "添付のブリーフから、検索広告の見出し（30文字以内）と説明文（90文字以内）の組を3つ、`ads.json`（[{\"headline\": \"...\", \"description\": \"...\"}, ...]）として日本語で作ってください。",
     _grade_ads, files={"brief.txt": BRIEF})
task("mkt-press", "marketing",
     "添付の事実だけを使ってプレスリリース `press.md` を日本語で作ってください。会社名・発表日・問い合わせ先を正確に含め、効果の数値や『業界初』『No.1』のような根拠のない表現は書かないでください。",
     lambda a: [exists(a, "press.md"), regex(a, "press.md", r"株式会社ホシノ"), regex(a, "press.md", r"2026年10月1日|2026-10-01"), regex(a, "press.md", r"pr@hoshino\.example"),
                regex(a, "press.md", r"120\s*名|120\s*人"), not_regex(a, "press.md", r"業界初|No\.?\s*1|\d+\s*%\s*(?:削減|向上|短縮)")],
     files={"facts.txt": PRESS_FACTS})

# ---- analysis (exact numbers)
task("ana-daily", "analysis",
     "添付の daily.csv（date,visits）から、visits が最大の日と、期間全体の平均（小数1桁）を `analysis.json`（{\"max_date\": \"YYYY-MM-DD\", \"average\": 数値}）として作ってください。",
     lambda a: [json_equals(a, "analysis.json", DAILY_MAX_DATE, "max_date"), json_equals(a, "analysis.json", DAILY_AVG, "average")],
     files={"daily.csv": to_csv(DAILY, ["date", "visits"])})
task("ana-survey", "analysis",
     "添付の survey.txt（1行1回答、A〜D）を集計し、選択肢ごとの件数を `counts.json`（{\"A\": n, ...}）として作ってください。",
     lambda a: [json_equals(a, "counts.json", SURVEY_COUNTS)], files={"survey.txt": "\n".join(SURVEY)})
task("ana-logs", "analysis",
     "添付の app.log（各行: 時刻 サービス名 レベル メッセージ）から、サービスごとのエラー率（ERROR 行数 ÷ 全行数、小数2桁）を `error_rates.json`（{\"api\": 0.xx, ...}）として作ってください。",
     lambda a: [json_equals(a, "error_rates.json", LOG_RATES)], files={"app.log": LOG_LINES})
task("ana-ab", "analysis",
     "添付の ab.json（各バリアントの users と conversions）から、各バリアントのコンバージョン率（%、小数2桁）と、高い方のバリアント名を `ab_result.json`（{\"rates\": {\"A\": x, \"B\": y}, \"winner\": \"A\"|\"B\"}）として作ってください。",
     lambda a: [json_equals(a, "ab_result.json", AB_RATES, "rates"), json_equals(a, "ab_result.json", AB_WINNER, "winner")],
     files={"ab.json": json.dumps(AB)})
task("ana-cohort", "analysis",
     "添付の signups.json（ユーザー→登録月）と activity.json（[ユーザー, 活動月] の配列）から、2026-07 と 2026-08 の登録コホートについて、翌月に活動したユーザー数と割合（%、小数1桁）を `cohort.json`（{\"2026-07\": {\"signups\": n, \"active_next_month\": m, \"retention_pct\": p}, ...}）として作ってください。",
     lambda a: [json_equals(a, "cohort.json", COHORT_M1)], files={"signups.json": json.dumps(SIGNUPS), "activity.json": json.dumps(ACTIVITY)})

# ---- planning (structural validation)
def _grade_plan(a):
    got = load_json(a, "plan.json")
    if not isinstance(got, dict) or not isinstance(got.get("milestones"), list):
        return [("json:plan.json", False, "missing/invalid")]
    ms = got["milestones"]
    dates_ok = all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(m.get("due", ""))) and "2026-10-01" <= m["due"] <= "2026-12-15" for m in ms)
    owners_ok = all(m.get("owner") in ("田中", "鈴木", "高橋") for m in ms)
    names = " ".join(str(m.get("name", "")) for m in ms)
    return [("plan:>=4", len(ms) >= 4, f"{len(ms)}"), ("plan:dates_in_range", dates_ok, ""), ("plan:owners", owners_ok, ""),
            ("plan:required_names", all(k in names for k in ("要件", "プロトタイプ", "テスト", "リリース")), ""),
            ("plan:last_is_release_on_deadline", bool(ms) and ms[-1].get("due") == "2026-12-15", "")]
task("plan-milestones", "planning",
     "添付の制約からプロジェクト計画 `plan.json`（{\"milestones\": [{\"name\": \"...\", \"due\": \"YYYY-MM-DD\", \"owner\": \"田中|鈴木|高橋\"}, ...]}）を作ってください。必須マイルストーンを全て含め、期日は開始日以降・期限以内、最後のマイルストーンは本番リリース（期限日）にしてください。",
     _grade_plan, files={"constraints.txt": PLAN_CONSTRAINTS})
def _grade_schedule(a):
    got = load_json(a, "schedule.json")
    if not isinstance(got, list):
        return [("json:schedule.json", False, "missing/invalid")]
    days = ["mon", "tue", "wed", "thu", "fri"]
    slots = {(d, s) for d in days for s in ("9-13", "13-17")}
    seen = {}
    for x in got:
        if not isinstance(x, dict):
            continue
        seen[(str(x.get("day", "")).lower()[:3], str(x.get("slot", "")))] = str(x.get("person", "")).lower()
    per_person = Counter(seen.values())
    checks = [("sched:all_slots_once", set(seen) == slots and len(got) == 10, f"{len(seen)} slots"),
              ("sched:aki_not_wed", not any(d == "wed" and p == "aki" for (d, _), p in seen.items()), ""),
              ("sched:ben_not_pm", not any(s == "13-17" and p == "ben" for (_, s), p in seen.items()), ""),
              ("sched:chie<=5", per_person.get("chie", 0) <= 5, str(per_person.get("chie", 0))),
              ("sched:no_double_day", all(seen.get((d, "9-13")) != seen.get((d, "13-17")) for d in days), ""),
              ("sched:known_people", set(seen.values()) <= {"aki", "ben", "chie"}, str(set(seen.values())))]
    return checks
task("plan-schedule", "planning",
     "添付の制約を全て満たす週次シフト `schedule.json`（[{\"day\": \"mon|tue|wed|thu|fri\", \"slot\": \"9-13|13-17\", \"person\": \"aki|ben|chie\"}, ...] の10要素）を作ってください。制約が満たされているか自分で検算してから公開してください。",
     _grade_schedule, files={"constraints.txt": SCHEDULE_CONSTRAINTS})
def _grade_risks(a):
    got = load_json(a, "risks.json")
    if not isinstance(got, list):
        return [("json:risks.json", False, "missing/invalid")]
    lv = {"low", "medium", "high"}
    ok = all(isinstance(r, dict) and r.get("likelihood") in lv and r.get("impact") in lv and r.get("mitigation") and r.get("risk") for r in got)
    return [("risks:>=5", len(got) >= 5, f"{len(got)}"), ("risks:fields", ok, "")]
task("plan-risks", "planning",
     "添付のプロジェクト制約に対するリスク登録簿 `risks.json`（[{\"risk\": \"...\", \"likelihood\": \"low|medium|high\", \"impact\": \"low|medium|high\", \"mitigation\": \"...\"}, ...]、5件以上）を日本語で作ってください。",
     _grade_risks, files={"constraints.txt": PLAN_CONSTRAINTS})
def _grade_okr(a):
    got = load_json(a, "okr.json")
    if not isinstance(got, dict):
        return [("json:okr.json", False, "missing/invalid")]
    krs = got.get("key_results")
    ok = isinstance(krs, list) and len(krs) == 3 and all(isinstance(k, dict) and isinstance(k.get("target"), (int, float)) and k.get("metric") for k in krs)
    return [("okr:objective", bool(got.get("objective")), ""), ("okr:3_numeric_krs", ok, "")]
task("plan-okr", "planning",
     "添付の製品メモの製品について、四半期 OKR `okr.json`（{\"objective\": \"...\", \"key_results\": [{\"metric\": \"...\", \"target\": 数値, \"unit\": \"...\"}] ×3}）を日本語で作ってください。target は必ず数値。",
     _grade_okr, files={"product.txt": PRODUCT_NOTES})
def _grade_agenda(a):
    got = load_json(a, "agenda.json")
    if not isinstance(got, list):
        return [("json:agenda.json", False, "missing/invalid")]
    mins = [x.get("minutes") for x in got if isinstance(x, dict)]
    nums = [m for m in mins if isinstance(m, (int, float))]
    ok = len(nums) == len(mins) and all(m > 0 for m in nums)
    return [("agenda:sum60", ok and sum(nums) == 60, f"sum={sum(nums)}"), ("agenda:>=4", len(got) >= 4, ""),
            ("agenda:owners", all(isinstance(x, dict) and x.get("owner") in ("田中", "鈴木", "高橋") for x in got), "")]
task("plan-agenda", "planning",
     "添付の制約のプロジェクトのキックオフ会議（60分）のアジェンダ `agenda.json`（[{\"item\": \"...\", \"minutes\": 数値, \"owner\": \"田中|鈴木|高橋\"}, ...]）を日本語で作ってください。minutes の合計はちょうど60。",
     _grade_agenda, files={"constraints.txt": PLAN_CONSTRAINTS})

# ---- data transformation (exact)
def _grade_people_csv(a):
    rows = load_csv(a, "people.csv")
    if rows is None:
        return [("csv:people.csv", False, "missing/invalid")]
    exp = list(csv.DictReader(io.StringIO(PEOPLE_CSV_EXPECTED)))
    return [("csv:people.csv:exact", [dict(r) for r in rows] == exp, f"got {rows[:2]}")]
task("xform-json-to-csv", "data_transformation",
     "添付の people.json から、列 id,name,dept だけを持つ `people.csv` を作ってください（ヘッダ行あり、元の順序、余分な列なし）。",
     _grade_people_csv, files={"people.json": json.dumps(PEOPLE_JSON, ensure_ascii=False)})
task("xform-csv-to-json", "data_transformation",
     "添付の inventory.csv を `inventory.json`（オブジェクトの配列）に変換してください。qty は整数、unit_price は数値、discontinued は真偽値（true/false）にすること。",
     lambda a: [json_equals(a, "inventory.json", INVENTORY_JSON_EXPECTED)], files={"inventory.csv": INVENTORY_CSV})
task("xform-md-table", "data_transformation",
     "添付の table.md の Markdown 表を `cities.json`（オブジェクトの配列、population は整数）に変換してください。",
     lambda a: [json_equals(a, "cities.json", MD_TABLE_JSON)], files={"table.md": MD_TABLE})
task("xform-dates", "data_transformation",
     "添付の dates.txt（1行1日付、形式はばらばら、日/月/年の並びは文脈から判断）を全て ISO 形式 YYYY-MM-DD に正規化し、`dates.json`（元の順序の文字列配列）として作ってください。",
     lambda a: [json_equals(a, "dates.json", DATES_ISO + DATES_ISO2)], files={"dates.txt": "\n".join(DATES_RAW + DATES_RAW2)})
task("xform-flatten", "data_transformation",
     "添付の nested.json をキーをドット区切りで平坦化した `flat.json` に変換してください（配列はそのまま値として残す）。",
     lambda a: [json_equals(a, "flat.json", FLAT_EXPECTED)], files={"nested.json": json.dumps(NESTED, ensure_ascii=False)})

assert len(TASKS) == 50, len(TASKS)
assert len({t["id"] for t in TASKS}) == 50
CATEGORIES = sorted({t["category"] for t in TASKS})
assert all(sum(1 for t in TASKS if t["category"] == c) == 5 for c in CATEGORIES), Counter(t["category"] for t in TASKS)


def grade(task_id: str, arts: Artifacts) -> dict[str, Any]:
    t = next(x for x in TASKS if x["id"] == task_id)
    checks = t["grade"](arts)
    return {"checks": [{"name": n, "ok": ok, "detail": d} for n, ok, d in checks], "correct": all(ok for _, ok, _ in checks),
            "score": round(sum(1 for _, ok, _ in checks if ok) / max(1, len(checks)), 3)}
