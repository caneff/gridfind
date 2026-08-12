---
name: gridfind-flags-to-map
description: Synthesize the eval page's saved flags into a wayfinder map issue you approve before it is filed.
disable-model-invocation: true
---

# gridfind-flags-to-map

Turn the flags a reviewer left on the `just eval-links` page into a `wayfinder:map`
— a planning issue that groups the related findings and points at where to dig
next. You cluster and draft; the reviewer approves before anything is filed.

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
   Present the proposed clusters and let the reviewer decide whether they become
   one map or several. Default: one map, each cluster a `## Notes` subsection.
   Wait for the reviewer's call before drafting.

4. **Draft each map in the `wayfinder:map` shape.** Two headings:
   - `## Destination` — where this line of investigation is headed: the question
     the map exists to answer.
   - `## Notes` — the findings, each carrying its receipts: source stem(s),
     verdict, and comment(s). Name the stem; do not paste the link — it already
     lives in `src/gridfind/links/<stem>.txt`, and repeating it in the issue just
     duplicates a long blob a reader can `cat`. A finding the flags do not
     resolve is written as an explicit open question — never a fabricated
     conclusion.

5. **Show the draft.** Present each drafted map in full, and file it only after
   the reviewer approves it.

6. **On approval, file each map.**
   `gh issue create --title "<theme> — wayfinder map" --label wayfinder:map --body "<draft>"`
   (heredoc for the body). Report each issue number.

7. **Archive the covered flags.** For each filed map, move its flags out of the
   store, stamped with that issue's number:
   ```
   uv run python -c "import sys; sys.path.insert(0, 'scripts'); from eval_links import archive_flags, FLAGGED_PATH, FLAGGED_ARCHIVE_PATH; archive_flags(FLAGGED_PATH, FLAGGED_ARCHIVE_PATH, {<covered stems>}, <issue number>)"
   ```
   Covered flags leave the store; uncovered flags stay for the next run.

8. **Stop at the filed map.** Do not run `/to-spec` or `/to-tickets` — the map is
   the deliverable.
