#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const os = require("os");

const SKILLS_DIR = path.join(os.homedir(), ".claude", "skills");
const REPO_ROOT = path.join(__dirname, "..");
const PLUGINS = ["signal-scout", "podcast"];

// Files we never overwrite once a user has run the skill and built up state.
const PRESERVE_IF_EXISTS = new Set(["config.json"]);

function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    if (entry.name === ".claude-plugin" || entry.name === "__pycache__") continue;

    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);

    if (entry.isDirectory()) {
      copyDir(srcPath, destPath);
      continue;
    }
    if (PRESERVE_IF_EXISTS.has(entry.name) && fs.existsSync(destPath)) {
      console.log(`  skip (already exists)  ${path.relative(SKILLS_DIR, destPath)}`);
      continue;
    }
    fs.copyFileSync(srcPath, destPath);
    console.log(`  write                  ${path.relative(SKILLS_DIR, destPath)}`);
  }
}

fs.mkdirSync(SKILLS_DIR, { recursive: true });

for (const name of PLUGINS) {
  const src = path.join(REPO_ROOT, "plugins", name);
  const dest = path.join(SKILLS_DIR, name);
  console.log(`Installing ${name} -> ${dest}`);
  copyDir(src, dest);
}

console.log("\nDone. Restart Claude Code (or start a new session) to pick up the new skills.");
