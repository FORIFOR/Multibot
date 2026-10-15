"""Build both public pages from reviewed copy and preserved execution evidence.

Run: python3 docs/site/build_site.py. No network, model or generated business data.
The revision explorer extracts exact text from retained artifacts, in both locales.
"""
import hashlib
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COPY = json.loads((ROOT / 'site/copy.json').read_text())
RECORD = ROOT / 'evidence/scenarios/research2'
SOURCE_BEFORE = RECORD / 'research.md.r1'
SOURCE_AFTER = RECORD / 'research-final-r2.md.r1'
CMD = 'uvx --from "git+https://github.com/FORIFOR/Multibot#subdirectory=backend" agentteam quickstart'
GH = 'https://github.com/FORIFOR/Multibot'
EV = GH + '/blob/main/docs/evidence/scenarios/research2/'
esc = html.escape


def source_line(path, prefix):
    matches = [line for line in path.read_text().splitlines() if line.startswith(prefix)]
    if len(matches) != 1:
        raise ValueError(f'Expected one source line in {path.name}: {prefix}')
    return matches[0]


def excerpts():
    old = source_line(SOURCE_BEFORE, '| 提供形態 |').split('|')
    new = source_line(SOURCE_AFTER, '| 提供形態 |').split('|')
    return [
        (old[3].strip(), new[3].strip()),
        (source_line(SOURCE_BEFORE, '  - 参考（').strip().removeprefix('- '),
         source_line(SOURCE_AFTER, '    - 限定事項:').strip().removeprefix('- ')),
        (old[2].strip(), new[2].strip()),
    ]


def bot(kind):
    svg = (ROOT.parent / f'frontend/src/assets/bots/{kind}.svg').read_text().strip()
    return svg.replace('<svg ', '<svg class="bot-art" aria-hidden="true" focusable="false" ', 1)


def inline_source(text):
    """Format only inline code/emphasis; source text and files remain unchanged."""
    parts = re.split(r"(`[^`]+`|\*\*[^*]+\*\*)", text)
    return ''.join(
        f'<code>{esc(part[1:-1])}</code>' if part.startswith('`') and part.endswith('`')
        else f'<strong>{esc(part[2:-2])}</strong>' if part.startswith('**') and part.endswith('**')
        else esc(part) for part in parts)


def heading(text):
    return '<br>'.join(esc(part) for part in text.split('\n'))


def page(t):
    b, lang = t['base'], t['lang']
    nav = ''.join(f'<a href="{href}">{esc(label)}</a>' for href, label in t['nav'])
    paths = ['master', 'researcher', 'builder', 'reviewer']
    crew = ''.join(f'<div class="crew-role">{bot(kind)}<span>{esc(label)}</span></div>'
                   for kind, label in zip(paths, t['roles_short']))
    finding_buttons = ''.join(
        f'<button type="button" class="finding" data-finding="{i}" aria-pressed="{str(i == 0).lower()}" aria-controls="change-{i}">'
        f'<span class="finding-id">{fid}</span><span><strong>{esc(label)}</strong><small>{esc(detail)}</small></span>'
        '<span class="finding-arrow" aria-hidden="true">↗</span></button>'
        for i, (fid, label, detail) in enumerate(t['findings']))
    panels = []
    for i, (before, after) in enumerate(excerpts()):
        sides = []
        for label, text, path, kind in [(t['before'], before, SOURCE_BEFORE, 'before'), (t['after'], after, SOURCE_AFTER, 'after')]:
            sha = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
            sides.append(f'<section class="revision revision-{kind}"><div class="revision-label">'
                         f'<span>{esc(label)}</span><span class="mono">{sha}</span></div>'
                         f'<blockquote lang="ja">{inline_source(text)}</blockquote>'
                         f'<a class="source-link" href="{EV}{path.name}">{esc(t["source"])} <span aria-hidden="true">↗</span></a></section>')
        panels.append(f'<article class="change" id="change-{i}" data-diff="{i}" aria-label="F-{i+1}">'
                      f'<div class="change-head"><span class="mono">F-{i+1}</span><span>{esc(t["excerpt"])}</span></div>'
                      + (f'<p class="change-summary">{esc(t["change_summaries"][i])}</p>' if lang == 'en' else '')
                      + ''.join(sides) + '</article>')
    team = ''.join(f'<article class="teammate"><div class="teammate-mark">{bot(kind)}<span class="mono">0{i+1}</span></div>'
                   f'<p class="role-label">{esc(role)}</p><h3>{esc(h)}</h3><p>{esc(p)}</p></article>'
                   for i, (kind, _, role, h, p) in enumerate(t['team_cards']))
    steps = ''.join(f'<li><span class="step-no">0{i+1}</span><div><h3>{esc(h)}</h3><p>{esc(p)}</p></div></li>'
                    for i, (h, p) in enumerate(t['app_steps']))
    setup_steps = ''.join(f'<li><strong>{esc(h)}</strong><span>{esc(p)}</span></li>' for h, p in t['steps'])
    faq = ''.join(f'<details><summary>{esc(q)}<span aria-hidden="true">+</span></summary><p>{esc(a)}</p></details>' for q, a in t['faq'])
    f = t['form']
    # Real-browser exports are required; never silently publish a historical theme.
    screen = f'award-request-{lang}.png'
    mobile_screen = f'award-request-mobile-{lang}.png'
    for name, dimensions in [(screen, (1440, 900)), (mobile_screen, (390, 844))]:
        image = (ROOT / 'media' / name).read_bytes()
        actual = tuple(int.from_bytes(image[i:i+4], 'big') for i in (16, 20))
        if image[:8] != b'\x89PNG\r\n\x1a\n' or actual != dimensions:
            raise ValueError(f'Unexpected real capture dimensions: {name}')
    return f'''<!doctype html>
<html lang="{lang}">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(t['title'])}</title><meta name="description" content="{esc(t['desc'])}">
<meta property="og:title" content="{esc(t['title'])}"><meta property="og:description" content="{esc(t['desc'])}">
<meta property="og:image" content="https://forifor.github.io/Multibot/media/{'og-ja.png' if lang == 'ja' else 'og.png'}">
<meta property="og:url" content="{t['self']}"><meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="{t['self']}"><link rel="alternate" hreflang="{t['other_lang']}" href="https://forifor.github.io/Multibot/{'' if t['other_lang'] == 'en' else 'ja/'}">
<link rel="icon" type="image/svg+xml" href="{b}favicon.svg"><link rel="stylesheet" href="{b}home.css">
</head>
<body>
<a class="skip" href="#main">{esc(t['skip'])}</a>
<header class="top wrap"><a class="brand" href="./"><img src="{b}favicon.svg" width="32" height="32" alt=""><span>Agent Team<small>Multibot / Open source</small></span></a>
<nav class="nav" aria-label="{'サイト内' if lang == 'ja' else 'Site'}">{nav}<a class="language" href="{t['other']}" lang="{t['other_lang']}" hreflang="{t['other_lang']}">{esc(t['other_label'])}</a><a class="nav-github" href="{GH}">GitHub <span aria-hidden="true">↗</span></a></nav></header>
<main id="main" tabindex="-1">
<section class="hero wrap">
<div class="hero-copy"><p class="eyebrow"><span class="rule"></span>{esc(t['eyebrow'])}</p>
<h1>{''.join(f'<span>{esc(line)}</span>' for line in t['h1'])}</h1>
<p class="lede">{esc(t['lede'])}</p>
<div class="cta"><a class="btn" href="#proof">{esc(t['cta1'])}<span aria-hidden="true">↓</span></a><a class="textlink" href="#start" data-track="quickstart_open">{esc(t['cta2'])}<span aria-hidden="true">↗</span></a></div>
<p class="availability">{esc(t['availability'])}</p></div>
<figure class="hero-team"><div class="crew">{crew}</div><figcaption><strong>{esc(t['hero_caption'])}</strong><span>{esc(t['hero_note'])}</span></figcaption><span class="hero-index" aria-hidden="true">MAKE / CHECK / CHOOSE</span></figure>
<div class="hero-footer"><span>OPEN SOURCE · MIT</span><span>FILES + REVIEWS + HISTORY</span><span aria-hidden="true">↓</span></div>
</section>
<section class="section evidence" id="proof"><div class="wrap">
<div class="section-heading"><p class="eyebrow">{esc(t['proof_eyebrow'])}</p><h2>{heading(t['proof_h'])}</h2><p class="lede">{esc(t['proof_p'])}</p></div>
<div class="record"><div class="record-bar"><span>{esc(t['record_label'])}</span><strong class="status">{esc(t['record_status'])}</strong></div>
<div class="record-grid"><div class="findings" role="group" aria-label="{esc(t['proof_eyebrow'])}">{finding_buttons}<a class="review-link" href="{EV}review-final.md.r1">{esc(t['review'])} ↗</a></div><div class="changes">{''.join(panels)}</div></div>
<div class="record-note"><span aria-hidden="true">※</span><div><p>{esc(t['record_limit'])}</p><small>{esc(t['record_model'])}</small></div></div></div>
</div></section>
<section class="section workspace" id="app"><div class="wrap">
<div class="section-heading"><p class="eyebrow">{esc(t['app_eyebrow'])}</p><h2>{heading(t['app_h'])}</h2><p class="lede">{esc(t['app_p'])}</p></div>
<figure class="app-screen"><div class="screen-title"><span>Agent Team</span><span>{esc(t['app_eyebrow'].split('/ ')[-1])}</span></div><picture><source media="(max-width: 760px)" srcset="{b}media/{mobile_screen}" width="390" height="844"><img src="{b}media/{screen}" width="1440" height="900" loading="lazy" decoding="async" alt="{esc(t['app_caption'])}"></picture><figcaption>{esc(t['app_caption'])}<a class="screen-full screen-desktop" href="{b}media/{screen}" target="_blank" rel="noopener">{esc(t['view_full'])} ↗</a><a class="screen-full screen-mobile" href="{b}media/{mobile_screen}" target="_blank" rel="noopener">{esc(t['view_full'])} ↗</a></figcaption></figure>
<ol class="work-steps">{steps}</ol>
</div></section>
<section class="section team-section" id="team"><div class="wrap">
<div class="section-heading compact"><p class="eyebrow">{esc(t['team_eyebrow'])}</p><h2>{heading(t['team_h'])}</h2><p class="lede">{esc(t['team_p'])}</p></div><div class="team">{team}</div>
</div></section>
<section class="section start" id="start"><div class="wrap start-grid"><div class="section-heading"><p class="eyebrow">{esc(t['start_eyebrow'])}</p><h2>{heading(t['start_h'])}</h2><p class="lede">{esc(t['start_p'])}</p><a class="textlink" href="{GH}#quick-start" data-track="quickstart_open">README ↗</a></div>
<div class="setup"><p class="command-label">{esc(t['command_label'])}</p><div class="command"><code id="cmd">{esc(CMD)}</code><button id="copy" type="button" hidden data-copied="{esc(t['copied'])}" data-failed="{esc(t['copy_failed'])}">{esc(t['copy'])}</button></div><p id="copy-status" class="copy-status" role="status" aria-live="polite"></p>
<p class="needs"><strong>{esc(t['needs_label'])}</strong>{t['needs']}</p><ol class="setup-steps">{setup_steps}</ol><p class="small">{esc(t['start_note'])}</p></div>
<div class="data-note" id="privacy"><h3>{esc(t['data_h'])}</h3><p>{esc(t['data_p'])}</p></div></div></section>
<section class="section faq-section" id="faq"><div class="wrap faq-grid"><div><p class="eyebrow">FAQ</p><h2>{esc(t['faq_h'])}</h2></div><div class="faq">{faq}</div></div></section>
<section class="section contact-section" id="consult"><div class="wrap contact-grid"><div class="section-heading"><p class="eyebrow">{esc(t['biz_eyebrow'])}</p><h2>{esc(t['biz_h'])}</h2><p class="lede">{esc(t['biz_p'])}</p><p class="launch-boundary">{esc(t['boundary'])}<a href="{GH}/blob/codex/public-service/docs/PUBLIC_SERVICE.md">{esc(t['plan_label'])} ↗</a></p></div>
<form id="portfolio-form"><noscript><p>{esc(t['form_no_js'])}</p></noscript><fieldset disabled><legend class="sr-only">{esc(t['biz_h'])}</legend><div class="form-pair"><label>{esc(f['name'])}<input name="name" required maxlength="80" autocomplete="name"></label><label>{esc(f['email'])}<input name="email" type="email" required maxlength="254" autocomplete="email"></label></div><label>{esc(f['org'])}<input name="organization" maxlength="120" autocomplete="organization"></label><label>{esc(f['msg'])}<textarea name="message" required minlength="10" maxlength="2000"></textarea></label><label class="trap" aria-hidden="true">Website<input name="website" tabindex="-1" autocomplete="off"></label><p class="small">{esc(f['privacy'])}</p><label class="consent"><input type="checkbox" name="consent" required><span>{esc(f['consent'])}</span></label><button class="btn" type="submit">{esc(f['send'])} <span aria-hidden="true">↗</span></button></fieldset><p id="portfolio-status" role="status" aria-live="polite"></p></form>
</div></section>
</main>
<footer class="wrap footer"><a class="brand" href="./">Agent Team<small>Multibot · MIT</small></a><p>{esc(t['foot_note'])}</p><div><a href="{GH}">GitHub ↗</a><a href="https://reachmade.com/products/#agent-team">Reachmade ↗</a><a href="{t['other']}" lang="{t['other_lang']}" hreflang="{t['other_lang']}">{esc(t['foot_other'])}</a></div></footer>
<script src="{b}home.js"></script><script src="{b}portfolio.js" data-product="agent-team"></script>
</body></html>
'''


if __name__ == '__main__':
    for lang, target in [('en', ROOT / 'index.html'), ('ja', ROOT / 'ja/index.html')]:
        target.write_text(page(COPY[lang]))
    print('Built English and Japanese pages from copy.json and retained source artifacts.')
