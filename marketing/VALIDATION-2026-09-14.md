# Launch verification — 2026-09-14

- GitHub commit `fb3fbf5` pushed to main; CI 34765855449 passed backend, frontend, and UI smoke. The pre-existing CI uses its test provider; it is not real-LLM evidence.
- GitHub Pages deployment completed. Both the Japanese page and the new MP4 are served publicly; MP4 returns HTTP 200 and video/mp4.
- Local Japanese page checked in the browser at desktop and 390px width: no horizontal overflow (document width 375, viewport 390); F-1 selects the corresponding changed passage; install-copy button reports success.
- EN and JA static assets, fragment links and duplicate IDs checked locally; no missing assets/anchors or duplicate IDs.
- MP4 decoded by ffprobe: 32 seconds, H.264 1280×800, AAC. Captions provided as WebVTT. The footage comes from the existing real-model replay, not a newly captured live run. Narration is synthesized; limitations are shown in copy and narration.
- Three new regression tests use the exported real-provider result records, without a mock provider. They check quota detection (100 failed plus 2 partial), preservation of non-quota outcomes and resumability of unattempted repetitions.
- Facebook reel published as public with AI label: https://www.facebook.com/reel/1117648910591001/
- No new live-model benchmark was run. The existing interrupted comparison cannot establish a team-quality advantage. No customer-data PoC or production-readiness claim was made.
- Business form entry point and disclosure retained. A new lead was not submitted; end-to-end receipt and delivery were not reverified in this pass.
