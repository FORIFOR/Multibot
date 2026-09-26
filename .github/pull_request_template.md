## What changes

<!-- One task per pull request. What does it change, and why? -->

## How it was verified

<!-- Commands you ran and their results. Keep categories separate: -->
- Deterministic tests (scripted provider):
- Browser checks / screenshots (for UI changes):
- Real model run (which provider and model), if any:

## Not verified

<!-- Anything you could not check. "None" only if that is true. The scripted provider never proves real-model behaviour. -->

## Checklist

- [ ] No scripted chat, canned success logs or fake counts in the product path
- [ ] UI changes: `pnpm build` in `frontend/` and `frontend/dist/.` copied into `backend/agentteam/ui`
- [ ] Public site changes: edited `docs/site/build_site.py` and regenerated (not the HTML by hand)
- [ ] No keys or secrets committed
