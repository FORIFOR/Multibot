# Agent Team (FORIFOR/Multibot)

Local-first AI teams that draft, review and revise deliverables. Python/FastAPI backend (`backend/agentteam`), React UI (`frontend/`), public site (`docs/`, GitHub Pages). User-facing text is Japanese first, English second.

## Three different surfaces — do not mix them
- **App** (`frontend/src`): design contract in `docs/design/`. What users install is the committed bundle `backend/agentteam/ui`; after UI changes run `pnpm build` in `frontend/` and copy `frontend/dist/.` into it, or installed users and the `secured-container` CI job see the old UI.
- **Public site** (`docs/index.html`, `docs/ja/index.html`): design contract in `docs/site/`. Generated — edit `docs/site/build_site.py`, then run it. Never edit the two HTML files by hand.
- **Detailed work record** (`frontend/src/pages/RunView.tsx`): the inspector inside the app; may use technical vocabulary the everyday screens must not.

## UI work
- New UI or UI changes use `/ui-craft` (`.claude/skills/ui-craft/SKILL.md`). Read `docs/design/brief.md` and `acceptance.md` first.
- Reading code, capturing a screen and looking at the image are three different acts. After a change, run the app, capture, and open the PNG.
- Get an independent review from `ui-reviewer` with images; do not hand it your own verdict.
- Never write PASS for a check that was not run. Never delete tests, loosen thresholds or refresh baselines to pass.
- If three repair rounds do not converge, stop and report what is unmet.
- "Better than VoiceOS / Wonder" needs a named comparison, same conditions and evidence. Otherwise do not claim it.
- No push, merge, deploy or release without explicit permission in the current conversation.

## Honesty rules of this product
- No fabricated conversations, success logs, testimonials, user counts or star counts anywhere.
- Every number on the site links to `docs/evidence/`. Unfavourable results are shown at the same size.
- Partial, unverified and failed stay visible as such in the UI.

## Commands (verified 2026-09-19)
- Backend tests: `cd backend && .venv/bin/python -m pytest -q` (dev extras: `uv pip install --python .venv/bin/python -e ".[dev]"`).
- Frontend (pnpm): in `frontend/` — `pnpm build` (includes `tsc -b`), `pnpm lint`, `pnpm test:router`, `test:bots`, `test:journey`, `test:welcome`, `test:markdown`.
- Browser regressions against the fresh build, no server needed: `node scripts/ui-polish-smoke.mjs`, `node scripts/three-step-smoke.mjs` (in `frontend/`).
- Browser smokes that need the scripted test server: `cd backend && AGENTTEAM_ALLOW_FAKE_PROVIDER=1 AGENTTEAM_NO_SEATBELT=1 .venv/bin/python scripts/demo_fake_server.py --port 8791`, then `node scripts/ui-smoke.mjs` and `node scripts/workroom-smoke.mjs`.
- Screens for review: with that server running, `node frontend/scripts/ui-capture.mjs` writes `artifacts/ui/*.png`.
- Site: `python3 docs/site/build_site.py`; serve `docs/` and run `node frontend/scripts/site-check.mjs <base>`.
- Evidence gate: `node scripts/ui-quality.mjs begin|inspect|check|assert <session>`; its own tests: `node --test scripts/tests/ui-gate.test.mjs`.
- The scripted test provider is test-only and never proves real model behaviour. Real-model benchmarks use local Ollama, not the Claude subscription.
