
Experimental agent-tool addition: `read_artifact` accepts optional `start_char` (zero-based Unicode code points) and `max_chars` (1–20000). With either field supplied, omitted `max_chars` defaults to 4000; starts beyond EOF return an empty range. Pin `revision` across pages. The result and `artifact.read` event include start/end, total characters, `more` and `partial`; the SHA remains the complete artifact's SHA. Binary range reads are rejected. Omitting both fields preserves the previous complete-read response. Partial reading does not establish complete review coverage.

Range reads that would exceed the configured tool-output character limit including metadata are explicitly rejected before recording a read. Retry with a smaller range; no silently truncated range is reported as delivered.

For peer messages, `request` stores an assignment for the recipient's scheduled session; it does not spawn an immediate reply or transfer task/output ownership. `question` requests a specific answer and can start a reply session for an idle recipient, subject to runtime permissions and limits. Neither delivery receipt proves an answer, correction, or task completion.

Experimental draft editing: the existing `workspace_write` permission accepts either `{path, content}` (complete text, unchanged contract) or `{path, edit: {expected_sha256, old_text, new_text}}`. An edit requires an existing UTF-8 task draft, matching SHA-256 of all current bytes, and exactly one nonempty `old_text` occurrence. Missing/ambiguous text, stale hashes, or mixed complete/edit inputs are rejected without changes. Include unchanged surrounding text to disambiguate. Each successful write returns the new whole-draft SHA. A published artifact's SHA is usable only if the workspace draft has identical bytes. Edits remain unpublished and go through the same delivery checks, publication and review gates. This reduces generation length; it does not prove semantic correctness.

### Literal text checks

`run_check` kinds `text_contains` and `text_not_contains` search exact substrings in UTF-8 decoded source, preserving Markdown markers, whitespace, case and punctuation. They do not search rendered Markdown or establish semantic coverage. A failed search can reflect formatting differences; inspect the original revision before concluding that a requirement is missing. This clarification does not change verdicts or recorded check events.

### Explicit character selection (experimental)

`POST /api/runs` accepts `inputs.selected_agent_ids: string[]` with
`inputs.team_selection: "fixed"`. IDs must identify enabled configured workers,
excluding coordinator/reporter, which remain automatically included. Selection
preserves names, emojis, voice, tools and model settings in the run snapshot;
forks retain that selected snapshot before applying explicit supported overrides.
At least one producer and any required independent reviewer must be included.
Invalid duplicate/empty IDs or adaptive combination return 422; unavailable
members or missing capabilities return 409 with `code: "team_selection"`.
Omitting this field preserves the existing fixed/adaptive behavior and serialization.
