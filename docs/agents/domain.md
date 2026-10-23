# Domain Docs

## Layout

This repo uses a single-context layout:

- `GLOSSARY.md` at the repository root.
- `docs/adr/` for architecture decision records.

## Before exploring

Read `GLOSSARY.md` and the ADRs relevant to the area being explored.

If these files do not exist, proceed silently. Do not suggest creating
them upfront. The domain-modeling workflow creates them when terms
or decisions are actually resolved.

## Vocabulary

Use glossary terms consistently in issues, proposals, hypotheses,
tests, and implementation.

If a needed term is missing, reconsider whether it belongs to the
project's vocabulary, or note the gap for domain-modeling.

## ADR conflicts

Explicitly flag proposals that contradict an existing ADR.
Identify the ADR and explain why the decision should be reconsidered.
