---
name: gridfind-flags-to-tickets
description: Synthesize the eval page's saved flags into issues (map or ticket) the reviewer approves before they are filed, and archive the flags against them.
disable-model-invocation: true
---

# gridfind-flags-to-tickets

Turn the flags a reviewer left on the `just eval-links` page into issues — a
`wayfinder:map` for a foggy line of investigation, or a plain ticket for a
crisp one. You cluster and draft; the reviewer approves before anything is
filed.

## Archive against an existing issue

Flags sometimes already fed an issue filed by hand — the reviewer went
flags → grilling → spec → tickets outside this skill. When that has happened,
skip drafting: run the `archive_flags` one-liner in step 7 against that
issue's number and the stems it covers.

## Steps

1. **Read the flags.** `cat scripts/.eval-flagged.json`. Each entry is
   `{stem, comment}`, and a stem may carry several flags. A missing file or an
   empty `flagged` list means nothing to synthesize — say so and stop.

2. **Gather each flag's receipts.** The flag store holds only the note; fetch
   the rest per stem:
   - **Link** — the last whitespace-separated token of `src/gridfind/links/<stem>.txt`.
   - **Verdict + structure** — `uv run python scripts/inspect_link.py $(cat src/gridfind/links/<stem>.txt)`.
     It prints the verdict (found / broke / unknown) and classifies each constraint.

3. **Cluster by theme, and propose the clusters first.** Group the flagged
   findings by what they share — a constraint, a failure mode, a question.
   For each cluster, propose whether it becomes a **map** (foggy, needs
   wayfinding) or a **ticket** (crisp, ready to act on) and let the reviewer
   decide — including splitting or merging clusters. Wait for the reviewer's
   call before drafting.

4. **Draft each issue.**
   - **Map** — the `wayfinder:map` shape, two headings:
     - `## Destination` — where this line of investigation is headed: the
       question the map exists to answer.
     - `## Notes` — the findings, each carrying its receipts: source stem(s),
       verdict, and comment(s).
   - **Ticket** — a short body carrying the same receipts (stem(s), verdict,
     comment(s)) under whatever headings fit the ticket.
   - Either way: name the stem; do not paste the link — it already lives in
     `src/gridfind/links/<stem>.txt`, and repeating it in the issue just
     duplicates a long blob a reader can `cat`. A finding the flags do not
     resolve is written as an explicit open question — never a fabricated
     conclusion.

5. **Show the draft.** Present each drafted issue in full, and file it only
   after the reviewer approves it.

6. **On approval, file each issue.**
   - Map: `gh issue create --title "<theme> — wayfinder map" --label wayfinder:map --body "<draft>"`
   - Ticket: `gh issue create --title "<theme>" --label <label the reviewer named, or needs-triage> --body "<draft>"`
     (heredoc for the body). Every open issue must carry a state label — if the
     reviewer doesn't name one, use `needs-triage`.
   Report each issue number.

7. **Archive the covered flags.** For each filed issue, move its flags out of
   the store, stamped with that issue's number:
   ```
   uv run python -c "import sys; sys.path.insert(0, 'scripts'); from eval_links import archive_flags, FLAGGED_PATH, FLAGGED_ARCHIVE_PATH; archive_flags(FLAGGED_PATH, FLAGGED_ARCHIVE_PATH, {<covered stems>}, <issue number>)"
   ```
   Covered flags leave the store; uncovered flags stay for the next run. Use
   this same one-liner for the "archive against an existing issue" path above.

8. **Stop at the filed issues.** Do not run `/to-spec` or `/to-tickets` — the
   filed issue is the deliverable.
