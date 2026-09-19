"""Builds docs/index.html and docs/ja/index.html from one template so the two languages cannot drift.
Run: python3 docs/site/build_site.py   (no dependencies). The before/after text of the three findings is copied
verbatim from docs/record.js, the recorded run; do not replace it with a summary."""
import html, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]  # docs/
ACC = {'master':'crown','researcher':'lens','builder':'pencil','reviewer':'check'}
def bot(kind, state='idle', size='stage'):
    face = 'happy' if state=='done' else 'focus' if state in ('thinking','reviewing') else 'normal'
    working = state in ('thinking','researching','building','reviewing')
    mark = '<i></i><i></i><i></i>' if working else ('✓' if state=='done' else '')
    return (f'<span class="bot-character bot-{kind} bot-{state} bot-size-{size}" data-bot aria-hidden="true">'
            f'<span class="bot-antenna"><i></i></span><span class="bot-head"><span class="bot-face face-{face}"><i class="eye left"></i><i class="eye right"></i><i class="mouth"></i></span>'
            f'<span class="bot-accessory accessory-{ACC[kind]}"></span></span><span class="bot-body"><i class="bot-heart"></i></span>'
            f'<span class="bot-state-mark{" is-working" if working else ""}">{mark}</span></span>')
CMD = 'uvx --from "git+https://github.com/FORIFOR/Multibot#subdirectory=backend" agentteam quickstart'
EV = 'https://github.com/FORIFOR/Multibot/tree/main/docs/evidence/'
T = {
 'ja': dict(lang='ja', base='../', self='https://forifor.github.io/Multibot/ja/', other='../', other_lang='en', other_label='EN',
  title='Agent Team — 頼むのは一度。チームが作って、確かめる。',
  desc='調べる・つくる・確かめるを、AIのチームが分担。できたファイルと確認の経緯まで受け取れる、あなたのPCで動くオープンソースのAI作業アプリ。',
  skip='本文へ', nav=[('#team','チーム'),('#proof','実際の記録'),('#privacy','データの扱い'),('#faq','よくある質問')], nav_cta='始める',
  h1='頼むのは一度。<br>チームが作って、確かめる。',
  lede='調べる係、つくる係、確かめる係。AIのチームが分担して、できたファイルと「何を確かめたか」まで渡します。',
  cta1='自分のPCで始める', cta2='実際の記録を見る', facts=['オープンソース・MIT','あなたのPCで動く','外部へ勝手に送信しない'],
  ask_label='お願い', ask='このCSVを年月別に集計するツールを作って。使い方とテストも付けて。',
  roles=[('master','まとめ役','進め方と完了条件を決める'),('researcher','調べる係','資料と公開ページを読む'),('builder','つくる係','ファイルを作って直す'),('reviewer','確かめる係','条件を満たすか確かめる')],
  states={'idle':'出番待ち','thinking':'計画中','researching':'調査中','building':'作業中','reviewing':'確認中','done':'担当分は完了'},
  stage_note='動きを説明するためのアニメーションです。ここではAIは動いていません。', pause='動きを止める', play='動かす',
  shots_eyebrow='アプリの画面', shots_h='3ステップで、<wbr>迷わない。', shots_p='お願いする。チームを見る。できたものを見る。画面はこの3つだけです。',
  shots=[('ask','お願いする','やってほしいことを、いつもの言葉で書きます。資料を添えたり、予算の上限を決めたりもできます。'),('team','チームを見る','誰が何をしているかが、ひと目で分かります。途中で追加のお願いも渡せます。'),('results','できたものを見る','できたファイルを読み、確認の結果を見てから、使う版を選びます。')],
  shots_note='実際のアプリの画面です。2と3は、2026年9月14日にローカルのAI（Qwen 3.5 9B）で実行した記録を表示しています。',
  team_eyebrow='チーム', team_h='ひとりのAIに、<wbr>全部は任せない。', team_p='作った本人は、自分の間違いに気づきにくい。だから、作る係と確かめる係を分けました。',
  team_cards=[('master','#e8ebff','まとめ役','進め方を決める','お願いを、成果物と完了条件に分けます。必要な仲間だけに仕事を頼みます。'),('researcher','#dff6ed','調べる係','根拠を集める','渡した資料や公開ページを読み、出典つきでメモにします。'),('builder','#fff0cf','つくる係','ファイルにする','コード、文書、表。指摘を受けたら、その版を直して出し直します。'),('reviewer','#ffe7f0','確かめる係','通さないこともある','完了条件を一つずつ確かめます。確かめられなかったことは「未確認」と残します。')],
  get_eyebrow='受け取るもの', get_h='チャットの返事で、<wbr>終わらない。', get_p='手元に残るのは、使えるファイルです。',
  get_cards=[('ファイルで受け取る','コード、Markdown、CSV、HTML。まとめてZIPでも取得できます。'),('版の違いが見える','初稿と修正版の差分を見比べて、使う版を自分で選べます。'),('途中で口をはさめる','進んでいる途中でも、チャットから追加の指示を渡せます。'),('経緯がぜんぶ残る','誰が何を作り、何を確かめ、何が未確認か。後から追える記録になります。')],
  proof_eyebrow='実際の記録', proof_h='確かめる係は、<wbr>本当に差し戻す。', proof_p='2026年9月13日の実行記録から。3つの公開ページを比較する調査メモに、確かめる係が出した指摘です。',
  findings=[('F-1','根拠引用の欠落','比較表の「backend / frontend 構成」に、原文の引用がない。'),('F-2','関係性の未明示','あるリポジトリを「公式」とする根拠が、示されていない。'),('F-3','言い換え','提供形態を「CLI」と書いているが、原文にない語。')],
  diff_file='research.md r1 → research-final-r2.md', was='変更前 · r1（記録の原文）', now='変更後 · r2（記録の原文）',
  diffs=[('出典のない「backend / frontend 構成」という説明が、比較表に入っていた。','引用できる原文がないため、その説明を表から外した。再確認でpass。'),('「仕様ページ上部にリンクされている公式リポジトリ」と断定していた。','関係を確認できないことを明記し、参考情報として扱いを分けた。再確認でpass。'),('原文にない「CLI」という語で提供形態をまとめていた。','原文の表現に合わせて書き直した。再確認でpass。')],
  receipt=[('結果','partial（未完了）','partial'),('イベント','171',''),('モデル呼び出し','91',''),('費用','$6.07（定価換算）',''),('時間','23分51秒','')],
  proof_note='最終レビューが予算の上限で終わったため、この実行は「未完了」のままです。原文との照合も、レビュー環境から取得できず「未確認」と記録されています。', proof_link='記録の全文を見る',
  honest_eyebrow='正直な数字', honest_h='うまくいかなかった<wbr>記録も、消しません。', honest_p='同じ小型のローカルAIで、チームと一人を比べました（2026年9月18日、10課題・各1回）。',
  score_a=('コードを作る課題','隠しテストで採点・5課題'), score_b=('調べてまとめる課題','自動採点・5課題'), lbl_team='チーム', lbl_single='一人のAI',
  honest_cards=[('速さでは、負けます。','10課題の合計で、チームは164分、一人のAIは37分でした。'),('テストで確かめられる成果物では、正確でした。','コードの課題は5件とも正解。一人のAIは2件を落としました。'),('調べものは、まだ苦手です。','小型のAIでは5件とも不正解。時間切れと、確認の見逃しがありました。')],
  caveat='小さな試験で、差は偶然の範囲に入り得ます。品質の優位を一般に示すものではありません。', honest_link='試験の条件と全結果',
  priv_eyebrow='データの扱い', priv_h='あなたのPCで、動く。', priv_p='登録も、クラウドのアカウントも要りません。',
  priv=[('実行記録とファイルは、あなたのPCに保存します。',''),('ローカルのAI（Ollama）なら、入力は外へ出ません。',''),('クラウドのAIを選んだ場合は、入力がその接続先へ送られます。','どのAIを使うかは、設定で自分で決めます。'),('外部への投稿や送信は、しません。','作るのは草案までです。権限を広げる操作は、承認を求めます。')],
  conn_h='いつものAIに、つなぐだけ。', conn=[('Claude Code','キー不要'),('OpenAI互換API',''),('Ollama','ローカル')],
  start_eyebrow='始める', start_h='コマンドひとつで、<wbr>最初のお願いを。', start_p='Python環境の準備は要りません。uvが入っていれば、そのまま起動します。', copy='コピー', copied='コピーしました',
  steps=[('起動する','上のコマンドを実行すると、ブラウザで画面が開きます。'),('AIにつなぐ','Claude Code、API、Ollamaから選んで、疎通を確認します。'),('お願いする','やってほしいことを、いつもの言葉で書きます。')],
  start_note='利用料はかかりません。クラウドのAIを使う場合は、そのAIの利用料が別にかかります。', gh='GitHubで見る',
  faq_h='よくある質問', faq=[('ChatGPTやClaudeと、何が違いますか？','一人のAIが答えて終わりではなく、作る係と確かめる係が分かれています。受け取るのは返事ではなくファイルで、何を確かめたか、何が未確認かの記録も残ります。'),('必ず正しいものができますか？','いいえ。確かめる係が見逃すこともあります。だから、未完了や未確認をそのまま表示し、うまくいかなかった実行記録も公開しています。大事な成果物は、ご自身でも確認してください。'),('料金はかかりますか？','アプリは無料のオープンソース（MIT）です。クラウドのAIにつなぐ場合は、そのAIの利用料がかかります。一回ごとの予算上限を設定でき、達すると止まります。'),('データはどこへ送られますか？','実行記録とファイルは、あなたのPCに保存されます。ローカルのAIなら入力は外へ出ません。クラウドのAIを選んだ場合だけ、入力がその接続先へ送られます。'),('どんな仕事に向いていますか？','テストや条件で確かめられる成果物に向いています。小さなツール、データの変換、決まった形式の文書などです。小型のローカルAIでの調べものは、まだ安定していません。')],
  final_h='最初のお願いを、<wbr>してみよう。', final_p='チームは、あなたのPCで待っています。',
  biz_eyebrow='業務での利用', biz_h='自分の仕事に使えるか、相談する。', biz_p='対象の作業と合格条件を絞って、一緒に確かめます。顧客データでの有償PoC、本番SLA、SSO、組織分離は、提供済みとはしていません。',
  form=dict(name='お名前', email='返信先メール', org='会社・団体名（任意）', msg='相談したい内容', privacy='入力内容は運営者への非公開の問い合わせとしてGoogle Cloudに保存し、返信のために利用します。AIの入力やアクセス解析には利用しません。90日後から順次削除します。公開Issueには投稿されません。送信による契約や課金はありません。', consent='上記の取り扱いに同意して送信します。', send='相談を送信'),
  foot=[('https://github.com/FORIFOR/Multibot','GitHub'),('https://github.com/FORIFOR/Multibot/issues','不具合・提案'),(EV+'local-recompare-2026-09-18','評価と制約'),('https://reachmade.com/products/#agent-team','Reachmade')], foot_other='English'),
 'en': dict(lang='en', base='', self='https://forifor.github.io/Multibot/', other='ja/', other_lang='ja', other_label='日本語',
  title='Agent Team — Ask once. A team builds it, then checks it.',
  desc='An AI team splits the work: research, make, review. You get real files and a record of what was checked. Open source, runs on your computer.',
  skip='Skip to content', nav=[('#team','The team'),('#proof','A real record'),('#privacy','Your data'),('#faq','FAQ')], nav_cta='Get started',
  h1='Ask once. A team builds it,<br>then checks it.',
  lede='A researcher, a maker and a reviewer. An AI team splits the work and hands you the files, along with what was checked.',
  cta1='Run it on your computer', cta2='See a real record', facts=['Open source · MIT','Runs on your computer','Never sends anything out on its own'],
  ask_label='Request', ask='Build a tool that totals this CSV by month. Include usage notes and tests.',
  roles=[('master','Coordinator','Plans the work and the finish line'),('researcher','Researcher','Reads your files and public pages'),('builder','Maker','Writes the files and fixes them'),('reviewer','Reviewer','Checks each condition')],
  states={'idle':'On standby','thinking':'Planning','researching':'Researching','building':'Working','reviewing':'Reviewing','done':'Assigned work done'},
  stage_note='An animation that explains the flow. No AI is running on this page.', pause='Pause animation', play='Play',
  shots_eyebrow='The app', shots_h='Three steps. Nothing to learn.', shots_p='Ask. Watch the team. See the results. Those are the only three screens.',
  shots=[('ask','Ask','Write what you need in your own words. You can attach files and set a budget limit.'),('team','Watch the team','See at a glance who is doing what. You can hand over a new direction at any time.'),('results','See the results','Read the files, look at what was checked, then choose the version you will use.')],
  shots_note='These are real screens of the app. Steps 2 and 3 show a run recorded on 14 September 2026 with a local model (Qwen 3.5 9B).',
  team_eyebrow='The team', team_h='Don\'t leave it all to one AI.', team_p='Whoever wrote it is the last to notice its mistakes. So making and checking are separate jobs.',
  team_cards=[('master','#e8ebff','Coordinator','Plans the work','Turns your request into deliverables and finish conditions, and asks only the teammates it needs.'),('researcher','#dff6ed','Researcher','Gathers evidence','Reads your files and public pages, and writes notes with sources.'),('builder','#fff0cf','Maker','Turns it into files','Code, documents, tables. When a finding comes back, it fixes that version and publishes again.'),('reviewer','#ffe7f0','Reviewer','Sometimes says no','Checks each finish condition. Whatever could not be checked stays marked unverified.')],
  get_eyebrow='What you get', get_h='It doesn\'t end with a chat reply.', get_p='What stays with you is a file you can use.',
  get_cards=[('Real files','Code, Markdown, CSV, HTML. Download them together as a ZIP.'),('Visible revisions','Compare the first draft with the fix, and choose the version you will use.'),('Step in any time','Send a new direction from the chat while the work is under way.'),('The whole trail','Who made what, what was checked, what is still unverified. A record you can follow later.')],
  proof_eyebrow='A real record', proof_h='The reviewer really sends work back.', proof_p='From the run of 13 September 2026: findings the reviewer raised on a memo comparing three public pages.',
  findings=[('F-1','Missing evidence','The comparison table says "backend / frontend" with no quoted source.'),('F-2','Unstated link','A repository is called "official" without evidence of that link.'),('F-3','Paraphrase','The delivery form is called a "CLI"; the source never uses that word.')],
  diff_file='research.md r1 → research-final-r2.md', was='Before · r1 (as recorded)', now='After · r2 (as recorded)',
  diffs=[('The comparison table described a "backend / frontend" layout with no source.','No quotable source existed, so the description was removed. Re-checked: pass.'),('The memo asserted that a repository was "the official repo linked from the spec page".','The memo now says the link could not be confirmed, and treats it as reference only. Re-checked: pass.'),('The delivery form was summarised with the word "CLI", which the source does not use.','Rewritten to match the wording of the source. Re-checked: pass.')],
  receipt=[('Result','partial (not complete)','partial'),('Events','171',''),('Model calls','91',''),('Cost','$6.07 at list price',''),('Time','23m 51s','')],
  proof_note='The final review stopped at the budget limit, so this run stays "partial". Matching quotes against the original pages is recorded as "unverified", because the review environment could not fetch them.', proof_link='Open the full record',
  honest_eyebrow='Honest numbers', honest_h='We keep the records that went badly.', honest_p='The same small local model, as a team and alone (18 September 2026, 10 tasks, one run each).',
  score_a=('Coding tasks','graded by hidden tests · 5 tasks'), score_b=('Research-and-summarise tasks','auto-graded · 5 tasks'), lbl_team='Team', lbl_single='One AI',
  honest_cards=[('It is slower.','Across the 10 tasks the team took 164 minutes. One AI took 37.'),('It was more accurate where tests can check the work.','All five coding tasks were correct. One AI missed two.'),('Research is still a weak spot.','With a small model, all five were graded wrong: timeouts, and checks that missed gaps.')],
  caveat='A small test. The differences may be chance, and this is not a general claim of better quality.', honest_link='Conditions and full results',
  priv_eyebrow='Your data', priv_h='It runs on your computer.', priv_p='No sign-up. No cloud account.',
  priv=[('The work record and files are stored on your computer.',''),('With a local model (Ollama), your input never leaves.',''),('If you choose a cloud model, your input goes to that provider.','You decide which model to use in Settings.'),('Nothing is posted or sent externally.','It stops at drafts. Anything that widens permissions asks for your approval.')],
  conn_h='Connect the AI you already use.', conn=[('Claude Code','no key needed'),('OpenAI-compatible APIs',''),('Ollama','local')],
  start_eyebrow='Get started', start_h='One command to your first request.', start_p='No Python setup. If you have uv, it just starts.', copy='Copy', copied='Copied',
  steps=[('Start it','Run the command above. The app opens in your browser.'),('Connect a model','Pick Claude Code, an API or Ollama, and run the connection check.'),('Ask','Write what you need in your own words.')],
  start_note='The app is free. If you connect a cloud model, that provider bills you for usage.', gh='View on GitHub',
  faq_h='Questions', faq=[('How is this different from ChatGPT or Claude?','It is not one AI answering once. Making and checking are separate jobs. You receive files, not a reply, along with a record of what was checked and what is still unverified.'),('Will the result always be right?','No. The reviewer can miss things. That is why partial and unverified results are shown as they are, and why we publish the runs that went badly. Check important work yourself.'),('What does it cost?','The app is free and open source (MIT). A cloud model bills you for usage. You can set a budget limit per request, and work stops when it is reached.'),('Where does my data go?','The work record and files stay on your computer. With a local model your input never leaves. Only if you choose a cloud model does your input go to that provider.'),('What kind of work suits it?','Work that tests or conditions can check: small tools, data conversion, documents with a fixed format. Research with a small local model is not yet reliable.')],
  final_h='Make your first request.', final_p='The team is waiting on your computer.',
  biz_eyebrow='Using it at work', biz_h='Ask whether it fits your work.', biz_p='We narrow it to one task and its pass conditions, and check together. Paid pilots on customer data, production SLAs, SSO and organisation isolation are not offered as available.',
  form=dict(name='Name', email='Reply email', org='Organization (optional)', msg='What would you like to discuss?', privacy='Your inquiry is stored privately in Google Cloud for the operator to follow up. It is not used as AI input or analytics, and becomes eligible for deletion after 90 days. It is not posted to a public issue. Sending it creates no contract or charge.', consent='I agree to this handling of my inquiry.', send='Send inquiry'),
  foot=[('https://github.com/FORIFOR/Multibot','GitHub'),('https://github.com/FORIFOR/Multibot/issues','Issues'),(EV+'local-recompare-2026-09-18','Evaluation and limits'),('https://reachmade.com/products/#agent-team','Reachmade')], foot_other='日本語'),
}

import re as _re
_rec = (ROOT/'record.js').read_text(encoding='utf-8')
_pairs = [(b.replace("\\n","\n").replace("\\'","'"), a.replace("\\n","\n").replace("\\'","'")) for b,a in _re.findall(r"before: '((?:[^'\\]|\\.)*)',\s*\n\s*after: '((?:[^'\\]|\\.)*)'", _rec)]
assert len(_pairs) == 8, len(_pairs)   # 4 recorded blocks per language: F-3, F-1, F-2, comparison table
REAL = {'ja': [_pairs[1], _pairs[2], _pairs[0]], 'en': [_pairs[5], _pairs[6], _pairs[4]]}

def page(t):
    t = dict(t, diffs=REAL[t['lang']])
    e = html.escape; b = t['base']
    nav = ''.join(f'<a href="{h}">{e(l)}</a>' for h,l in t['nav'])
    mates = ''.join(f'<li class="mate" data-kind="{k}" data-n="{i+1}"><div class="floor">{bot(k)}</div><span class="who">{e(n)}</span><span class="pill" data-pill>{e(t["states"]["idle"])}</span></li>' for i,(k,n,_) in enumerate(t['roles']))
    team = ''.join(f'<article class="card role" data-reveal style="--tone:{tone}"><div class="floor">{bot(k,"idle")}</div><small>{e(role)}</small><h3>{e(h)}</h3><p>{e(p)}</p></article>' for k,tone,role,h,p in t['team_cards'])
    shot_tabs = ''.join(f'<button type="button" role="tab" id="shot-tab-{i}" aria-controls="shot-{i}" aria-selected="{"true" if i==0 else "false"}" data-shot="{i}"><b>{i+1}</b>{e(h)}</button>' for i,(k,h,p) in enumerate(t['shots']))
    shot_panels = ''.join(f'<div class="shot" role="tabpanel" id="shot-{i}" aria-labelledby="shot-tab-{i}" data-shot-panel="{i}"><figure><div class="frame"><img src="{b}media/app-{k}-{t["lang"]}.webp" width="1440" height="788" alt="{e(h)}" {"" if i==0 else "loading=\"lazy\" "}decoding="async"></div><figcaption><b>{i+1}. {e(h)}</b>{e(p)}</figcaption></figure></div>' for i,(k,h,p) in enumerate(t['shots']))
    get = ''.join(f'<article class="card" data-reveal><h3>{e(h)}</h3><p>{e(p)}</p></article>' for h,p in t['get_cards'])
    finds = ''.join(f'<button type="button" class="finding" data-finding="{i}" aria-pressed="{"true" if i==0 else "false"}"><span class="id">{fid}</span><b>{e(l)}</b><span class="t">{e(x)}</span></button>' for i,(fid,l,x) in enumerate(t['findings']))
    diffs = ''.join(f'<div data-diff="{i}"{"" if i==0 else " hidden"}><div class="was"><span class="lbl">{e(t["was"])}</span>{e(w).replace(chr(10),'<br>')}</div><div class="now" style="margin-top:14px"><span class="lbl">{e(t["now"])}</span>{e(n).replace(chr(10),'<br>')}</div></div>' for i,(w,n) in enumerate(t['diffs']))
    receipt = ''.join(f'<span class="{c}">{e(k)} <b>{e(v)}</b></span>' for k,v,c in t['receipt'])
    def score(title, team_v, single_v):
        return (f'<article class="card score" data-reveal><h3>{e(title[0])}<small>{e(title[1])}</small></h3>'
                f'<div class="bar" style="--v:{team_v*20}%"><span>{e(t["lbl_team"])}</span><i></i><b>{team_v}/5</b></div>'
                f'<div class="bar" style="--v:{single_v*20}%;--c:#9aa3b8"><span>{e(t["lbl_single"])}</span><i></i><b>{single_v}/5</b></div></article>')
    honest = ''.join(f'<article class="card" data-reveal><h3>{e(h)}</h3><p>{e(p)}</p></article>' for h,p in t['honest_cards'])
    priv = ''.join(f'<li{" class=\"note\"" if i==2 else ""}><div>{e(a)}{f"<small>{e(s)}</small>" if s else ""}</div></li>' for i,(a,s) in enumerate(t['priv']))
    conn = ''.join(f'<span>{e(n)}{f"<small>{e(s)}</small>" if s else ""}</span>' for n,s in t['conn'])
    steps = ''.join(f'<li><b>{e(h)}</b>{e(p)}</li>' for h,p in t['steps'])
    faq = ''.join(f'<details><summary>{e(q)}</summary><p>{e(a)}</p></details>' for q,a in t['faq'])
    crew = ''.join(bot(k,'done') for k,_,_ in t['roles'])
    f = t['form']
    foot = ''.join(f'<a href="{h}"{" data-track=\"github_outbound\" data-intent=\"repo\"" if "github.com/FORIFOR/Multibot\"" in h+"\"" and h.endswith("Multibot") else ""}>{e(l)}</a>' for h,l in t['foot'])
    states = html.escape(__import__('json').dumps(t['states'], ensure_ascii=False), quote=True)
    return f'''<!doctype html>
<html lang="{t['lang']}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(t['title'])}</title>
<meta name="description" content="{e(t['desc'])}">
<meta property="og:title" content="{e(t['title'])}">
<meta property="og:description" content="{e(t['desc'])}">
<meta property="og:image" content="https://forifor.github.io/Multibot/media/{"og-ja.png" if t["lang"]=="ja" else "og.png"}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:url" content="{t['self']}">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="{t['self']}">
<link rel="alternate" hreflang="{t['other_lang']}" href="https://forifor.github.io/Multibot/{'' if t['other_lang']=='en' else 'ja/'}">
<link rel="icon" type="image/svg+xml" href="{b}favicon.svg">
<link rel="stylesheet" href="{b}home.css">
</head>
<body>
<a class="skip" href="#main">{e(t['skip'])}</a>
<header class="top">
  <a class="brand" href="./">Agent Team<small>Multibot · MIT</small></a>
  <nav class="nav" aria-label="{'サイト内' if t['lang']=='ja' else 'Site'}">{nav}<a class="lang" href="{t['other']}" lang="{t['other_lang']}" hreflang="{t['other_lang']}">{e(t['other_label'])}</a><a class="btn" href="#start" data-track="quickstart_open">{e(t['nav_cta'])}</a></nav>
</header>
<main id="main">
<section class="hero sky"><div class="wrap">
  <h1>{t['h1']}</h1>
  <p class="lede">{e(t['lede'])}</p>
  <div class="cta"><a class="btn" href="#start" data-track="quickstart_open">{e(t['cta1'])}</a><a class="btn ghost" href="#proof">{e(t['cta2'])}</a></div>
  <p class="facts">{''.join(f'<span>{e(x)}</span>' for x in t['facts'])}</p>
  <div class="stage" id="stage" data-states="{states}">
    <p class="ask-line"><b>{e(t['ask_label'])}</b>{e(t['ask'])}</p>
    <ol class="mates">{mates}</ol>
    <div class="stage-foot"><span>{e(t['stage_note'])}</span><button type="button" id="stage-toggle" data-pause="{e(t['pause'])}" data-play="{e(t['play'])}" aria-pressed="false" hidden>{e(t['pause'])}</button></div>
  </div>
</div></section>

<section class="section" id="app"><div class="wrap">
  <div class="head" data-reveal><p class="eyebrow">{e(t['shots_eyebrow'])}</p><h2>{t['shots_h']}</h2><p class="lede">{e(t['shots_p'])}</p></div>
  <div class="shots" data-reveal><div class="shot-tabs" role="tablist" aria-label="{e(t['shots_eyebrow'])}">{shot_tabs}</div>{shot_panels}</div>
  <p class="caveat" data-reveal>{e(t['shots_note'])}</p>
</div></section>

<section class="section tint" id="team"><div class="wrap">
  <div class="head" data-reveal><p class="eyebrow">{e(t['team_eyebrow'])}</p><h2>{t['team_h']}</h2><p class="lede">{e(t['team_p'])}</p></div>
  <div class="grid g4">{team}</div>
</div></section>

<section class="section" id="files"><div class="wrap">
  <div class="head" data-reveal><p class="eyebrow">{e(t['get_eyebrow'])}</p><h2>{t['get_h']}</h2><p class="lede">{e(t['get_p'])}</p></div>
  <div class="grid g2">{get}</div>
</div></section>

<section class="section tint" id="proof"><div class="wrap">
  <div class="head" data-reveal><p class="eyebrow">{e(t['proof_eyebrow'])}</p><h2>{t['proof_h']}</h2><p class="lede">{e(t['proof_p'])}</p></div>
  <div class="proof" data-reveal><div class="findings">{finds}</div><div class="diff" aria-live="polite"><span class="file">{e(t['diff_file'])}</span>{diffs}</div></div>
  <p class="receipt" data-reveal>{receipt}</p>
  <p class="caveat" data-reveal>{e(t['proof_note'])} <a class="textlink" href="{EV}scenarios/research2" data-track="artifact_open">{e(t['proof_link'])}</a></p>
</div></section>

<section class="section" id="numbers"><div class="wrap">
  <div class="head" data-reveal><p class="eyebrow">{e(t['honest_eyebrow'])}</p><h2>{t['honest_h']}</h2><p class="lede">{e(t['honest_p'])}</p></div>
  <div class="grid g2" style="margin-bottom:16px">{score(t['score_a'],5,3)}{score(t['score_b'],0,3)}</div>
  <div class="grid g3">{honest}</div>
  <p class="caveat" data-reveal>{e(t['caveat'])} <a class="textlink" href="{EV}local-recompare-2026-09-18" data-track="artifact_open">{e(t['honest_link'])}</a></p>
</div></section>

<section class="section tint" id="privacy"><div class="wrap split">
  <div class="head" data-reveal><p class="eyebrow">{e(t['priv_eyebrow'])}</p><h2>{e(t['priv_h'])}</h2><p class="lede">{e(t['priv_p'])}</p></div>
  <ul class="checks" data-reveal>{priv}</ul>
</div></section>

<section class="section" id="start"><div class="wrap">
  <div class="head" data-reveal><p class="eyebrow">{e(t['start_eyebrow'])}</p><h2>{t['start_h']}</h2><p class="lede">{e(t['start_p'])}</p></div>
  <div class="term" id="github" data-reveal><code id="cmd">{e(CMD)}</code><button type="button" id="copy" data-copied="{e(t['copied'])}">{e(t['copy'])}</button></div>
  <ol class="steps3" data-reveal>{steps}</ol>
  <p class="caveat" data-reveal>{e(t['start_note'])}</p>
  <p class="conn" style="margin-top:40px" data-reveal aria-label="{e(t['conn_h'])}">{conn}</p>
  <p style="text-align:center;margin-top:28px" data-reveal><a class="btn ghost" href="https://github.com/FORIFOR/Multibot" data-track="github_outbound" data-intent="repo">{e(t['gh'])}</a></p>
</div></section>

<section class="section tint" id="faq"><div class="wrap">
  <div class="head" data-reveal><h2>{e(t['faq_h'])}</h2></div>
  <div class="faq" data-reveal>{faq}</div>
</div></section>

<section class="section final sky"><div class="wrap">
  <div class="crew" aria-hidden="true">{crew}</div>
  <h2 data-reveal>{t['final_h']}</h2><p class="lede" style="margin:18px auto 32px" data-reveal>{e(t['final_p'])}</p>
  <a class="btn" href="#start" data-track="quickstart_open">{e(t['cta1'])}</a>
</div></section>

<section class="section tint" id="consult"><div class="wrap contact">
  <div class="head" style="text-align:left;margin:0" data-reveal><p class="eyebrow">{e(t['biz_eyebrow'])}</p><h2 style="font-size:clamp(26px,3vw,38px)">{e(t['biz_h'])}</h2><p class="lede" style="margin-left:0">{e(t['biz_p'])}</p></div>
  <form id="portfolio-form" data-reveal><label>{e(f['name'])}<input name="name" required maxlength="80" autocomplete="name"></label><label>{e(f['email'])}<input name="email" type="email" required maxlength="254" autocomplete="email"></label><label>{e(f['org'])}<input name="organization" maxlength="120" autocomplete="organization"></label><label>{e(f['msg'])}<textarea name="message" required minlength="10" maxlength="2000"></textarea></label><label class="trap" aria-hidden="true">Website<input name="website" tabindex="-1" autocomplete="off"></label><p class="privacy">{e(f['privacy'])}</p><label class="consent"><input type="checkbox" name="consent" required>{e(f['consent'])}</label><button class="btn" type="submit">{e(f['send'])}</button><p id="portfolio-status" role="status" aria-live="polite"></p></form>
</div></section>
</main>
<footer class="wrap footer"><span>Agent Team / Multibot · MIT</span><div class="footer-links">{foot}<a href="{t['other']}" lang="{t['other_lang']}" hreflang="{t['other_lang']}">{e(t['foot_other'])}</a></div></footer>
<script src="{b}home.js"></script>
<script src="{b}portfolio.js" data-product="agent-team"></script>
</body>
</html>
'''
def build_bots_css():
    """The site uses the product's own characters. Copy their CSS instead of keeping a second, drifting version."""
    src = (ROOT.parent/'frontend/src/quiet-cinema.css').read_text(encoding='utf-8').splitlines()
    i = next(n for n,l in enumerate(src) if l.startswith('/* Role-aware bot characters'))
    j = next(n for n,l in enumerate(src) if n>i and l.startswith('@media(prefers-reduced-motion:reduce){.bot-character'))
    base = '\n'.join(l for l in src[i:j+1] if not l.startswith('.bot-agent'))
    polish = (ROOT.parent/'frontend/src/bot-polish.css').read_text(encoding='utf-8')
    site = (ROOT/'site/bots-site.css').read_text(encoding='utf-8')
    css = (ROOT/'home.css').read_text(encoding='utf-8')
    a, b = css.index('/* BOTS:BEGIN'), css.index('/* BOTS:END */')
    head = css[a:css.index('\n', a)+1]
    (ROOT/'home.css').write_text(css[:a] + head + base + '\n' + polish + site + css[b:], encoding='utf-8')
build_bots_css()
(ROOT/'index.html').write_text(page(T['en']), encoding='utf-8')
(ROOT/'ja'/'index.html').write_text(page(T['ja']), encoding='utf-8')
print('ok', len(page(T['en'])), len(page(T['ja'])))
