"""Post launch threads to X with the OAuth1 credentials from an env file. Usage:
   ENV_FILE=~/Projects/RingZero/.env python marketing/post_x.py en|ja [--dry]
Weighted length is checked before anything is sent (CJK = 2, URL = 23)."""
from __future__ import annotations
import json, os, sys, time, unicodedata, re
import requests
from requests_oauthlib import OAuth1

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = "https://github.com/FORIFOR/Multibot"
SITE = "https://forifor.github.io/Multibot/"
SITE_JA = "https://forifor.github.io/Multibot/ja/"
VIDEO = os.path.join(ROOT, "docs/media/hero.mp4")
REPORT_IMG = os.path.join(ROOT, "docs/media/report.png")
LP_IMG = os.path.join(ROOT, "docs/media/real-run4-lp.png")

THREADS = {
"en": [
 (f"An open-source AI team that ships real work — with a conversation you can follow.\n\nOne request → Master plans → Researcher / Builder / Reviewer do the work → files PLUS the real bot-to-bot messages, a timeline, and checks bound to each revision.\n\n{REPO}", VIDEO),
 ("The chat panel is not a transcript written afterwards. Every line is a delivered message: a Builder question wakes the Researcher, which answers with reply_to. Acknowledgements never wake a model.", None),
 ("Verification is an event bound to an artifact hash. The Reviewer fails index.html r1 → the Builder publishes r2 → the Reviewer re-checks r2. The final report is compiled from those events, so \"started\" never becomes \"passed\".", REPORT_IMG),
 ("Limits live in the runtime, not in the prompt: tool scope, write scope, budget reserved per call, approvals with hash+nonce, cancel / resume / fork. Unknown model prices refuse to start.", None),
 ("No API key needed if you have Claude Code: each agent session runs through `claude -p`, with the team's tools exposed as MCP tools. Also Claude API, OpenAI-compatible endpoints, Ollama. Per-bot model, endpoint and prompt; configured vs provider-reported model both shown.", None),
 (f"Real run, unedited, committed to the repo: claude-opus-5 built a launch page + 3 post drafts, 10 checks pass, reviewer 6/6, $1.66 list-price, 19 min. Run 1 exposed a reviewer bug — fixed. The demo video uses a scripted provider (labelled on screen). MIT.\n\n{SITE}", LP_IMG),
],
"ja": [
 (f"「依頼は一度。AI チームが作り、確かめ、経緯を残す。」\n\n一文の依頼から Master が計画し、Researcher / Builder / Reviewer が実際に作業。成果物と一緒に、Bot 間の実メッセージ・時系列・revision 単位の検証が返ってきます。OSS (MIT) で公開しました。\n\n{REPO}", VIDEO),
 ("チャットは後付けの台本ではなく、実際に配送されたメッセージだけ。Builder の質問で Researcher が起動して回答し、reply_to で紐付きます。相槌ではモデルを起動しません。", None),
 ("検証は成果物のハッシュに紐付くイベント。Reviewer が r1 を不合格 → Builder が r2 を公開 → r2 に再検証。最終報告はこのイベントから組み立てるので「開始」が「合格」にすり替わりません。", REPORT_IMG),
 ("権限・書込範囲・予算（予約込み）・承認（hash+nonce）・停止/再開/分岐は Runtime が強制。価格不明のモデルは開始できません。", None),
 ("Claude Code があれば API キー不要。各 Bot のセッションを claude -p で動かし、チームのツールを MCP で公開します。Claude API / OpenAI 互換 / Ollama も可。設定したモデルと実際に応答したモデルを両方表示。", None),
 (f"実 run（無編集でリポジトリに同梱）: claude-opus-5 が LP と投稿 3 案を作成、検証 10 件 pass、レビュー 6/6、$1.66、19 分。デモ動画はスクリプト provider（画面に表示）。\n\n{SITE_JA}", LP_IMG),
],
"en2": [
 (f"What the Builder shipped in the real run: a complete single-file launch page under the Master's recorded assumptions (no prices, no invented numbers, placeholder URLs). Reviewer 6/6 pass. Provider-reported model: claude-opus-5. Unedited files in the repo.\n\n{REPO}", LP_IMG),
],
"ja2": [
 (f"実 run で Builder が実際に作った LP。Master が記録した前提（価格・実績数値を書かない、URL はプレースホルダ）どおりに、単一ファイルで完成。Reviewer は 6/6 pass、応答モデルは claude-opus-5。生成物は無編集でリポジトリに置いています。\n\n{SITE_JA}", LP_IMG),
],
}

URL_RE = re.compile(r"https?://\S+")
def weighted_len(text: str) -> int:
    t = URL_RE.sub("x" * 23, text)
    n = 0
    for ch in t:
        n += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return n

def auth():
    return OAuth1(os.environ["X_API_KEY"], os.environ["X_API_SECRET"], os.environ["X_ACCESS_TOKEN"], os.environ["X_ACCESS_SECRET"])

def upload_media(a, path: str) -> str:
    data = open(path, "rb").read()
    if path.endswith(".mp4"):
        base = "https://upload.twitter.com/1.1/media/upload.json"
        r = requests.post(base, auth=a, data={"command": "INIT", "media_type": "video/mp4", "total_bytes": len(data), "media_category": "tweet_video"}, timeout=60)
        r.raise_for_status(); mid = r.json()["media_id_string"]
        chunk = 4 * 1024 * 1024
        for i in range(0, len(data), chunk):
            rr = requests.post(base, auth=a, data={"command": "APPEND", "media_id": mid, "segment_index": i // chunk}, files={"media": data[i:i + chunk]}, timeout=120)
            rr.raise_for_status()
        r = requests.post(base, auth=a, data={"command": "FINALIZE", "media_id": mid}, timeout=60); r.raise_for_status()
        info = r.json().get("processing_info")
        while info and info.get("state") in ("pending", "in_progress"):
            time.sleep(info.get("check_after_secs", 3))
            r = requests.get(base, auth=a, params={"command": "STATUS", "media_id": mid}, timeout=60); r.raise_for_status()
            info = r.json().get("processing_info")
        if info and info.get("state") == "failed":
            raise RuntimeError(f"video processing failed: {info}")
        return mid
    r = requests.post("https://upload.twitter.com/1.1/media/upload.json", auth=a, files={"media": (os.path.basename(path), data)}, timeout=60)
    r.raise_for_status()
    return r.json()["media_id_string"]

def post(a, text: str, media_id: str | None, reply_to: str | None) -> str:
    body: dict = {"text": text}
    if media_id: body["media"] = {"media_ids": [media_id]}
    if reply_to: body["reply"] = {"in_reply_to_tweet_id": reply_to}
    r = requests.post("https://api.x.com/2/tweets", auth=a, json=body, timeout=60)
    if r.status_code >= 300:
        raise RuntimeError(f"{r.status_code} {r.text[:300]}")
    return r.json()["data"]["id"]

def main():
    lang = sys.argv[1]; dry = "--dry" in sys.argv
    thread = THREADS[lang]
    for i, (t, _) in enumerate(thread, 1):
        n = weighted_len(t)
        assert n <= 280, f"tweet {i} too long: {n}"
        print(f"[{lang} {i}] weighted={n}")
    if dry: return
    a = auth(); ids = []; prev = None
    for i, (t, media) in enumerate(thread, 1):
        mid = upload_media(a, media) if media else None
        tid = post(a, t, mid, prev); ids.append(tid); prev = tid
        print(f"posted {i}: https://x.com/i/status/{tid}", flush=True)
        time.sleep(2)
    with open(os.path.join(ROOT, "marketing/POSTED.md"), "a") as f:
        f.write(f"\n## X ({lang}) {time.strftime('%Y-%m-%d %H:%M JST')}\n" + "\n".join(f"- https://x.com/i/status/{t}" for t in ids) + "\n")

if __name__ == "__main__":
    main()
