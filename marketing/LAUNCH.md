# Launch kit (drafts — nothing here has been posted)

Posting on X, Hacker News, Reddit, Product Hunt, Zenn or Qiita requires your accounts. These are ready-to-paste drafts.
Every draft keeps the disclosure that the demo uses the scripted provider and that real-model runs are not yet verified.
Do not remove that; it is the difference between this project and the "N bots chatting" demos it is positioned against.

## Positioning (one line, use everywhere)
EN: **An open-source AI team that ships real work — with a conversation you can follow.**
JA: **依頼は一度。AI チームが作り、確かめ、成果物と経緯を残す。**

Links: repo https://github.com/FORIFOR/Multibot · site https://forifor.github.io/Multibot/ · video docs/media/demo.mp4 · GIF docs/media/demo.gif

## Order of operations (recommended, same day)
1. Show HN in the US morning (13:00–15:00 JST is ~midnight ET; better: 22:00–24:00 JST = 09:00–11:00 ET).
2. X thread (EN) 10 minutes after, quote the HN link in the last post. Then the JA thread.
3. Reddit r/LocalLLaMA (Ollama support is the hook there) and r/artificial in the same hour.
4. Zenn article (JA) the next morning with the timeline/report screenshots.
5. Product Hunt only after the first real-model smoke has been run and the README says so.

## Show HN
Title (80 chars max): `Show HN: Agent Team – an open-source AI team whose work you can audit`

Body:
```
Hi HN. Agent Team is a local-first tool where one request becomes a small AI team (Master → Researcher / Builder / Reviewer) that actually does the work and hands you artifacts plus an auditable trace.

What's different from "put N bots in a chat":
- The chat panel is a projection of real message deliveries (send_message → recipient mailbox → message.sent event). A question wakes the other bot to answer. Nothing is narrated after the fact.
- Checks and review verdicts are events bound to an artifact revision hash. The final report is compiled from the event log; the model's summary can't turn "started" into "passed".
- Tool scope, write scope, budget (spent + reserved), approvals and cancel are enforced by the runtime, not prompt wording. Unknown model prices refuse to start.
- Per-bot endpoint/model/prompt (lockable). Configured vs provider-reported model are both shown; no silent fallbacks.
- Replay never calls a model. Fork from a checkpoint with a different model for one bot.

Stack: Python/FastAPI + SQLite (WAL, append-only events, SSE), React. Works with Claude (official SDK), OpenAI-compatible endpoints, Ollama. macOS seatbelt sandbox for builder commands.

Honesty section: the 37s demo on the site drives the real UI/runtime with a scripted test provider (labelled on screen) because I wanted it deterministic and free. 36 deterministic tests pass; the end-to-end real-model smoke script exists but I haven't got a public run to show yet. Prompts are original seeds, not benchmark-tuned. No Docker sandbox yet.

Repo: https://github.com/FORIFOR/Multibot
Site + video: https://forifor.github.io/Multibot/

I'd love feedback on the review→revise loop bound to revisions, and on whether the "fewer messages, more evidence" trade-off holds up for your tasks.
```

## X thread — EN
1/ I built an open-source AI team that ships real work — with a conversation you can follow.
One request → Master plans → Researcher/Builder/Reviewer actually work → you get the files AND the real bot-to-bot messages, a timeline, and checks bound to each revision.
[attach intro.mp4 (58s narrated) — or demo.mp4 for the raw version]
2/ The chat isn't a transcript written afterwards. Every line is a delivered message. A question from the Builder wakes the Researcher, who answers with reply_to. Acknowledgements never wake a model.
3/ Verification is an event bound to an artifact hash. Reviewer fails index.html r1 → Builder publishes r2 → Reviewer re-runs the check on r2. The final report is compiled from those events.
[attach docs/media/report.png]
4/ Limits live in the runtime, not the prompt: tool scope, write scope, budget reserved per call, approvals with hash+nonce, cancel/resume/fork. Unknown model prices refuse to start.
5/ Per-bot endpoint + model + prompt (lockable). Claude via the official SDK, any OpenAI-compatible endpoint, or Ollama. Configured vs provider-reported model both shown. No silent fallbacks.
6/ Disclosure: the demo runs the real UI/runtime on a scripted test provider (labelled on screen) so it's deterministic. 36 tests pass; the real-model smoke script is in the repo, and I haven't published a real run yet. MIT.
★ https://github.com/FORIFOR/Multibot  ·  site: https://forifor.github.io/Multibot/

## X thread — JA
1/ 「依頼は一度。AI チームが作り、確かめ、成果物と経緯を残す。」
一文の依頼から Master が計画し、Researcher / Builder / Reviewer が実際に作業。成果物と一緒に、Bot 間の実メッセージ・時系列・revision 単位の検証結果が返ってきます。OSS (MIT) で公開しました。
[動画 intro.mp4（58 秒・ナレーション付き）]
2/ チャットは後から書いた台本ではなく、実際に配送されたメッセージの投影です。Builder の質問で Researcher が起動して回答し、reply_to で紐付きます。相槌ではモデルを起動しません。
3/ 検証は成果物のハッシュに紐付くイベント。Reviewer が index.html r1 を不合格 → Builder が r2 を公開 → r2 に対して再検証。最終報告はこのイベントから組み立てるので「開始」が「合格」にすり替わりません。
4/ 権限・書込範囲・予算（予約込み）・承認（hash+nonce）・停止/再開/分岐は Runtime が強制。価格不明のモデルは開始できません。
5/ Bot ごとに接続先・モデル・プロンプト（手動固定可）を上書き。Claude（公式 SDK）/ OpenAI 互換 / Ollama。設定したモデルと実際に応答したモデルを両方表示。無断フォールバックなし。
6/ 正直に: デモは実 UI/Runtime をテスト用のスクリプト provider で動かしたもの（画面に表示）。決定論的テスト 36 件は通過、実 LLM スモークのスクリプトは同梱、実 run の公開はこれからです。
★ https://github.com/FORIFOR/Multibot  ·  https://forifor.github.io/Multibot/

## Reddit
r/LocalLLaMA title: `Agent Team: local-first multi-agent runner with real bot-to-bot mailboxes, revision-bound checks, Ollama support (MIT)`
Body: Show HN body + one paragraph: "Ollama: set driver `ollama`, base_url `http://localhost:11434/v1`, price is 0 by design for local; the probe checks that your model actually does tool calling + JSON schema before you can start."

r/artificial title: `I open-sourced an AI team whose work you can audit: real messages, revision-bound verification, runtime-enforced budgets`

## Zenn (JA) article outline
Title: 「Bot 同士を会話させるのではなく、仕事の経緯がそのままチャットになる」マルチエージェントを OSS で作った
1. 動機: 会話を見せるための Bot と、仕事に必要なやり取りが残る構造の違い
2. アーキテクチャ: append-only Event Store → chat / timeline / report の投影（図: docs/media/timeline.png）
3. 実メッセージ配送と返信セッション（コード: runtime/mailbox.py, scheduler._reply_session）
4. revision 単位の検証とレビュー→修正ループ（図: docs/media/report.png）
5. Runtime 強制の権限・予算・承認（policy.py）
6. Master の計画を Runtime が検査する（planner.validate_plan）
7. 未検証のこと（実 LLM スモーク、プロンプト最適化、Docker sandbox）
8. 試し方（Quickstart）

## Product Hunt (later)
Tagline (60): `An AI team that ships real work — with a trace you can audit`
First comment: the Show HN honesty paragraph, plus the first real-model run's evidence JSON.

## Assets checklist
- [x] docs/media/intro.mp4 (1280x720, 58s, title cards + narrated walkthrough + BGM 'I03 Sunlit Launch'; disclosure on screen)
- [x] docs/media/demo.mp4 (1280px, 37s raw walkthrough, no timing edits)
- [x] docs/media/demo.gif (README hero)
- [x] docs/media/run.png · timeline.png · report.png · settings.png
- [x] OG image docs/media/poster.jpg (site meta)
- [ ] A real-model run's evidence (run scripts/smoke_real_llm.py with a key) — add to README before Product Hunt
