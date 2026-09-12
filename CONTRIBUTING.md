# Contributing

Thanks for looking. The bar for this project is simple: **nothing fake in the product path.**

- Bot conversations are real deliveries (`message.sent` events). No scripted chat, no canned success logs.
- Every verification is bound to an artifact revision. Old checks are never reused on new content.
- The fake provider (`backend/agentteam/providers/fake_driver.py`) is for deterministic tests and UI smoke only. It cannot be selected from config, and runs that use it are labelled `provider_kind=fake`.

## Dev loop

```bash
cd backend && uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python -e '.[dev]' pytest-timeout
.venv/bin/python -m pytest -q --timeout 120
cd ../frontend && pnpm install && pnpm build
```

UI smoke without an API key (scripted provider, clearly labelled):

```bash
cd backend && AGENTTEAM_ALLOW_FAKE_PROVIDER=1 .venv/bin/python scripts/demo_fake_server.py --port 8791
cd ../frontend && node scripts/ui-smoke.mjs
```

Real-LLM smoke (needs a key; this is the only thing that proves the product works end to end):

```bash
cd backend && ANTHROPIC_API_KEY=... .venv/bin/python scripts/smoke_real_llm.py --budget 1.5
```

## Pull requests

- One task per branch. Keep diffs local; don't mix refactors into fixes.
- Add or extend a deterministic test for runtime behaviour. Mark anything that needs a real model as unverified in the PR body.
- Never commit keys. Config holds references only (`env:`, `keychain:`, `file:`).
- Prompts and skills in `backend/agentteam/prompts` / `backend/agentteam/skills` are original; don't paste external prompts wholesale (see `docs/blueprint/REFERENCES.md`).
