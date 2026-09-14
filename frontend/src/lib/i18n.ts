// Japanese-keyed dictionary: t("日本語") returns English when the UI language is 'en', else the key itself.
const EN: Record<string, string> = {
  '実行待ち': 'Queued', '実行枠が空き次第、開始します。': 'Starts when an execution slot is available.',
  '推論モード（Ollama）': 'Thinking mode (Ollama)', 'サーバーの既定': 'Server default',
  '短い出力で回答が空になる場合は無効を試してください。': 'Try disabling this if short responses return no answer.',
  '依頼': 'Request', '設定': 'Settings',
  '依頼は一度。': 'One request.', 'チームが作り、': 'A team builds, ', '確かめ': 'verifies', '、経緯を残す。': ', and leaves a trail.',
  'Master が成果物と完了条件を決め、必要な Bot だけが実際に作業します。成果物・Bot 間の実メッセージ・時系列は同じ実行記録から表示されます。台本の会話や固定の成功ログは使いません。':
    'A Master decides the deliverables and acceptance criteria; only the bots that are needed do the work. Artifacts, the real bot-to-bot messages and the timeline are projections of one execution record. No scripted chat, no canned success logs.',
  '接続': 'Connection', '/ モデル': '/ model', 'は疎通確認済み。予算上限': 'is verified. Budget cap', '設定を開く': 'open Settings',
  '開始前に設定が必要です：': 'Setup needed before you can start: ',
  '添付・URL・予算': 'Attachments · URLs · budget', '外部への投稿・送信は行いません（草案まで）。': 'Nothing is posted or sent externally (drafts only).',
  '設定へ': 'Go to Settings', '最近の実行': 'Recent runs', 'まだ実行はありません。': 'No runs yet.',
  '例: この製品の説明をもとに、紹介LPとREADME、SNS投稿案を作って。足りない情報は調べて、公開前の状態まで仕上げて。':
    'e.g. From this product description, build a launch page, a README and three social posts. Research what is missing. Stop before publishing.',
  '製品説明などのテキスト（任意）': 'Text such as a product description (optional)', '参照URL（空白区切り、任意）': 'Reference URLs (space-separated, optional)',
  'この run の予算上限 USD（既定': 'Budget cap for this run in USD (default', '開始中…': 'Starting…', '開始': 'Start',
  'FAKE PROVIDER — 実 LLM ではありません': 'FAKE PROVIDER — not a real LLM', '停止': 'Stop', '再開': 'Resume', '分岐して再実行': 'Fork & re-run',
  'ツール呼出も表示': 'Show tool calls', 'チーム': 'Team', '結果:': 'Result:', '時系列で見る': 'View in timeline', '成果物': 'Artifacts',
  'まだ成果物は公開されていません。': 'No artifacts published yet.', 'この revision の経緯': 'Trace of this revision', '関連イベントなし': 'No related events',
  '→ 時系列': '→ timeline', 'Bot 間のメッセージはまだありません。表示されるのは実際に宛先の受信箱へ配送されたメッセージだけです。':
    'No bot-to-bot messages yet. Only messages actually delivered to a recipient mailbox appear here.',
  '要約': 'Summary', '検証済み': 'Verified', '未解決・承認待ち': 'Unresolved / pending approval', 'なし': 'none', '次の一手': 'Next steps', '時間・費用': 'Time & cost',
  'final-report.md を開く': 'Open final-report.md',
  '承認要求はありません。外部への投稿・送信・支払い・本番変更は、承認されるまで実行されません。': 'No approval requests. External posting, sending, payments and production changes are not executed until approved.',
  'が': ' requests approval for ', 'の承認を要求': '', '承認': 'Approve', '却下': 'Reject', '承認待ち': 'Pending approval', '承認待ち {n} 件': '{n} pending approval(s)',
  '読み込み中…': 'Loading…', 'Master が記録した前提': 'Assumption recorded by the Master', '前提': 'assumption',
  'チームチャット': 'Team chat', '時系列': 'Timeline', '最終報告': 'Final report', 'Master が計画中…': 'Master is planning…',
  'メッセージを待っています': 'Waiting for messages', '実行のコミュニケーション': 'Run communication', '実メッセージ': 'Delivered messages',
  '実際に受信箱へ届いたメッセージを、担当Botごとに表示しています。': 'Messages delivered to a recipient mailbox, grouped by bot.', '返信': 'reply', 'メッセージを時系列で見る': 'View message in timeline',
  '手動固定プロンプト': 'user-locked prompt', '公開': 'published', '検証': 'check', 'レビュー': 'review', 'メッセージ': 'message',
  '報告はありません。': 'No report.', '実行完了後に、成果物・検証・未解決・費用・経緯参照をまとめた報告が生成されます。': 'After the run completes, a report of deliverables, checks, unresolved items, cost and trace references is generated.',
  '要約: 生成なし（証拠のみ）': 'Summary: not generated (evidence only)', '見積': 'estimate', '期限': 'expires',
  '変更は次の run から反映されます。進行中の run は開始時のスナップショットで動きます。': 'Changes apply to runs started after this revision. Running runs keep their start-time snapshot.',
  '開始条件を満たしています。': 'Ready to start.',
  '接続（API キーは参照のみ保存: env:NAME / keychain:service/account / file:/path）': 'Connections (API keys are stored as references only: env:NAME / keychain:service/account / file:/path)',
  '既定と上限': 'Defaults & limits', 'Bot（共通設定を継承し、必要なものだけ上書き）': 'Bots (inherit the defaults; override only what you need)',
  '保存': 'Save', 'tool calling と JSON schema 出力を実際に試します。': 'Makes real calls to confirm tool calling and JSON-schema output.',
  '接続を追加（例: ローカル Ollama = driver ollama, http://localhost:11434/v1, キーなし）': 'Add a connection (e.g. local Ollama: driver ollama, http://localhost:11434/v1, no key)',
  '追加': 'Add', '既定モデル': 'Default model', '既定接続': 'Default connection',
  '価格表（USD / 1M tokens）。価格不明のクラウドモデルは開始できません。': 'Price table (USD per 1M tokens). Cloud models without a price cannot start.',
  '実効': 'Effective', '手動固定（Master は上書きしない）': 'User-locked (the Master will not overwrite)', '元に戻す': 'Revert',
  '設定が別の場所で更新されました。再読み込みします。': 'The config was updated elsewhere. Reloading.',
  'api_key_ref 例: env:ANTHROPIC_API_KEY': 'api_key_ref e.g. env:ANTHROPIC_API_KEY',
  'Anthropic のサーバ側 refusal fallback（別モデルへ自動ルーティング）。既定 OFF。': "Anthropic server-side refusal fallback (auto-routes to another model). Off by default.",
  '接続を保存しました（要 再疎通確認）': 'Connection saved (probe again)', '疎通確認を実行しました': 'Probe finished', '確認中…': 'Probing…',
  '疎通確認（実 API 呼出・少額）': 'Probe (real call, a few cents)', '接続を追加しました': 'Connection added', '既定と上限を保存しました': 'Defaults & limits saved',
  '無効': 'disabled', '有効': 'enabled', 'を': ' ', '化しました': '', '接続を変更しました': 'Connection changed', 'モデルを変更しました': 'Model changed',
  'effort を変更しました': 'Effort changed', 'プロンプトを閉じる': 'Close prompt', 'システムプロンプト': 'System prompt', 'ロック状態を変更しました': 'Lock state changed',
  'ユーザー編集版': 'user-edited', 'ファイル': 'file', 'プロンプトを保存しました（新 revision）': 'Prompt saved (new revision)', '同梱プロンプトに戻しました': 'Reverted to the bundled prompt',
  '差分': 'diff', '文字': 'chars', 'のモデル ID': ' model id', 'どの Bot のモデルを変えて分岐しますか？': 'Which bot should get a different model for the fork?',
  '空欄なら設定変更なしで再実行': 'leave empty to re-run without changes', '件': '', '前提: ': 'assumption: ', '対象読者': 'audience',
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
