/* Agent Team site — the "work record" hero. Real data from docs/evidence/scenarios/research2 (run_1a09777700a7d829c4a,
   claude-opus-5 via claude_cli, 2026-09-12T21:13Z–21:36Z). No LLM is called here; this only renders recorded text. */
(function () {
  'use strict';
  var EV = 'https://github.com/FORIFOR/Multibot/blob/main/docs/evidence/scenarios/research2/';
  var I18N = {
    ja: {
      artifact: '成果物', record: '進行記録', before: '変更前 r1', after: '変更後 r2', open: '全文を開く', jump: '該当箇所へ',
      hint: '指摘をクリックすると、成果物の変更箇所へ移動します。', more: '省略', file: 'ファイル',
      steps: [
        { k: 'request', t: '21:13Z', who: 'あなた', title: '依頼', body: '3つの公開ページを取得し「主張・対象読者・ライセンス」を出典URL付きで比較する調査メモ。取得できないページは「取得不可」と書き、推測で埋めない。' },
        { k: 'draft', t: '21:16Z', who: 'researcher', title: '初稿', body: 'research.md r1 を公開（sha256 e3420149…）。3ページを web_fetch で取得。deer-flow は後半が切り詰め。', link: 'research.md.r1' },
        { k: 'review', t: '21:19Z', who: 'reviewer', title: 'レビューの指摘', body: '受入条件 5 件: pass 3 / unverified 2（レビュー環境にネットワークがなく原文再取得は不可）。指摘 3 件を researcher に送信。', link: 'review.md.r1',
          findings: [
            { id: 'F-1', label: '根拠引用の欠落', body: '比較表の deer-flow「（backend / frontend 構成）」に原文引用がない。', fix: 'f1' },
            { id: 'F-2', label: '関係性の未明示', body: 'agentskills/agentskills を「仕様ページ上部にリンクされている公式リポジトリ」とする根拠がない。', fix: 'f2' },
            { id: 'F-3', label: '言い換え', body: 'deepagents の提供形態「CLI」は原文にない語。', fix: 'f3' }
          ] },
        { k: 'fix', t: '21:29Z', who: 'researcher', title: '修正箇所', body: 'research-final-r2.md r1 を公開（sha256 fbc33429…）。F-1〜F-3 を反映し、2ページを再取得して引用を追加。', link: 'research-final-r2.md.r1' },
        { k: 'verify', t: '21:36Z', who: 'reviewer', title: '再検証', body: 'read_artifact のみで全文対照。', link: 'review-final.md.r1',
          verdicts: [['F-1〜F-3 の反映', 'pass'], ['出典URL＋原文引用', 'pass'], ['推測の混入なし', 'pass'], ['原文逐一照合', 'unverified']],
          note: 'この直後にレビュー・セッションが予算上限（$1.5）に達し、実行全体は partial で終了。' }
      ],
      artifactHead: { name: 'research-final-r2.md', rev: 'r1', sha: 'fbc33429ea6f…', by: 'researcher · t3b · 21:29Z', full: 'research-final-r2.md.r1' },
      blocks: [
        { h: '2-1. langchain-ai/deepagents — 対象読者（補足）', fix: 'f3', tag: 'F-3',
          before: '補足: ターミナル向けの既製コーディングエージェントにも言及があり、ライブラリ利用者以外も想定されている。',
          after: '根拠引用（2026-09-12T21:27:36Z の再取得で確認）: "Deep Agents Code — a pre-built coding agent in your terminal, similar to Claude Code or Cursor, powered by any LLM."\n注記（F-3 対応）: 原文は "a pre-built coding agent in your terminal" であり、「CLI」という語は原文には現れない。本書では原文表現に沿って記述する。' },
        { h: '2-2. bytedance/deer-flow — ライセンス', fix: 'f1', tag: 'F-1',
          before: '（比較表に「backend / frontend 構成」と記載。2-2 に対応する原文引用なし）',
          after: '未確認（F-1 対応）: 旧版 r1 の比較表にあった「backend / frontend 構成」という記述は、取得できた範囲の原文に対応する根拠引用が無く、未確認である。当該記述は比較表から削除し、推測による補完も行わない。' },
        { h: '2-3. agentskills.io/specification — ライセンス', fix: 'f2', tag: 'F-2',
          before: '参考（ページ上部にリンクされている公式リポジトリ https://github.com/agentskills/agentskills の記載）: "Apache-2.0 license" …',
          after: 'リンク実在の根拠（F-2 対応 / 21:27:35Z の再取得で確認）: 仕様ページのヘッダ部に、リポジトリ名そのものをラベルとするリンク表記が 2 箇所現れる。原文引用: "… ⌘ I / agentskills/agentskills / agentskills/agentskills"\n限定事項: 取得できたのは抽出テキストのみで href 属性は含まれない。そのリンク先が https://github.com/agentskills/agentskills であること自体は本取得からは確認できていない。' },
        { h: '3. 比較表 — 提供形態', fix: 'f13', tag: 'F-1 · F-3', table: true,
          before: 'deepagents: Python ライブラリ（uv add deepagents）＋ JS/TS 版＋ CLI（Deep Agents Code）\ndeer-flow: クローンして make setup → Docker もしくはローカル実行のアプリケーション（backend / frontend 構成）',
          after: 'deepagents: Python ライブラリ（uv add deepagents）＋ JS/TS 版（"available as a JavaScript/TypeScript library"）＋ ターミナル上の既製コーディングエージェント（Deep Agents Code / 原文 "a pre-built coding agent in your terminal"）\ndeer-flow: クローンして make setup → Docker もしくはローカル実行のアプリケーション（内部構成については根拠引用を確認できておらず未確認のため記載しない）' }
      ]
    },
    en: {
      artifact: 'Deliverable', record: 'Work record', before: 'Before · r1', after: 'After · r2', open: 'Open full file', jump: 'Jump to change',
      hint: 'Click a finding to jump to the changed part of the deliverable.', more: 'omitted', file: 'file',
      steps: [
        { k: 'request', t: '21:13Z', who: 'you', title: 'Request', body: 'Fetch three public pages and compare their claims, audience and licence in a memo with source URLs. Mark unreachable pages as such; never fill gaps by guessing.' },
        { k: 'draft', t: '21:16Z', who: 'researcher', title: 'First draft', body: 'Published research.md r1 (sha256 e3420149…). All three pages fetched; deer-flow truncated.', link: 'research.md.r1' },
        { k: 'review', t: '21:19Z', who: 'reviewer', title: 'Review findings', body: '5 acceptance criteria: 3 pass, 2 unverified (the review sandbox has no network, so sources could not be re-fetched). Three findings sent to the researcher as a real message.', link: 'review.md.r1',
          findings: [
            { id: 'F-1', label: 'Missing evidence', body: 'The comparison table says deer-flow has a "backend / frontend" layout with no quoted source.', fix: 'f1' },
            { id: 'F-2', label: 'Unstated link', body: 'agentskills/agentskills is called "the official repo linked from the spec page" without evidence of that link.', fix: 'f2' },
            { id: 'F-3', label: 'Paraphrase', body: 'deepagents\' delivery form is called a "CLI"; the source never uses that word.', fix: 'f3' }
          ] },
        { k: 'fix', t: '21:29Z', who: 'researcher', title: 'Changes', body: 'Published research-final-r2.md r1 (sha256 fbc33429…). F-1 to F-3 applied; two pages re-fetched for new quotes.', link: 'research-final-r2.md.r1' },
        { k: 'verify', t: '21:36Z', who: 'reviewer', title: 'Re-verification', body: 'Full-text comparison with read_artifact only.', link: 'review-final.md.r1',
          verdicts: [['F-1 to F-3 applied', 'pass'], ['URL + quote for every claim', 'pass'], ['No guessed content', 'pass'], ['Line-by-line source check', 'unverified']],
          note: 'Right after this the review session hit its budget cap ($1.5), so the run ended partial.' }
      ],
      artifactHead: { name: 'research-final-r2.md', rev: 'r1', sha: 'fbc33429ea6f…', by: 'researcher · t3b · 21:29Z', full: 'research-final-r2.md.r1' },
      blocks: [
        { h: '2-1. langchain-ai/deepagents — audience (note)', fix: 'f3', tag: 'F-3',
          before: 'Note: the page also mentions a ready-made coding agent for the terminal, so non-library users are in scope.',
          after: 'Quote (re-fetched 2026-09-12T21:27:36Z): "Deep Agents Code — a pre-built coding agent in your terminal, similar to Claude Code or Cursor, powered by any LLM."\nNote (F-3): the source says "a pre-built coding agent in your terminal"; the word "CLI" does not appear. This memo follows the source wording.' },
        { h: '2-2. bytedance/deer-flow — licence', fix: 'f1', tag: 'F-1',
          before: '(The comparison table stated a "backend / frontend" layout; section 2-2 had no quote supporting it.)',
          after: 'Unverified (F-1): the "backend / frontend layout" in the r1 table has no supporting quote in the fetched text. The statement is removed from the table and not replaced by a guess.' },
        { h: '2-3. agentskills.io/specification — licence', fix: 'f2', tag: 'F-2',
          before: 'Reference (the official repository linked at the top of the page, https://github.com/agentskills/agentskills): "Apache-2.0 license" …',
          after: 'Evidence the link exists (F-2, re-fetched 21:27:35Z): the page header shows a link labelled with the repository name twice. Quote: "… ⌘ I / agentskills/agentskills / agentskills/agentskills"\nLimitation: only extracted text was fetched, without href attributes, so it is not confirmed that the link targets https://github.com/agentskills/agentskills.' },
        { h: '3. Comparison table — delivery form', fix: 'f13', tag: 'F-1 · F-3', table: true,
          before: 'deepagents: Python library (uv add deepagents) + JS/TS + CLI (Deep Agents Code)\ndeer-flow: clone, make setup → Docker or local app (backend / frontend layout)',
          after: 'deepagents: Python library (uv add deepagents) + JS/TS ("available as a JavaScript/TypeScript library") + a pre-built coding agent in your terminal (Deep Agents Code, quoted)\ndeer-flow: clone, make setup → Docker or local app (internal layout unverified: no supporting quote, so not stated)' }
      ]
    }
  };
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function nl(s) { return esc(s).replace(/\n/g, '<br>'); }
  window.track = window.track || function (name, props) {
    if(window.productEvent) window.productEvent(name);
  };
  var TARGET = { f1: ['f1', 'f13'], f2: ['f2'], f3: ['f3', 'f13'] };
  function render(root) {
    var lang = root.getAttribute('data-lang') || 'ja', d = I18N[lang] || I18N.ja, layout = root.getAttribute('data-layout') || 'a';
    root.className = 'record layout-' + layout;
    var art = '<div class="pane art"><div class="pane-h"><span class="lbl">' + d.artifact + '</span><span class="mono">' + esc(d.artifactHead.name) + ' · ' + d.artifactHead.rev + ' · ' + esc(d.artifactHead.sha) + '</span><span class="who">' + esc(d.artifactHead.by) + '</span><a class="open" data-track="artifact_open" href="' + EV + d.artifactHead.full + '">' + d.open + ' ↗</a></div><div class="pane-b">';
    d.blocks.forEach(function (b) {
      art += '<section class="blk" data-fix="' + b.fix + '"><h4>' + esc(b.h) + ' <span class="ftag">' + esc(b.tag) + '</span></h4>' +
        '<div class="diff"><div class="was"><span class="dl">' + d.before + '</span><p>' + nl(b.before) + '</p></div><div class="now"><span class="dl">' + d.after + '</span><p>' + nl(b.after) + '</p></div></div></section>';
    });
    art += '</div></div>';
    var rec = '<div class="pane rec"><div class="pane-h"><span class="lbl">' + d.record + '</span><span class="hint">' + d.hint + '</span></div><ol class="steps">';
    d.steps.forEach(function (s, i) {
      rec += '<li class="st st-' + s.k + '"><div class="st-h"><span class="n">' + (i + 1) + '</span><b>' + esc(s.title) + '</b><span class="mono t">' + s.t + ' · ' + esc(s.who) + '</span></div><p>' + esc(s.body) + (s.link ? ' <a data-track="artifact_open" href="' + EV + s.link + '">' + d.file + ' ↗</a>' : '') + '</p>';
      if (s.findings) { rec += '<div class="findings">' + s.findings.map(function (f) { return '<button type="button" class="finding" data-fix="' + f.fix + '" data-id="' + f.id + '"><span class="fid">' + f.id + '</span><span class="fl">' + esc(f.label) + '</span><span class="fb">' + esc(f.body) + '</span><span class="go">' + d.jump + ' →</span></button>'; }).join('') + '</div>'; }
      if (s.verdicts) { rec += '<ul class="verdicts">' + s.verdicts.map(function (v) { return '<li class="v-' + v[1] + '"><span>' + esc(v[0]) + '</span><em>' + v[1] + '</em></li>'; }).join('') + '</ul><p class="note">' + esc(s.note) + '</p>'; }
      rec += '</li>';
    });
    rec += '</ol></div>';
    root.innerHTML = art + rec;
    var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var seen = {}; var started = false;
    root.querySelectorAll('.finding').forEach(function (btn) {
      btn.addEventListener('click', function () {
        if (!started) { started = true; window.track('demo_start'); }
        var fix = btn.getAttribute('data-fix'), ids = TARGET[fix] || [fix];
        root.querySelectorAll('.blk').forEach(function (b) { b.classList.remove('hit', 'hit2'); });
        root.querySelectorAll('.finding').forEach(function (b) { b.classList.remove('on'); });
        btn.classList.add('on');
        var first = null;
        ids.forEach(function (id, i) { var b = root.querySelector('.blk[data-fix="' + id + '"]'); if (b) { b.classList.add(i ? 'hit2' : 'hit'); if (!first) first = b; } });
        if (first) {
          var body = root.querySelector('.art .pane-b'), beh = reduce ? 'auto' : 'smooth';
          if (body.scrollHeight > body.clientHeight) {
            var top = first.getBoundingClientRect().top - body.getBoundingClientRect().top + body.scrollTop - 8;
            body.scrollTo({ top: top, behavior: beh });
            var pr = body.parentNode.getBoundingClientRect();
            if (pr.top < 0 || pr.bottom > window.innerHeight) body.parentNode.scrollIntoView({ behavior: beh, block: 'nearest' });
          } else first.scrollIntoView({ behavior: beh, block: 'center' });
          if (!reduce) { first.classList.remove('pulse'); void first.offsetWidth; first.classList.add('pulse'); }
        }
        seen[fix] = 1; window.track('record_finding', { id: btn.getAttribute('data-id') });
        if (Object.keys(seen).length === 3 && !seen._done) { seen._done = 1; window.track('demo_complete', { kind: 'record' }); }
      });
    });
    root.querySelectorAll('a[data-track]').forEach(function (a) { a.addEventListener('click', function () { window.track(a.getAttribute('data-track'), { href: a.href }); }); });
  }
  document.querySelectorAll('[data-record]').forEach(render);
})();
