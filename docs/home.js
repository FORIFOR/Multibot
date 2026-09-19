/* Agent Team site. Everything here is presentation: no model is called and nothing is sent.
   The page reads fully without this script; it adds the explanatory stage loop, finding tabs, copy and reveal. */
(function () {
  'use strict';
  var doc = document, root = doc.documentElement;
  root.classList.add('js');
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Reveal once on scroll. Without IntersectionObserver everything simply stays visible.
  var items = [].slice.call(doc.querySelectorAll('[data-reveal], .bar'));
  if (reduce || !('IntersectionObserver' in window)) items.forEach(function (el) { el.classList.add('in'); });
  else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) { if (entry.isIntersecting) { entry.target.classList.add('in'); io.unobserve(entry.target); } });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 });
    items.forEach(function (el) { io.observe(el); });
  }

  // Stage: coordinator → researcher → maker → reviewer, then everyone done. An explanation, not a live run.
  var stage = doc.getElementById('stage');
  if (stage) {
    var labels = JSON.parse(stage.getAttribute('data-states'));
    var mates = [].slice.call(stage.querySelectorAll('.mate'));
    var working = { master: 'thinking', researcher: 'researching', builder: 'building', reviewer: 'reviewing' };
    var STATES = ['idle', 'thinking', 'researching', 'building', 'reviewing', 'done'];
    var setState = function (mate, state) {
      var bot = mate.querySelector('[data-bot]'), mark = bot.querySelector('.bot-state-mark'), face = bot.querySelector('.bot-face');
      STATES.forEach(function (s) { bot.classList.remove('bot-' + s); });
      bot.classList.add('bot-' + state);
      var active = state !== 'idle' && state !== 'done';
      face.className = 'bot-face face-' + (state === 'done' ? 'happy' : state === 'thinking' || state === 'reviewing' ? 'focus' : 'normal');
      mark.className = 'bot-state-mark' + (active ? ' is-working' : '');
      mark.innerHTML = active ? '<i></i><i></i><i></i>' : state === 'done' ? '✓' : '';
      mate.classList.toggle('on', active); mate.classList.toggle('ok', state === 'done');
      mate.querySelector('[data-pill]').textContent = labels[state];
    };
    var frame = function (step) {
      mates.forEach(function (mate, i) {
        var kind = mate.getAttribute('data-kind');
        setState(mate, step >= mates.length ? 'done' : i < step ? 'done' : i === step ? working[kind] : 'idle');
      });
    };
    if (reduce) frame(mates.length);
    else {
      var step = 0, timer = null, toggle = doc.getElementById('stage-toggle');
      // Steps 0–3 light one teammate each; 4 and 5 hold everyone on "done" before the loop restarts.
      var tick = function () { frame(step); step = (step + 1) % (mates.length + 2); };
      var start = function () { if (!timer) { tick(); timer = setInterval(tick, 2200); } };
      var stop = function () { clearInterval(timer); timer = null; };
      toggle.hidden = false;
      toggle.addEventListener('click', function () {
        var paused = toggle.getAttribute('aria-pressed') !== 'true';
        toggle.setAttribute('aria-pressed', String(paused));
        toggle.textContent = toggle.getAttribute(paused ? 'data-play' : 'data-pause');
        stage.classList.toggle('paused', paused);
        if (paused) stop(); else start();
      });
      doc.addEventListener('visibilitychange', function () { if (doc.hidden) stop(); else if (toggle.getAttribute('aria-pressed') !== 'true') start(); });
      start();
    }
  }

  // Real app screens: three tabs with arrow-key support. Without this script the three figures simply stack.
  var tabs = [].slice.call(doc.querySelectorAll('[data-shot]')), panels = [].slice.call(doc.querySelectorAll('[data-shot-panel]'));
  var showShot = function (n, focus) {
    tabs.forEach(function (t, i) { t.setAttribute('aria-selected', String(i === n)); t.tabIndex = i === n ? 0 : -1; if (i === n && focus) t.focus(); });
    panels.forEach(function (p, i) { p.hidden = i !== n; });
  };
  tabs.forEach(function (tab, i) {
    tab.addEventListener('click', function () { showShot(i, false); });
    tab.addEventListener('keydown', function (ev) {
      var next = ev.key === 'ArrowRight' ? (i + 1) % tabs.length : ev.key === 'ArrowLeft' ? (i + tabs.length - 1) % tabs.length : -1;
      if (next >= 0) { ev.preventDefault(); showShot(next, true); }
    });
  });
  if (tabs.length) showShot(0, false);

  // Findings: one real finding at a time, with its before/after.
  var findings = [].slice.call(doc.querySelectorAll('[data-finding]'));
  findings.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var id = btn.getAttribute('data-finding');
      findings.forEach(function (b) { b.setAttribute('aria-pressed', String(b === btn)); });
      [].forEach.call(doc.querySelectorAll('[data-diff]'), function (d) { d.hidden = d.getAttribute('data-diff') !== id; });
    });
  });

  // Copy the start command.
  var copy = doc.getElementById('copy');
  if (copy && navigator.clipboard) {
    copy.addEventListener('click', function () {
      var label = copy.textContent;
      navigator.clipboard.writeText(doc.getElementById('cmd').textContent).then(function () {
        copy.textContent = copy.getAttribute('data-copied');
        setTimeout(function () { copy.textContent = label; }, 1800);
      });
    });
  } else if (copy) copy.hidden = true;
})();
