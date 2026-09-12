# 確認資料と採用方針

確認日: 2026-09-12。将来のupstream変更は固定されていません。外部実装を採用するときにcommit hash・licenseを別途固定してください。

## Grok Bot
`https://x.ai/news/introducing-grok-bot`

Bot間thread、group chat、実ツール作業の製品例。公開説明であり、内部実装や品質の独立検証ではない。

## DeerFlow
`https://github.com/bytedance/deer-flow`

sandbox、skill、subagent、成果物体験の参照。公式READMEはMIT。完成品の全面forkではなく設計参考。

## Deep Agents
`https://github.com/langchain-ai/deepagents`

Worker harness候補。MIT。model-agnosticとあるが実modelごとのtool calling検査は必要。

## Deep Agents subagents
`https://docs.langchain.com/oss/python/deepagents/subagents`

model/prompt/tools/skills個別設定。同期subagentの終了待ちをpeer通信と混同しない。

## Deep Agents async
`https://docs.langchain.com/oss/python/deepagents/async-subagents`

非同期実行のAPI評価候補。永続双方向mailboxが必要な製品契約はadapterで検証する。

## Deep Agents v0.7
`https://www.langchain.com/blog/deep-agents-v0-7`

2026-07-29の公式報告。promptとtool説明の削減をevalで比較。結果を本製品へ一般化しない。

## Anthropic multi-agent research
`https://www.anthropic.com/engineering/multi-agent-research-system`

タスク境界、成果物参照、評価と復旧の考え方。チャット比token値は自社researchの観察であり普遍値ではない。

## Research lead prompt
`https://github.com/anthropics/claude-cookbooks/blob/main/patterns/agents/prompts/research_lead_agent.md`

分担と出力契約を参照。単純taskでも必ずsubagentを起動する指示は本製品では不採用。

## Agency Agents
`https://github.com/msitarzewski/agency-agents`

役割テンプレートの参考。人気を品質保証として扱わず、本文を丸ごと転載しない。

## Reality Checker
`https://github.com/msitarzewski/agency-agents/blob/main/testing/testing-reality-checker.md`

証拠ベースの評価を参考。初回を必ず不合格にする運用は不採用。

## Evidence Collector
`https://github.com/msitarzewski/agency-agents/blob/main/testing/testing-evidence-collector.md`

受入条件と実証拠の対応付けを参考。最低3〜5件の不具合を強制する指示や静止画だけを真実とする指示は不採用。

## Agent Skills specification
`https://agentskills.io/specification`

SKILL.mdとメタデータの規格。必要時読込の契約を参考。

## Anthropic Skills README
`https://raw.githubusercontent.com/anthropics/skills/main/README.md`

Apache-2.0のものとsource-availableのdocument skillsが混在。ファイル別のlicense確認が必要。

## Rivulets
`https://github.com/jwilson411/Rivulets`

チャット型Botチーム、handoff、timelineの比較例。READMEはBSL 1.1、hosted再提供に制限。主基盤には採らない。

## X search availability
`https://x.com/MarshalXuan/status/2088567862277607437`

検索結果で言及を確認したが投稿本文は取得エラー。技術・品質の根拠には採用しない。

## X developer search availability
`https://x.com/bromann?lang=en`

検索結果にDeep Agents実装への言及。プロフィール本文取得は失敗し、性能の根拠にはしない。

## 注意
このパッケージのプロンプトは原文の転載ではなく、この製品の目的・予算・安全条件に合わせて新しく記述した初期候補です。
参考repoの機能やstar数は動作性能を証明しません。ここではstar数を評価結果として使用していません。
