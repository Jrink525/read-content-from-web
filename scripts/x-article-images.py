#!/usr/bin/env python3
"""Download an X Article's figures in body order and print the markdown mapping.

Usage:
    python3 scripts/x-article-images.py <tweet.json> <article.txt> <slug> [image_dir]

<article.txt> is the block-order extraction that prints `[IMG <mediaId>,...]`
markers (SKILL.md step 1). Files are numbered by occurrence in the body, so
`image/<slug>-<n>.<ext>` in the page follows the article's own layout. Exits 1
when downloaded count differs from marker count, or a mediaId has no URL.
"""
import json
import os
import re
import subprocess
import sys

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def sniff(path):
    head = open(path, "rb").read(16)
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if head.startswith(b"GIF8"):
        return "gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    tweet_path, text_path, slug = sys.argv[1:4]
    out_dir = sys.argv[4] if len(sys.argv) > 4 else "image"
    os.makedirs(out_dir, exist_ok=True)

    article = json.load(open(tweet_path))["tweet"].get("article") or {}
    urls = {}
    for m in article.get("media_entities") or []:
        info = m.get("media_info") or {}
        if info.get("original_img_url"):
            urls[m.get("media_id")] = info["original_img_url"]

    body = open(text_path, encoding="utf-8", errors="ignore").read()
    order = []
    for group in re.findall(r"\[IMG ([0-9,]*)\]", body):
        order.extend(mid.strip() for mid in group.split(",") if mid.strip())

    if not order:
        print("no [IMG] markers in %s: either the article has no inline figures "
              "or step 1 dropped the MEDIA branch" % text_path)
        return 0

    made, missing, failed = [], [], []
    for n, mid in enumerate(order, 1):
        url = urls.get(mid)
        if not url:
            missing.append(mid)
            continue
        dest = None
        for _ in range(3):
            tmp = os.path.join(out_dir, "%s-%d.tmp" % (slug, n))
            subprocess.run(["curl", "-sL", "--max-time", "40", "-A", UA,
                            url, "-o", tmp], check=False)
            real = sniff(tmp) if os.path.exists(tmp) else None
            if real:
                dest = os.path.join(out_dir, "%s-%d.%s" % (slug, n, real))
                os.replace(tmp, dest)
                break
            if os.path.exists(tmp):
                os.remove(tmp)
        if dest:
            made.append((n, mid, dest))
        else:
            failed.append(mid)

    for n, mid, dest in made:
        print("%-5s %-21s %-8d %s" % (n, mid, os.path.getsize(dest), dest))
    for mid in missing:
        print("NO URL  %s" % mid)
    for mid in failed:
        print("FAILED  %s  (3 attempts, header is not an image)" % mid)

    print("\nmarkdown refs (add one ../ per level below the workspace root):")
    for n, mid, dest in made:
        ext = dest.rsplit(".", 1)[-1]
        print("![原文配图，无图说](../image/%s-%d.%s)" % (slug, n, ext))

    print("\nmarkers %d | downloaded %d | no url %d | failed %d"
          % (len(order), len(made), len(missing), len(failed)))
    if len(made) != len(order):
        print("counts disagree: download the missing figures, or drop their "
              "references before writing the page")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
