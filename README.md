# podcast-skill

Two skills, shipped together, for both Claude Code and Codex CLI — both tools
read the identical `SKILL.md`-plus-scripts folder shape, just from different
homes (`~/.claude/skills` vs `~/.codex/skills`).

- **`podcast`** — resolve any podcast URL (Apple Podcasts, Spotify, direct
  RSS, or YouTube) to its feed/transcripts, mine episodes for ideas without
  dumping raw transcript into context, track falsifiable predictions across
  episodes, dedup cross-show claims.
- **`signal-scout`** — the reporting stage `podcast` calls once it has
  findings: renders everything relevant, ranked into priority tiers, as one
  shareable Artifact. `podcast` depends on it.

### Requirements

- Python 3 (stdlib only for Apple/Spotify/RSS — no extra packages).
- [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) on `PATH` — only needed for
  YouTube URLs (`brew install yt-dlp`, `pipx install yt-dlp`). Apple/Spotify/
  RSS mining works without it.

## Install

Pick whichever install path fits your setup. All of them land the same two
skills.

### Claude Code plugin (recommended for Claude Code)

```
/plugin marketplace add OrenSegal/podcast-skill
/plugin install podcast@oren-podcast-skills
```

`podcast` declares a dependency on `signal-scout`, so installing it pulls
`signal-scout` in automatically. Skills are invoked as `/podcast` and
`/signal-scout` (single-skill plugins, so no `plugin:skill` prefix needed).

### Codex CLI

Codex has no plugin/marketplace layer, just skill folders. Drop both
directly into your global skills folder:

```
git clone https://github.com/OrenSegal/podcast-skill /tmp/podcast-skill
cp -r /tmp/podcast-skill/plugins/podcast /tmp/podcast-skill/plugins/signal-scout ~/.codex/skills/
```

Or use the npx installer below, it detects `~/.codex` and writes there too.
Codex reads global skills from `~/.codex/skills/<name>/SKILL.md`; see
[developers.openai.com/codex/skills](https://developers.openai.com/codex/skills).

### skills.sh

```
npx skills add OrenSegal/podcast-skill
```

### npm / npx

```
npx podcast-skill
```

Detects which of `~/.claude` and `~/.codex` exist on your machine and copies
both skills into whichever it finds (both, if you have both installed).
Falls back to `~/.claude/skills` if neither is present yet. Safe to re-run —
it never clobbers a `config.json` you've already customized.

## Repo layout

```
plugins/podcast/          the podcast skill (SKILL.md, ledger.py, resolve.py)
plugins/signal-scout/     the signal-scout skill (SKILL.md, template.html)
.claude-plugin/marketplace.json   marketplace manifest for the two Claude Code plugins above
bin/install.js            npx entry point, installs into Claude Code and/or Codex CLI
```

## License

MIT
