---
name: podcast
description: Pull podcast transcripts on demand and mine them for ideas, trends, and mechanics — without dumping raw transcript into context. Use when the user shares a podcast/episode URL, names a show, or asks what's worth taking from an episode/series. Handles Apple Podcasts, Spotify, YouTube, and RSS feeds.
---

Turn podcasts into extracted findings. The whole point is that raw
transcript NEVER enters main context — subagents eat the noise, you keep
the signal.

## Why this exists

A 60-minute episode is ~10k words and roughly 70% filler: banter, sponsor
reads, audience-hyping, restating the last point. Reading it directly
burns context and buries the 3 specifics that mattered. Summarizing it
flattens exactly the weird concrete detail that WAS the idea.

Extract, don't summarize.

## What are you mining for?

This skill isn't hardwired to one lens (e.g. customer/monetization
validation) — that's one possible focus among several (technical patterns,
design/craft inspiration, a specific research question, general "what's
worth knowing here").

**Priority order for picking the lens:**
1. **The user stated one this run** ("mine this for X") — use it, exactly.
2. **Not stated** → don't default to a blank, filter-free summary either.
   Default to relevance to the current project you're running in (its
   CLAUDE.md, its current roadmap/open questions, whatever you already know
   about what the user is building) crossed with the podcast's own actual
   subject matter. A dev-workflow episode mined from inside a codebase repo
   defaults to "what does this change about how we build here," not to
   generic self-help takeaways.
3. **Genuinely no project context available** (a bare Claude Code session
   with no repo) → then ask, or fall back to general signal (mechanics,
   claims, predictions, no relevance filter) and say that's what you did.

Whichever lens applies, it changes what counts as fluff vs. payload in
Step 3 and how Step 4 frames relevance — decide it before fanning out
extractors, not after.

## Step 0 — Check the ledger before doing anything

`ledger.py` (next to this file) tracks state across runs so re-mining a show
doesn't repeat work: which episodes are already extracted, what predictions
are still open, and cross-show overlap.

```bash
python3 ~/.claude/skills/podcast/ledger.py mined --show "<show name>"
```

Cross-reference this against the episode list `resolve.py` returns (Step 1)
and only fan out extractors (Step 3) on episodes NOT already in this list.
If every candidate episode is already mined, say so and skip straight to
Step 3.5 (prediction check) and Step 5 (report) — don't re-extract.

## Step 1 — Resolve source → feed → transcripts

`resolve.py` (next to this file) does the whole first mile for ANY show.
Don't hand-roll curl pipelines; don't hardcode a feed.

```bash
python3 ~/.claude/skills/podcast/resolve.py "<url-or-show-name>" --limit 12 --download tx/
```

Accepts an Apple URL, a Spotify URL, a direct RSS URL, or a bare show
name. Prints the feed, marks the `?i=` target episode, lists which
episodes have transcripts, and with `--download` writes flattened `.txt`
plus a `manifest.json` (title, date, path, words, target).

What it encodes, so you don't rediscover it:
- **Apple pages 500 on fetch. Never fetch them.** Only the `id<N>` in the
  URL matters → `itunes.apple.com/lookup?id=<N>&entity=podcast` → feedUrl.
- **The `?i=<EPISODE_ID>` DOES resolve** — but only via the *show* lookup
  with `entity=podcastEpisode&limit=200`, matching on `trackId`. Looking
  up the episode id directly returns `resultCount:0`. This is the trap.
- Spotify has no open API — fall back to iTunes name search.
- Some shows (Apple-exclusive) expose no `feedUrl`. Say so, don't guess.

## Step 2 — Transcription fallback (only if the feed has no transcript tags)

Fallback order when `resolve.py` prints no `podcast:transcript` tags:
1. Show's own site — google `"<episode title>" transcript`
2. `yt-dlp --write-auto-sub --skip-download --sub-lang en --sub-format vtt "<yt-url>"`
3. Actual transcription (Whisper local, or a cloud ASR API) — only once 1-2
   are exhausted. Hosts like Flightcast and Transistor embed official
   machine transcripts; 12 episodes can be free and instant instead of an
   hour of local compute.

Before step 3, check the remembered preference:

```bash
python3 ~/.claude/skills/podcast/ledger.py config-get transcription_method
```

- If it returns `local` or `cloud`, use that method silently — don't re-ask.
- If empty, ask the user with `AskUserQuestion`: local Whisper (free, slower,
  private, `uv run --with openai-whisper whisper ep.mp3 --model small
  --output_format txt`) vs. a cloud ASR API (paid, fast, needs an API key in
  env — gate on the key actually being present, borrowed from OpenClaw's
  `requires.env` dependency-gating idea: don't offer cloud as a real option
  if no ASR key is set). Offer a "remember this choice" option on each; if
  chosen, persist it with `ledger.py config-set transcription_method
  local|cloud` so future runs skip the question.

## Step 3 — Fan out extractors

One subagent per 1-2 episodes (the ones Step 0 didn't already rule out), run
in parallel. Each reads its transcript IN FULL and returns structured
findings only. Never read the transcript yourself.

The extraction prompt must demand SHAPES, not a summary:

1. **What it actually is** — vs. what the clickbait title promised. The
   gap between these two is itself a signal about the show.
2. **Concrete mechanics** — named workflows, prompt patterns, configs,
   step order, exact numbers. Anything reproducible. Be greedy here; this
   is the payload.
3. **Claims with numbers** — each tagged `[measured]` / `[anecdotal]` /
   `[speculative]` based on how the speaker sourced it. This tag does
   most of the fluff-cutting work.
4. **Tools named** — and crucially: actually used, or just name-dropped?
5. **Pain points / "I wish X existed"** — the idea seeds.
6. **Falsifiable predictions** — checkable later, which makes the show
   scoreable over time.
7. **Fluff ratio** — % substance, and what the filler was.

Rules for every extractor:
- Quote at most one short sentence where phrasing is load-bearing.
  Paraphrase otherwise. Never reproduce long passages — it's someone
  else's copyrighted work.
- Empty section → say "none". Never manufacture content.
- Unsourced hype goes in FLUFF, not CLAIMS.

**Also require a structured block**, so the corpus stays machine-queryable
across shows and runs (this is what feeds Step 3.5's dedup and the
ledger). Ask each extractor to close its response with a fenced JSON block:

```json
{
  "episode": "<title>",
  "show": "<show name>",
  "date": "<published date>",
  "findings": [
    {"claim": "...", "tag": "measured|anecdotal|speculative", "topic": "..."}
  ],
  "predictions": ["<falsifiable prediction text>", "..."]
}
```

`topic` is a short free-text tag (e.g. "onboarding", "pricing", "agent
loops") — it's what makes cross-show topic overlap in Step 3.5 findable
instead of requiring manual eyeballing.

After each extractor returns, record it:

```bash
python3 ~/.claude/skills/podcast/ledger.py record --show "<show name>" \
  --episode "<title>" --date "<date>" --findings-path "<path to saved findings>" \
  --predictions-json '["<prediction 1>", "<prediction 2>"]'
```

## Step 3.5 — Check old predictions, surface cross-show overlap

Before synthesizing, pull what earlier mining runs (on this show or others)
already put on record:

```bash
python3 ~/.claude/skills/podcast/ledger.py predictions --show "<show name>"
python3 ~/.claude/skills/podcast/ledger.py dedup --threshold 0.5
```

- **Predictions**: for each open prediction, check whether anything in the
  freshly-mined episodes confirms, refutes, or is now stale (a
  tool/model/pricing prediction older than ~8 weeks is presumptively stale —
  say so rather than silently carrying it forward). Resolve it:
  `ledger.py check-prediction --show "<show>" --episode "<title>" --text "<substring>" --status confirmed|failed|stale`
- **Dedup**: `ledger.py dedup` does token-overlap matching across every
  show's recorded predictions/claims — it's a candidate list to check by
  hand, not a verdict (no embeddings, deliberately dependency-free). High
  scores between two different shows are exactly the "repetition across
  independent sources = signal" and "contradiction = most valuable finding"
  moments Step 4 cares about — go find them explicitly instead of relying on
  memory of past mining sessions.

## Trust mechanics, distrust ratings

Measured 2026-07-16 by running two independent extractions over the same
12 transcripts with the same prompt:

- **Mechanics matched almost perfectly** across runs — step orders, tool
  names, numbers, prompt structures. Extraction of concrete detail is
  reliable.
- **Judgments diverged wildly.** One episode scored 35% substance in one
  pass and 70% in the other. Fluff ratio is a vibe, not a measurement.

So: report mechanics as findings. Report fluff ratios as rough
orientation only, never as data, and never build a "signal quality"
ranking that the user might mistake for measurement. If a rating actually
matters to a decision, extract twice and compare.

Corollary: extractors reliably catch what a *single* pass misses about
evidence quality. The highest-value thing a second pass found was that an
impressive-looking dashboard predated the system being credited for it.
Ask explicitly: *does the evidence shown actually postdate the thing it's
offered as proof of?*

## Step 4 — Synthesize across episodes

One episode is one opinion. The trend only exists across episodes.

- **Repetition across independent episodes** = signal. Same claim from
  different guests, different weeks → real.
- **Contradictions** = the most valuable output. Where does ep 3 refute
  ep 9? Where did a prediction already fail? (Step 3.5's dedup pass and
  prediction ledger are what make this mechanical instead of eyeballed.)
- **Decay check** — model/tool episodes rot in weeks. Date-stamp
  everything and mark what's already stale.
- **Filter against whatever lens the user gave you** (see "What are you
  mining for?" above). "What's trending" is generic slop regardless of
  lens. "What does this confirm, contradict, or add to the specific thing
  the user is actually working on" is the useful question, whatever that
  thing is this run — it isn't always Shelfie, and it isn't always
  customer/monetization relevance.

## Step 5 — Report via the `signal-scout` skill

Chat text or a raw markdown dump doesn't hold up as something to reopen or
share later. The report step is delegated to the `signal-scout` skill —
invoke it rather than re-deriving report structure/tokens here. Hand it:

- every finding in scope for the user's query (not a curated top-N — rank
  by priority, don't cut),
- each finding's confidence tag (confirmed-twice / measured / anecdotal /
  unresolved / single-sourced),
- the ledger's open predictions (Step 3.5) and dedup output, so
  contradictions/overlaps land in the ranking instead of a separate
  ignored section,
- episode + date per finding, always — a dated citation beats an unsourced
  claim, the one habit worth keeping from every consumer podcast-summarizer
  that does source-attribution well.

`signal-scout` owns the Artifact mechanics (theming, tier layout, the
no-em-dash copy rule) — don't hand-roll a new report shell per mining run.

## Hygiene

- Transcripts go to the scratchpad, NEVER the repo. Someone else's words,
  and they bloat git.
- Keep a manifest (`title`, `date`, `path`, `words`) so the synthesis
  stage can cite which episode a finding came from.
- 12 episodes ≈ 80k words ≈ free via RSS. Whisper on 12 episodes is ~1hr
  of compute. Always check step 2's fallback ladder before reaching for
  Whisper/cloud ASR.
- State lives in `~/.claude/skills/podcast/config.json` (preferences) and
  `~/.claude/skills/podcast/state/<show-slug>.json` (per-show ledger:
  mined episodes, findings paths, predictions). Both are plain JSON,
  inspectable/editable by hand if the ledger ever needs correcting.

## What's deliberately NOT borrowed from prior art

Researched 2026-07-16 against OpenClaw's AgentSkills spec and several
existing Claude Code podcast skills before building the above:

- **OpenClaw's skill format has no memory/state, hooks, or structured
  output of its own** — it's YAML frontmatter + a markdown body, full stop.
  The ledger/predictions/dedup/structured-output machinery above has
  nothing to inherit from that spec; it's bespoke to this skill. The one
  idea worth taking was `requires.env`-style dependency gating, folded into
  Step 2's cloud-ASR check.
- Consumer summarizers (BibiGPT, Podwise) lean on mind-maps/flashcards —
  skipped deliberately: that's re-summarizing, which is the exact failure
  mode this skill exists to avoid.
- VERIDIVE's "DeepWatch" continuous topic-monitoring is the closest
  existing analogue to Step 3.5's dedup/prediction-tracking; this skill's
  version is a manual-trigger, dependency-free, token-overlap pass rather
  than a standing background watcher — right-sized for a skill invoked
  on demand, not a running service.
