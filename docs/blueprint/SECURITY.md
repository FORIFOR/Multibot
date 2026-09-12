# Security and trust boundaries

初期はloopback接続・一人用・ローカル保存。ローカル実行でもクラウドLLMを選べば本文が送信される。
何がどのProviderへ送信されるかを接続時に説明する。ローカル保存とローカル推論を混同しない。

## Runtimeで強制する境界
Botのpromptを編集してもworkspace/credential/approval/egress/budgetの境界は変わらない。
Masterが自分でrole promptを変え、管理者権限を獲得できる経路を作らない。
各run/agentでcapability tokenを発行し、tool gatewayでscopeを照合する。
Peer間で共有するのは許可されたartifact ref。APIキー、raw cookie、全ホームディレクトリは渡さない。
Agentに戻すエラーからcredential、Authorization、URL queryの秘密を除去する。

## Sandbox
Git worktree・ディレクトリ・Python subprocessだけを隔離と呼ばない。
非特権実行、不要capability削除、CPU/RAM/時間/ストレージ制限、network egress制限。
Docker socket、SSH agent、ホストのブラウザprofile、cloud credentialを作業containerへ渡さない。
外部コードを本番service accountで起動しない。
SDKのfilesystem permissionだけでは任意shellによる回避を防げないのでOS境界でも強制する。
公開SaaSの悪意あるユーザーを単なる共有containerで隔離できるとは扱わない。

## Provider接続
API keyはOS keychainまたはserver secret store。設定には参照だけを保存。
base URL変更はユーザー操作であり、Masterや外部Skillから変更できない。
key参照を接続先originに結び付け、変更時は再確認し別originへ秘密を転送しない。
互換APIの自由URLはSSRF対象。scheme/host/DNS/redirectとegressを検査する。
ユーザーが明示したOllama等のローカル接続だけは管理された例外にする。
Botのweb fetchはmetadata service、loopback、private IPを初期禁止し、Providerのローカル例外を流用しない。

## 外部操作と復旧
publish、post、email、delete、payment、本番書込は原則approval。
approvalは操作内容hashと対象、費用上限に紐付ける。承認後に内容をすり替えられない。
再試行のためのidempotency keyを発行し、実行先の仕様に応じて使用する。
timeoutで実行済みか不明な操作はunknown outcomeへ移し、自動再送しない。
画面停止で外部操作が物理的に取り消されるとは保証せず、確定/不明/未実行を分けて表示する。

## 外部Skillとログ
Skillは非信頼コード・指示として扱う。署名/hashは内容の安全性を保証しない。
採用前にlicense、権限、ネットワーク先、scriptを審査。upstream変更を自動でstableに反映しない。
SNSから拾ったsystem文言をそのままpolicyとして実行しない。
生成HTML/SVGはuntrusted。主アプリと別origin、厳しいCSP、sandbox iframeで隔離する。
必要ないallow-same-origin/allow-scriptsを同時許可しない。raw HTML markdownを信頼しない。
共有リンクはOFFが初期値。ログ・成果物を選択し、秘密情報マスクをプレビューして明示公開する。
append-onlyやhashchainだけで管理者による改ざんを不可能とは呼ばない。必要なら外部署名・独立保存を追加する。
保存期限、削除、鍵の失効、backup削除の仕様を定める。append-onlyは永続保持の強制ではない。
