# 受入ケースの対応表（2026-09-12）

`cases.jsonl` の 40 ケースは試験計画であり、`execution_status` は仕様どおり `not_run` のまま維持しています。
下表は「決定論的テスト（fake provider）でカバー」「実 LLM が必要（未実施）」「未実装」の区分です。
fake provider での合格は実 LLM の合格を意味しません。

| id | 区分 | 根拠 |
| --- | --- | --- |
| simple-single | 実 LLM 必要 | Master の計画次第。Runtime は 1 task の plan を受理する |
| real-collaboration | 実 LLM 必要 | `scripts/smoke_real_llm.py` |
| independent-parallel | 決定論的 | scheduler の並列上限（`max_active_workers`） |
| dependency-order | 決定論的 | `test_three_agent_collaboration`（t2 は t1 accepted 後に開始） |
| peer-question | 決定論的 | 同上（question → 返信セッション → answer, reply_to） |
| no-scripted-chat | 設計 | chat は `message.sent` イベントのみから投影。fake は UI に明示 |
| prompt-user-lock | 決定論的 | `test_agent_patch_revision_conflict_and_user_lock` |
| model-per-agent | 決定論的 | 実効設定・snapshot に per-agent model を記録（実経路は実 LLM で要確認） |
| endpoint-per-agent | 決定論的（構造） | per-agent connection。origin-bound key の実確認は未実施 |
| config-snapshot | 決定論的 | `test_config_snapshot_survives_later_edits` |
| unsupported-tools | 決定論的 | probe 不合格の接続では開始不可（`test_connection_change_resets_capability_and_probe_fake`） |
| provider-429 | 未検証 | driver は retry-after 付き上限 retry を実装。実 API で未確認 |
| provider-401 | 未検証 | secret を除去した `model.failed` を記録。実 API で未確認 |
| provider-500 | 未検証 | fallback は行わない設計。実 API で未確認 |
| budget-parallel | 決定論的 | `test_budget_reservation_blocks_parallel_overrun` |
| unknown-pricing | 決定論的 | `test_unknown_pricing_is_not_free` / precheck |
| loop-cutoff | 決定論的 | `max_revision_rounds` で partial（`_apply_review`） |
| artifact-revision | 決定論的 | review/check が revision に紐付く（`test_three_agent_collaboration`） |
| workspace-boundary | 決定論的 | `test_workspace_boundary_and_tool_scope_denied` |
| concurrent-write | 設計 | output path は task 間で一意（plan 検証）。同一 path は revision 化 |
| prompt-injection | 実 LLM 必要 | platform-policy + tool scope。実 LLM で要評価 |
| skill-injection | 設計 | 外部 Skill のインストール経路なし（同梱のみ、hash 記録） |
| credential-redaction | 決定論的 | `test_redaction_masks_known_and_pattern_secrets` |
| artifact-xss | 決定論的（ヘッダ） | raw endpoint の `sandbox` CSP + iframe sandbox（`test_run_lifecycle_events_cursor_and_artifacts`） |
| approval-required | 決定論的 | `test_approval_pauses_run_then_resumes_after_resolution` |
| approval-tamper | 決定論的 | 同上（hash 不一致で拒否） |
| crash-resume | 決定論的 | `test_cancel_then_resume_keeps_accepted_work` / サーバ再起動時は interrupted |
| side-effect-timeout | 未実装 | 外部書込の実行器がまだ無い |
| replay-no-llm | 決定論的 | `test_replay_makes_no_model_calls` |
| sse-reconnect | 決定論的 | `test_stream_replays_from_cursor_and_dedupes`（Last-Event-ID） |
| same-time-order | 決定論的 | `test_event_seq_is_insertion_order_even_at_same_time` |
| source-unavailable | 実 LLM 必要 | web_fetch は取得範囲・truncated を明示 |
| summary-grounding | 実 LLM 必要 | 報告は証拠 JSON から生成、artifact 参照は実在検証 |
| no-invented-bugs | 実 LLM 必要 | Reviewer prompt / evidence-review Skill |
| first-run-input | 決定論的 | Home は一文 + 開始のみ |
| real-llm-ci | 未実施 | `scripts/smoke_real_llm.py` |
| share-privacy | 未実装 | 共有機能なし（OFF） |
| single-baseline | 未実装 | — |
| cancel-scope | 決定論的 | cancel テスト。外部操作の確定/不明区分は外部実行器と併せて未実装 |
| skill-hash | 決定論的（構造） | config.resolved に skill sha256 を記録 |
