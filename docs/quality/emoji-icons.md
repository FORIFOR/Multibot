# ユーザー指定の絵文字アイコン

対象: マイチームの既存Bot設定、共通BotAvatar、会話。既存emoji契約と保存APIを利用し、未設定は役割別の絵文字へ。候補選択/自由入力/プレビュー/既定復帰を提供。会話でsnapshotのemojiを渡していなかった箇所を修正。過去の実行snapshotは改変しない。保存は次の依頼から反映。

検証: macOS Chrome、390/1440px、実ローカルの隔離サーバー8798。実設定をUIで🦊へ変更→保存API照合→reload→Home反映を確認後、finallyで元のemojiへ戻した。モデル/接続は変更せず、新規モデル実行なし。ユーザー稼働サーバー8796の設定は変更しない。過去の実会話にemojiを表示し、描画キャラクターDOMがないことを確認。画像を目視。

PASS: build/typecheck exit0（emoji-icons-build.log）、実ブラウザ保存・再読み込み・Home/会話・横溢れなし・例外なし（emoji-icons-browser.log、exit0）。自己検証。証拠は artifacts/product-quality/emoji-icons/。BLOCKED: 実ユーザー評価と全OSでのemoji字体、未実施を合格としない。

コマンド: repo rootで `python3 artifacts/product-quality/run-command.py emoji-icons-build pnpm --dir frontend build`。frontend cwdで `python3 ../artifacts/product-quality/run-command.py emoji-icons-browser node scripts/emoji-icons-check.mjs`。
