// Japanese-keyed dictionary: t("日本語") returns English when the UI language is 'en', else the key itself.
const EN: Record<string, string> = {
  'モデル呼出中': 'Calling the model',
  '実行待ち': 'Queued', '実行枠が空き次第、開始します。': 'Starts when an execution slot is available.',
  '推論モード（Ollama）': 'Thinking mode (Ollama)', 'サーバーの既定': 'Server default',
  '短い出力で回答が空になる場合は無効を試してください。': 'Try disabling this if short responses return no answer.',
  '依頼': 'Request', '設定': 'Settings',
  '確かめ': 'verifies', 
  '接続': 'Connection', 
  '設定へ': 'Go to Settings', 'まだ実行はありません。': 'No runs yet.',
  '製品説明などのテキスト（任意）': 'Text such as a product description (optional)', '参照URL（空白区切り、任意）': 'Reference URLs (space-separated, optional)',
  '依頼に含める資料': 'Materials for this request', 'txt / md / csv、1ファイル512KBまで': 'txt / md / csv, up to 512KB per file',
  '添付済み資料': 'Attached materials', 'txt / md / csv のみ添付できます。': 'Only txt, md or csv files can be attached.', 'まとめて取得': 'Download bundle', 'この版を採用': 'Adopt this version', '採用版': 'Adopted', '採用中…': 'Adopting…', 'この版を採用しました。': 'This version is adopted.', '比較元の版': 'Compare from revision', '比較する版を選択': 'Choose a revision to compare', '差分を見る': 'View diff', '成果物の差分': 'Artifact diff', '変更はありません。': 'No changes.', 'この形式の差分には対応していません。': 'Text diff is not available for this format.',
  '512KB 以下のファイルを選んでください。': 'Choose a file up to 512KB.', 'ファイルを読み込めませんでした。': 'The file could not be read.',
  '削除': 'Remove', '人間の指示': 'Human instruction', '受信': 'Received',
  '次に開始するタスクへ引き継ぎます。実行中の計画は自動で書き換えません。': 'Passed to the next task session. The current plan is not rewritten automatically.',
  '指示を入力': 'Add a direction', '変更': 'Change', '質問': 'Question', '編集': 'Edit',
  '指示を送る': 'Send direction', '送信中…': 'Sending…', '指示を受信しました。': 'Direction received.', '指示を送信できませんでした。': 'Could not send the direction.',
  'この run が進行中または開始前のときだけ送信できます。': 'You can send directions only before or while this run is executing.',
  '再開または分岐してから指示を送ってください。': 'Resume or fork the run before sending a direction.',
  '開始': 'Start',
  'FAKE PROVIDER — 実 LLM ではありません': 'FAKE PROVIDER — not a real LLM', '停止': 'Stop', '再開': 'Resume', '分岐して再実行': 'Fork & re-run',
  'ツール呼出も表示': 'Show tool calls', 'チーム': 'Team', '結果:': 'Result:', '時系列で見る': 'View in timeline', '成果物': 'Artifacts',
  'まだ成果物は公開されていません。': 'No artifacts published yet.', 'この revision の経緯': 'Trace of this revision', '関連イベントなし': 'No related events',
  '→ 時系列': '→ timeline', 'Bot 間のメッセージはまだありません。表示されるのは実際に宛先の受信箱へ配送されたメッセージだけです。':
    'No bot-to-bot messages yet. Only messages actually delivered to a recipient mailbox appear here.',
  '要約': 'Summary', '検証済み': 'Verified', '未解決・承認待ち': 'Unresolved / pending approval', 'なし': 'none', '次の一手': 'Next steps', '時間・費用': 'Time & cost',
  'final-report.md を開く': 'Open final-report.md',
  '承認要求はありません。外部への投稿・送信・支払い・本番変更は、承認されるまで実行されません。': 'No approval requests. External posting, sending, payments and production changes are not executed until approved.',
  'が': ' requests approval for ', 'の承認を要求': '', '承認': 'Approve', '却下': 'Reject', '承認待ち': 'Pending approval', 
  '読み込み中…': 'Loading…', 'Master が記録した前提': 'Assumption recorded by the Master', '前提': 'assumption',
  'チームチャット': 'Team chat', '時系列': 'Timeline', '最終報告': 'Final report', 'Master が計画中…': 'Master is planning…',
  '実行の補助情報': 'Run supporting information',
  'メッセージを待っています': 'Waiting for messages',
  'Bot 間のメッセージはありませんでした': 'No bot-to-bot messages', 'この実行では、受信箱へ配送されたメッセージはありません。作業の経緯は時系列で確認できます。': 'No message was delivered to an inbox in this run. Follow the work in the timeline.',
  '依頼文の全文を表示': 'Show the full request', '依頼文をたたむ': 'Collapse the request', '実行のコミュニケーション': 'Run communication', '実メッセージ': 'Delivered messages',
  '実際に受信箱へ届いたメッセージを、担当Botごとに表示しています。': 'Messages delivered to a recipient mailbox, grouped by bot.', '返信': 'reply', 'メッセージを時系列で見る': 'View message in timeline',
  '協働フロー': 'Collaboration flow', '参加Bot': 'bots', '作業スレッド': 'work threads', 'メッセージを整理': 'Organize messages', 'メッセージを検索': 'Search messages', 'すべて': 'All', '件表示': ' shown', '該当するメッセージはありません': 'No matching messages',
  '手動固定プロンプト': 'user-locked prompt', '公開': 'published', '検証': 'check', 'レビュー': 'review', 'メッセージ': 'message',
  '報告はありません。': 'No report.', '実行完了後に、成果物・検証・未解決・費用・経緯参照をまとめた報告が生成されます。': 'After the run completes, a report of deliverables, checks, unresolved items, cost and trace references is generated.',
  '要約: 生成なし（証拠のみ）': 'Summary: not generated (evidence only)', '見積': 'estimate', '期限': 'expires',
  '接続（API キーは参照のみ保存: env:NAME / keychain:service/account / file:/path）': 'Connections (API keys are stored as references only: env:NAME / keychain:service/account / file:/path)',
  '既定と上限': 'Defaults & limits', 
  '保存': 'Save', 'tool calling と JSON schema 出力を実際に試します。': 'Makes real calls to confirm tool calling and JSON-schema output.',
  '接続を追加（例: ローカル Ollama = driver ollama, http://localhost:11434/v1, キーなし）': 'Add a connection (e.g. local Ollama: driver ollama, http://localhost:11434/v1, no key)',
  '追加': 'Add', '既定モデル': 'Default model', '既定接続': 'Default connection',
  '価格表（USD / 1M tokens）。価格不明のクラウドモデルは開始できません。': 'Price table (USD per 1M tokens). Cloud models without a price cannot start.',
  '設定が別の場所で更新されました。再読み込みします。': 'The config was updated elsewhere. Reloading.',
  'api_key_ref 例: env:ANTHROPIC_API_KEY': 'api_key_ref e.g. env:ANTHROPIC_API_KEY',
  'Anthropic のサーバ側 refusal fallback（別モデルへ自動ルーティング）。既定 OFF。': "Anthropic server-side refusal fallback (auto-routes to another model). Off by default.",
  '接続を保存しました（要 再疎通確認）': 'Connection saved (probe again)', '疎通確認を実行しました': 'Probe finished', '確認中…': 'Probing…',
  '疎通確認（実 API 呼出・少額）': 'Probe (real call, a few cents)', '接続を追加しました': 'Connection added', '既定と上限を保存しました': 'Defaults & limits saved',
  '無効': 'disabled', '有効': 'enabled', 'を': ' ', 
  'システムプロンプト': 'System prompt', 
  'ファイル': 'file', 
  '差分': 'diff', '文字': 'chars', 
  '件': '', 
}
export type Lang = 'ja' | 'en'
let current: Lang = 'ja'
try {
  const saved = localStorage.getItem('agentteam.lang') as Lang | null
  current = saved || ((navigator.language || 'ja').toLowerCase().startsWith('ja') ? 'ja' : 'en')
} catch { /* no storage */ }
export function getLang(): Lang { return current }
export function setLang(l: Lang) { current = l; try { localStorage.setItem('agentteam.lang', l) } catch { /* ignore */ } }
export function t(ja: string, vars?: Record<string, string | number>): string {
  let s = current === 'en' ? (EN[ja] ?? ja) : ja
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, String(v))
  return s
}
