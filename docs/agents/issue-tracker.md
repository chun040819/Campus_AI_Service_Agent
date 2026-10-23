# Issue tracker: GitHub

Issues and specs live in GitHub Issues for
`chun040819/Campus_AI_Service_Agent`.

Use the `gh` CLI, prefixed with `rtk` as required by the repo instructions.
Run commands inside this clone so `gh` resolves the repository automatically.

## Operations

- Create: `rtk gh issue create --title "..." --body-file <file>`
- Read: `rtk gh issue view <number> --json number,title,body,labels,comments`
- List: `rtk gh issue list --state open --json number,title,body,labels`
- Comment: `rtk gh issue comment <number> --body-file <file>`
- Add labels: `rtk gh issue edit <number> --add-label "..."`
- Remove labels: `rtk gh issue edit <number> --remove-label "..."`
- Close: `rtk gh issue close <number>`

Write multiline bodies to a temporary file and pass it with `--body-file`.

## Relationships

Use GitHub sub-issues and native issue dependencies where supported.
Dependency API calls require the issue database ID, not its issue number.

If sub-issues are unavailable, put `Part of #<parent>` at the top of
the child issue and link it in the parent's task list.

If dependencies are unavailable, put `Blocked by: #<number>` at the
top of the child issue. Work is unblocked when all blockers are closed.

## Pull requests as a triage surface

**PRs as a request surface: no.**

## Skill conventions

When a skill says "publish to the issue tracker", create a GitHub issue.
When a skill says "fetch the relevant ticket", read the GitHub issue.

For wayfinder workflows, use a map issue labelled `wayfinder:map`
and child issues labelled `wayfinder:<type>`.
Select unassigned children with no open blockers in map order.
Claim work by assigning the issue to yourself.
Record the result on the child issue, close it when complete, and
add a result link to the map's Decisions-so-far.
