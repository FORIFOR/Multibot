# 取消・約定レビューの追加根拠

2026-09-20 JSTに公開公式資料を再確認。API接続・発注の試験記録ではない。元の添付資料は変更していない。

出典: [Alpaca Websocket Streaming](https://docs.alpaca.markets/us/docs/websocket-streaming)、Trade Updates節。

公式仕様の要約:
- 注文更新メッセージにはeventと、REST APIと同じ注文オブジェクトorderが含まれる。
- rejectedは注文の拒否、order_cancel_rejectedは取消要求の拒否であり、異なるイベント。
- fill/partial_fillのqtyはその約定イベントの数量であり、注文全体の累積約定数量とは区別する。
- pending_cancelは取消待ち。すべての取消がこのイベントを経由するわけではない。

設計への推論（APIが提供する保証とは区別）:
取消要求の結果だけを理由に、元注文の確認済み約定をゼロへ初期化してはいけない。注文状態・累積約定と取消要求の進行状態を区別し、全約定、残量取消、取消要求拒否、照会不能の条件を設計する。取消拒否を元注文の消滅や新規発注の許可と解釈しない。約定取消・訂正等の別事象まで、累積数量が絶対に減らないとの保証をこの資料から推定しない。

対象草稿: architecture.md seq95、12561bytes、SHA256 e61e62f79baca03069c6f6d399c6bbee5feb288912fedc2f5fde12328ae66ca5。第3.2節の約定量ゼロ初期化と取消拒否後の再発注許可は上記と整合しない。
