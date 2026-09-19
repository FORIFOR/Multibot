---
paths:
  - "frontend/src/**/*.{tsx,ts,css}"
  - "frontend/scripts/*.mjs"
  - "docs/home.css"
  - "docs/home.js"
  - "docs/site/**"
  - "docs/design/**"
---
# UI engineering rules

## Design contract
- App: `docs/design/brief.md` and `acceptance.md`. Public site: `docs/site/PRODUCT.md`, `DESIGN.md`, `ACCEPTANCE.md`. The user's explicit instruction comes first.
- The four teammates (coordinator, researcher, maker, reviewer) keep their shapes, colours and accessories. Character CSS lives in `frontend/src/quiet-cinema.css` and `bot-polish.css`; the site copies it at build time. Do not fork a second version.
- Fix information order, Japanese copy and the path to the main action before decoration.
- Reuse existing colours, type, spacing, radii and motion (`docs/design/tokens.md`). Structural values (0, 100%, auto, calc, optical corrections) are not token violations.
- Everyday screens use everyday words. `run`, `revision`, `sha256`, `tokens`, model ids and raw JSON belong in the detailed work record only (`three-step-smoke` enforces part of this).

## Interaction contract
- The main action has a label that says what will happen. Nothing starts automatically.
- States shown must be true: never infer live activity from old messages or task wording (`lib/bot-presentation.ts`). Unknown check outcomes read "unverified", never "passed".
- List the states this screen really has; check loading, empty, error, partial, read-only, long Japanese text where they apply.
- Keyboard operation, visible focus and where focus returns are part of the change.
- Non-essential motion stops under reduced motion and under "pause animation". Regular motion is checked separately.
- Mobile-width Chrome is not an iPhone. The browser build is not the installed bundle.

## Evidence contract
- Save the screenshot and then open it as an image. DOM or accessibility tree alone is not a visual check.
- Record size, URL, state, data and environment for each screenshot.
- Each claim is one of: measured, observed in an image, inferred, unverified.
- After any UI change the previous images, review and receipts are stale: capture and review again.
