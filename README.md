# claude-podcast-skill

Two Claude Code skills, shipped together:

- **`podcast`** — resolve any podcast URL to its feed/transcripts, mine
  episodes for ideas without dumping raw transcript into context, track
  falsifiable predictions across episodes, dedup cross-show claims.
- **`signal-scout`** — the reporting stage `podcast` calls once it has
  findings: renders everything relevant, ranked into priority tiers, as one
  shareable Artifact. `podcast` depends on it.

## Install

Pick whichever install path fits how you use Claude Code. All three land the
same two skills.

### Claude Code plugin (recommended)

```
/plugin marketplace add OrenSegal/claude-podcast-skill
/plugin install podcast@oren-podcast-skills
```

`podcast` declares a dependency on `signal-scout`, so installing it pulls
`signal-scout` in automatically. Skills are invoked as `/podcast` and
`/signal-scout` (single-skill plugins, so no `plugin:skill` prefix needed).

### skills.sh

```
npx skills add OrenSegal/claude-podcast-skill
```

### npm / npx

```
npx claude-podcast-skill
```

Copies both skills straight into `~/.claude/skills/`. Safe to re-run — it
never clobbers a `config.json` you've already customized.

## Repo layout

```
plugins/podcast/          the podcast skill (SKILL.md, ledger.py, resolve.py)
plugins/signal-scout/     the signal-scout skill (SKILL.md, template.html)
.claude-plugin/marketplace.json   marketplace manifest for the two plugins above
bin/install.js            npx entry point, same skill files, no Claude Code required
```

## License

MIT
