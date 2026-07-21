#!/usr/bin/env python3
"""Resolve any podcast URL -> RSS feed + episode list + transcript URLs.

Works for ANY show, not one hardcoded feed.

  python3 resolve.py "<url-or-show-name>" [--episode-id ID] [--limit N] [--download DIR]

Handles:
  podcasts.apple.com/<cc>/podcast/<slug>/id<SHOW>?i=<EPISODE>
  open.spotify.com/show/... (falls back to name search)
  a direct RSS/XML url
  a bare show name (searched via iTunes)
  youtube.com/watch?v=... or youtu.be/... (single video)
  youtube.com/@handle, /channel/UC..., /playlist?list=... (multiple videos, needs --limit)

YouTube requires yt-dlp on PATH (`brew install yt-dlp` / `pipx install yt-dlp`).
There is no RSS feed for YouTube — each video is fetched directly via yt-dlp:
metadata via `-J --skip-download`, transcript via auto-captions (falls back to
manual subs if present). No podcast:transcript tag equivalent exists, so
`have` transcript count reflects whichever videos actually have an en/en-orig
caption track — some videos (esp. very new ones) may have none yet.
"""
import json, re, sys, os, subprocess, urllib.request, urllib.parse
import xml.etree.ElementTree as ET

PNS = {"podcast": "https://podcastindex.org/namespace/1.0"}
UA = {"User-Agent": "Mozilla/5.0 (compatible; podcast-skill/1.0)"}


def get(url, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def itunes(params):
    return json.loads(get("https://itunes.apple.com/" + params).decode("utf-8", "replace"))


def is_youtube(src):
    return bool(re.search(r"youtube\.com|youtu\.be", src))


def yt_dlp_json(url, extra=()):
    cmd = ["yt-dlp", "--skip-download", "--no-warnings", "-J", *extra, url]
    try:
        raw = subprocess.run(cmd, capture_output=True, check=True, timeout=60).stdout
    except FileNotFoundError:
        sys.exit("yt-dlp not found on PATH. Install with `brew install yt-dlp`.")
    except subprocess.CalledProcessError as ex:
        sys.exit(f"yt-dlp failed for {url}: {ex.stderr.decode('utf-8', 'replace')[:400]}")
    return json.loads(raw)


def yt_list_videos(src, limit):
    """Single video URL -> [that video]. Channel/@handle/playlist -> up to `limit`
    videos, newest first, via yt-dlp's flat-playlist mode (fast, no per-video fetch)."""
    if re.search(r"[?&]v=|youtu\.be/", src):
        d = yt_dlp_json(src)
        return [{"id": d["id"], "title": d.get("title", ""),
                  "date": _yt_date(d.get("upload_date"))}]
    d = yt_dlp_json(src, extra=["--flat-playlist", "--playlist-end", str(limit)])
    entries = d.get("entries") or [d]
    out = []
    for e in entries[:limit]:
        if not e or not e.get("id"):
            continue
        out.append({"id": e["id"], "title": e.get("title", ""),
                     "date": _yt_date(e.get("upload_date"))})
    return out


def _yt_date(upload_date):
    if not upload_date or len(upload_date) != 8:
        return ""
    return f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"


def yt_transcript(video_id, workdir):
    """Auto-captions preferred (near-universal); falls back to manual subs.
    Returns flattened text, or None if neither track exists."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    base = os.path.join(workdir, video_id)
    for sub_flag in ("--write-auto-sub", "--write-sub"):
        cmd = ["yt-dlp", "--skip-download", "--no-warnings", sub_flag,
               "--sub-lang", "en.*", "--sub-format", "vtt",
               "-o", base + ".%(ext)s", url]
        subprocess.run(cmd, capture_output=True, timeout=120)
        for fname in os.listdir(workdir):
            if fname.startswith(os.path.basename(base)) and fname.endswith(".vtt"):
                path = os.path.join(workdir, fname)
                text = flatten_transcript_file(path)
                os.remove(path)
                return text
    return None


def flatten_transcript_file(path):
    with open(path, "rb") as f:
        raw = f.read()
    txt = raw.decode("utf-8", "replace")
    lines = [l for l in txt.splitlines()
             if l.strip() and "-->" not in l and not l.strip().isdigit()
             and not l.startswith(("WEBVTT", "NOTE", "Kind:", "Language:"))]
    lines = [re.sub(r"<[^>]+>", "", l) for l in lines]
    return "\n".join(dict.fromkeys(lines))


def run_youtube(src, limit, dl):
    videos = yt_list_videos(src, limit)
    print(f"show: (YouTube) {src}")
    print(f"episodes: {len(videos)} shown\n")

    if not dl:
        for i, v in enumerate(videos):
            print(f"{i:2d} {v['date']} | {v['title'][:64]}")
        print("\n! Pass --download DIR to fetch auto-caption transcripts via yt-dlp.")
        return

    os.makedirs(dl, exist_ok=True)
    man = []
    for i, v in enumerate(videos):
        slug = re.sub(r"[^a-z0-9]+", "-", v["title"].lower()).strip("-")[:40]
        p = os.path.join(dl, f"{i:02d}-{slug}.txt")
        text = yt_transcript(v["id"], dl)
        if text is None:
            print(f"  {i:2d} FAIL no en captions -> {v['title'][:40]}")
            continue
        open(p, "w").write(text)
        man.append({"title": v["title"], "date": v["date"], "path": os.path.abspath(p),
                     "words": len(text.split()), "target": i == 0, "video_id": v["id"]})
        print(f"  {len(text.split()):6d}w -> {p}")
    json.dump(man, open(os.path.join(dl, "manifest.json"), "w"), indent=1)
    print(f"\nmanifest: {os.path.join(dl, 'manifest.json')}  ({len(man)} files)")


def resolve_source(src):
    """-> (feed_url, show_id|None, episode_id|None, show_name)"""
    # Direct RSS
    if re.search(r"\.(xml|rss)(\?|$)", src) or "/feed" in src or src.startswith("http") and "podcasts.apple" not in src and "spotify" not in src and "youtube" not in src:
        if src.startswith("http") and not re.search(r"apple|spotify|youtu", src):
            return src, None, None, "(direct feed)"

    show_id = ep_id = None
    m = re.search(r"/id(\d+)", src)
    if m:
        show_id = m.group(1)
    m = re.search(r"[?&]i=(\d+)", src)
    if m:
        ep_id = m.group(1)

    if not show_id:
        # Spotify or bare name -> search iTunes by name
        name = src
        if "spotify.com" in src:
            slug = re.search(r"/show/[^/?]+", src)
            print("! Spotify has no open API; searching iTunes by name instead.", file=sys.stderr)
            name = input("Show name: ") if sys.stdin.isatty() else src
        q = urllib.parse.urlencode({"term": name, "entity": "podcast", "limit": 5})
        res = itunes("search?" + q).get("results", [])
        if not res:
            sys.exit(f"No podcast found for: {name}")
        show_id = str(res[0]["collectionId"])
        print(f"! Matched show: {res[0]['collectionName']}", file=sys.stderr)

    look = itunes(f"lookup?id={show_id}&entity=podcast").get("results", [])
    if not look:
        sys.exit(f"iTunes lookup failed for show id {show_id}")
    feed = look[0].get("feedUrl")
    name = look[0].get("collectionName", "?")
    if not feed:
        sys.exit(f"Show '{name}' exposes no feedUrl (Apple-exclusive?).")
    return feed, show_id, ep_id, name


def episode_title_for_id(show_id, ep_id):
    """Apple ?i= ids resolve via the SHOW lookup with entity=podcastEpisode."""
    if not (show_id and ep_id):
        return None
    for e in itunes(f"lookup?id={show_id}&entity=podcastEpisode&limit=200").get("results", []):
        if str(e.get("trackId")) == str(ep_id):
            return e.get("trackName")
    return None


def parse_feed(xml_bytes, limit):
    ch = ET.fromstring(xml_bytes).find("channel")
    out = []
    for it in ch.findall("item")[:limit]:
        tr = it.find("podcast:transcript", PNS)
        out.append({
            "title": (it.findtext("title") or "").strip(),
            "date": (it.findtext("pubDate") or "")[:16],
            "transcript": tr.get("url") if tr is not None else None,
        })
    return out


def flatten_transcript(url):
    raw = get(url)
    if url.endswith(".json") or raw[:1] in (b"{", b"["):
        d = json.loads(raw)
        segs = d.get("segments") or d.get("results") or []
        if segs:
            return "\n".join(s.get("body") or s.get("text", "") for s in segs)
        return json.dumps(d)
    txt = raw.decode("utf-8", "replace")
    if "WEBVTT" in txt[:64] or "-->" in txt[:400]:  # vtt/srt
        lines = [l for l in txt.splitlines()
                 if l.strip() and "-->" not in l and not l.strip().isdigit()
                 and not l.startswith(("WEBVTT", "NOTE", "Kind:", "Language:"))]
        return "\n".join(dict.fromkeys(lines))
    return txt


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    src = a[0]
    limit = int(a[a.index("--limit") + 1]) if "--limit" in a else 12
    dl = a[a.index("--download") + 1] if "--download" in a else None

    if is_youtube(src):
        run_youtube(src, limit, dl)
        return

    feed, show_id, ep_id, name = resolve_source(src)
    print(f"show: {name}\nfeed: {feed}")

    target = episode_title_for_id(show_id, ep_id)
    if ep_id:
        print(f"episode i={ep_id} -> {target or 'UNRESOLVED (falling back to newest)'}")

    eps = parse_feed(get(feed), limit)
    have = sum(1 for e in eps if e["transcript"])
    print(f"episodes: {len(eps)} shown, {have} with embedded transcripts\n")
    for i, e in enumerate(eps):
        mark = "<<< TARGET" if target and e["title"] == target else ""
        print(f"{i:2} {'OK ' if e['transcript'] else '-- '} {e['date']} | {e['title'][:64]} {mark}")

    if not have:
        print("\n! No podcast:transcript tags. Fall back, in order:"
              "\n  1. show's own site (google '<title> transcript')"
              "\n  2. yt-dlp --write-auto-sub --skip-download --sub-lang en --sub-format vtt <yt-url>"
              "\n  3. uv run --with openai-whisper whisper ep.mp3 --model small --output_format txt")
        return

    if dl:
        os.makedirs(dl, exist_ok=True)
        man = []
        for i, e in enumerate(eps):
            if not e["transcript"]:
                continue
            slug = re.sub(r"[^a-z0-9]+", "-", e["title"].lower()).strip("-")[:40]
            p = os.path.join(dl, f"{i:02d}-{slug}.txt")
            try:
                t = flatten_transcript(e["transcript"])
                open(p, "w").write(t)
                man.append({"title": e["title"], "date": e["date"],
                            "path": os.path.abspath(p), "words": len(t.split()),
                            "target": bool(target and e["title"] == target)})
                print(f"  {len(t.split()):6d}w -> {p}")
            except Exception as ex:
                print(f"  FAIL {e['title'][:40]}: {ex}")
        json.dump(man, open(os.path.join(dl, "manifest.json"), "w"), indent=1)
        print(f"\nmanifest: {os.path.join(dl, 'manifest.json')}  ({len(man)} files)")


if __name__ == "__main__":
    main()
