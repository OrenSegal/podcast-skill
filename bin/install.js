#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const os = require("os");

const HOME = os.homedir();
const REPO_ROOT = path.join(__dirname, "..");
const PLUGINS = ["signal-scout", "podcast"];

// Both tools read the identical SKILL.md-plus-scripts folder shape, just from
// different homes: Claude Code from ~/.claude/skills, Codex CLI (global) from
// ~/.codex/skills. https://developers.openai.com/codex/skills
const TARGETS = [
  { tool: "Claude Code", dir: path.join(HOME, ".claude", "skills") },
  { tool: "Codex CLI", dir: path.join(HOME, ".codex", "skills") },
];

// Files we never overwrite once a user has run the skill and built up state.
const PRESERVE_IF_EXISTS = new Set(["config.json"]);

function copyDir(src, dest, skillsDir) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    if (entry.name === ".claude-plugin" || entry.name === "__pycache__") continue;

    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);

    if (entry.isDirectory()) {
      copyDir(srcPath, destPath, skillsDir);
      continue;
    }
    if (PRESERVE_IF_EXISTS.has(entry.name) && fs.existsSync(destPath)) {
      console.log(`  skip (already exists)  ${path.relative(skillsDir, destPath)}`);
      continue;
    }
    fs.copyFileSync(srcPath, destPath);
    console.log(`  write                  ${path.relative(skillsDir, destPath)}`);
  }
}

// Only install into a tool's tree if that tool is actually in use on this
// machine (its home dir already exists) — never litter a fresh ~/.codex or
// ~/.claude onto a machine that doesn't have the tool. If neither is present
// yet, default to Claude Code, since that's this package's primary target.
let targets = TARGETS.filter((t) => fs.existsSync(path.dirname(t.dir)));
if (targets.length === 0) targets = [TARGETS[0]];

for (const { tool, dir } of targets) {
  fs.mkdirSync(dir, { recursive: true });
  console.log(`${tool} (${dir})`);
  for (const name of PLUGINS) {
    const src = path.join(REPO_ROOT, "plugins", name);
    const dest = path.join(dir, name);
    console.log(`Installing ${name} -> ${dest}`);
    copyDir(src, dest, dir);
  }
}

console.log("\nDone. Restart the tool(s) above to pick up the new skills.");
