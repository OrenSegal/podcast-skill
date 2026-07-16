---
name: signal-scout
description: Turn a pile of ranked research findings (from podcast mining, competitor audits, doc sweeps, whatever) into one prioritized Artifact report. Use as the reporting stage of any skill that has already done the extraction and just needs to present it as a shareable, ranked, reasoned page. Not a research method itself, and not a curation step.
---

Render everything relevant, ranked, with reasoning. Don't curate down to a
"top 3" and don't dump an uncurated section-by-section wall either. Every
item in scope for the query gets a slot; priority order does the filtering
work instead of a cutoff.

## When to reach for this

Called from another skill's own report step (e.g. `podcast`'s Step 5), once
that skill has already: extracted findings, tagged confidence per finding
(measured / anecdotal / speculative, confirmed-once / confirmed-twice /
unresolved), and decided what's in scope for the user's actual query.

This skill does NOT do extraction, dedup, or synthesis. That's upstream work
specific to the source type. This is purely: take the finished findings list
and render it well.

## Rules

1. **Rank, don't cut.** Every finding relevant to the query appears, grouped
   into priority tiers (e.g. ship-now, already-validated, open-decision,
   worth-testing, skip-this-source). A finding that doesn't make tier 1
   still belongs in the report, lower down, not silently dropped. If a
   genuine volume problem exists (50+ findings), say so explicitly and link
   to the full data instead of truncating without a note.
2. **Reasoning travels with the finding**, not to a separate section. Each
   item states: what it claims, why it matters here, and the evidence
   (source, episode/doc, date, confidence tag) inline — never split reason
   from citation.
3. **No em dashes anywhere in the copy.** Use a period, colon, comma, or
   parentheses instead. This is a hard style rule for this skill's output,
   not a preference — check the rendered text for "—" before publishing.
4. **Confidence is visible, not just implied.** A short tag per item
   (confirmed twice / measured / anecdotal / unresolved / single-sourced) so
   the reader can tell a load-bearing finding from a hunch at a glance.
5. **Contrast is theme-aware, correctly, every time.** Use the template
   below rather than re-deriving color tokens per report — a prior version
   of this skill inverted a dark/light token block and shipped light text
   on a light card. Copy `template.html`, keep its `:root` /
   `:root[data-theme="dark"]` / `:root[data-theme="light"]` / media-query
   block structure exactly (four blocks, each self-contained, never a
   partial override), and only change the actual color values and copy.
6. **Don't default to the AI-cliché look.** A second prior version of this
   skill shipped warm-cream background + serif headline + terracotta
   accent, unexamined — the exact combination `artifact-design` calls out
   as a generic default, and a user flagged it as slop on sight. Ground
   the palette and type pairing in the report's actual subject instead.
   `template.html`'s current palette (dark "signal intercept" panel, sans
   display, monospace data, signal-strength bars as a real priority
   readout) is one worked example for research-report subjects, not a
   mandatory replacement cliché — reground it again if the subject calls
   for something else, but never fall back to cream+serif+terracotta.
7. **Load `artifact-design` before publishing** — required by the
   `Artifact` tool itself, not optional.

## Structure that works

- One-line eyebrow: source scope + date (e.g. "36 episodes, 2026-07-16").
- Headline framed as the answer to the query, not a generic report title.
- One-sentence restatement of the query, so the ranking makes sense.
- Priority tiers, each a short label explaining what the tier means (not
  just "Tier 1") — e.g. "Ship before the deadline", "Already validated,
  keep doing it", "Decide before building further", "Worth a test, not a
  decision", "Skip this source next time". Every tier renders, even ones
  with only 1-2 items — don't merge or hide a thin tier.
- Within a tier: order by confidence (confirmed-twice above measured above
  anecdotal above unresolved), not by source or chronology.
- Footer: where the source data and any backing ledger/state files live.

## Anti-patterns (seen and rejected in earlier drafts)

- Picking a "top 3-4 actionables" and demoting everything else to a
  footnote strip. The user wants full prioritized coverage, not a curated
  highlight reel.
- Section headers for "Use now / Watch / Ignore" with a fixed 3-4 item cap
  per section regardless of how many findings actually exist at that
  priority.
- Warm-cream-plus-terracotta-serif as an unexamined default (flagged by
  `artifact-design` as a cliché combination) — pick a neutral and accent
  that's actually grounded in the report's subject instead.
