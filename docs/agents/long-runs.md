# Long solver runs

Before launching a long solver, search or hunt, list every available speedup
(tighter model, channeling or decomposition, per-task splits, portfolio
workers, warm starts, dropping constraints the goal does not need), apply the
ones that pay and name the rest in the launch message. The fast approach
should not wait for Chris to ask for it.

Box-load, scratch-directory and job-watch rules for any long run:
`~/.agents/skills/flow/claude/OPERATIONS.md` § Dispatch and § Wait.
