#!/usr/bin/env python3
"""State store for the podcast skill: config, per-show mining ledger,
prediction tracking, and cross-show dedup.

Nothing here calls an LLM or a Claude Code tool. This is plumbing the
orchestrating agent shells out to; AskUserQuestion / Artifact stay in SKILL.md.

Layout:
  ~/.claude/skills/podcast/config.json        — persisted preferences
  ~/.claude/skills/podcast/state/<slug>.json  — one file per show
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
STATE_DIR = ROOT / "state"


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return s or "show"


def load_json(path, default):
    if not path.exists():
        return default
    with open(path) as f:
        return json.load(f)


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def show_path(slug):
    return STATE_DIR / f"{slug}.json"


def load_show(slug):
    return load_json(show_path(slug), {"show": slug, "episodes": {}})


def today():
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------- config

def cmd_config_get(args):
    cfg = load_json(CONFIG_PATH, {})
    print(cfg.get(args.key, ""))


def cmd_config_set(args):
    cfg = load_json(CONFIG_PATH, {})
    cfg[args.key] = args.value
    save_json(CONFIG_PATH, cfg)
    print(f"{args.key}={args.value}")


# ---------------------------------------------------------- mined episodes

def cmd_mined(args):
    """Print episode titles already mined for this show, so the caller can
    skip them before fanning out extractors."""
    show = load_show(slugify(args.show))
    print(json.dumps(sorted(show["episodes"].keys())))


def cmd_record(args):
    """Record one mined episode: findings summary + any predictions made.

    predictions_json: JSON array of strings (each a falsifiable prediction).
    """
    slug = slugify(args.show)
    show = load_show(slug)
    preds = json.loads(args.predictions_json) if args.predictions_json else []
    show["episodes"][args.episode] = {
        "date": args.date or "",
        "mined_at": today(),
        "findings_path": args.findings_path or "",
        "predictions": [
            {"text": p, "status": "open", "made_at": today(), "checked_at": None}
            for p in preds
        ],
    }
    show["show"] = args.show
    save_json(show_path(slug), show)
    print(f"recorded {slug}/{args.episode} ({len(preds)} predictions)")


# --------------------------------------------------------------- predictions

def cmd_predictions(args):
    """Dump open predictions for a show (or all shows if --show omitted),
    so a re-mining pass can check them against new episodes."""
    shows = [slugify(args.show)] if args.show else [p.stem for p in STATE_DIR.glob("*.json")]
    out = []
    for slug in shows:
        show = load_show(slug)
        for ep, data in show["episodes"].items():
            for p in data.get("predictions", []):
                if p["status"] == "open" or args.all:
                    out.append({"show": show["show"], "episode": ep, **p})
    print(json.dumps(out, indent=2))


def cmd_check_prediction(args):
    """Mark a prediction resolved/confirmed/failed after a later episode speaks to it."""
    slug = slugify(args.show)
    show = load_show(slug)
    ep = show["episodes"].get(args.episode)
    if not ep:
        print(f"no such episode recorded: {slug}/{args.episode}", file=sys.stderr)
        sys.exit(1)
    matched = False
    for p in ep["predictions"]:
        if args.text.lower() in p["text"].lower():
            p["status"] = args.status
            p["checked_at"] = today()
            matched = True
    if not matched:
        print("no matching prediction text found", file=sys.stderr)
        sys.exit(1)
    save_json(show_path(slug), show)
    print(f"marked {args.status}")


# -------------------------------------------------------------------- dedup

STOPWORDS = set("""a an the of to and for in on with is are was were be being been
this that these those you your it its as at by or not no so if then than
""".split())


def _keywords(text):
    words = re.findall(r"[a-z0-9']+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 3}


def cmd_dedup(args):
    """Mechanical overlap scan across every mined show's episode titles +
    recorded predictions: surfaces candidate repeats/contradictions to check
    by hand, not a verdict. Token-overlap only, no embeddings/ML dependency."""
    claims = []  # (show, episode, text, keyword-set)
    for state_file in STATE_DIR.glob("*.json"):
        show = load_json(state_file, {"show": state_file.stem, "episodes": {}})
        for ep, data in show["episodes"].items():
            for p in data.get("predictions", []):
                claims.append((show["show"], ep, p["text"], _keywords(p["text"])))

    threshold = args.threshold
    pairs = []
    for i in range(len(claims)):
        for j in range(i + 1, len(claims)):
            a, b = claims[i], claims[j]
            if a[0] == b[0]:
                continue  # same-show repeats aren't cross-show signal
            overlap = a[3] & b[3]
            if not a[3] or not b[3]:
                continue
            score = len(overlap) / min(len(a[3]), len(b[3]))
            if score >= threshold:
                pairs.append({
                    "score": round(score, 2),
                    "shared_terms": sorted(overlap),
                    "a": {"show": a[0], "episode": a[1], "text": a[2]},
                    "b": {"show": b[0], "episode": b[1], "text": b[2]},
                })
    pairs.sort(key=lambda p: -p["score"])
    print(json.dumps(pairs, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("config-get")
    s.add_argument("key")
    s.set_defaults(func=cmd_config_get)

    s = sub.add_parser("config-set")
    s.add_argument("key")
    s.add_argument("value")
    s.set_defaults(func=cmd_config_set)

    s = sub.add_parser("mined")
    s.add_argument("--show", required=True)
    s.set_defaults(func=cmd_mined)

    s = sub.add_parser("record")
    s.add_argument("--show", required=True)
    s.add_argument("--episode", required=True)
    s.add_argument("--date", default="")
    s.add_argument("--findings-path", default="")
    s.add_argument("--predictions-json", default="[]")
    s.set_defaults(func=cmd_record)

    s = sub.add_parser("predictions")
    s.add_argument("--show", default=None)
    s.add_argument("--all", action="store_true", help="include already-checked predictions")
    s.set_defaults(func=cmd_predictions)

    s = sub.add_parser("check-prediction")
    s.add_argument("--show", required=True)
    s.add_argument("--episode", required=True)
    s.add_argument("--text", required=True, help="substring matching the prediction to resolve")
    s.add_argument("--status", required=True, choices=["confirmed", "failed", "stale"])
    s.set_defaults(func=cmd_check_prediction)

    s = sub.add_parser("dedup")
    s.add_argument("--threshold", type=float, default=0.5)
    s.set_defaults(func=cmd_dedup)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
