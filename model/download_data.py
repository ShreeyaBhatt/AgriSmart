#!/usr/bin/env python3
"""Download a PlantVillage subset for training.

Source: the public ``spMohanty/PlantVillage-Dataset`` GitHub repo
(``raw/color/<Class>/*.JPG``) — CC0, no auth needed. One Contents-API call per
class lists the files; images are then fetched in parallel from
``raw.githubusercontent.com``.

    python model/download_data.py --out data/plantvillage --per-class 150

Falls back gracefully: ``--data-dir`` uses an existing ImageFolder instead;
if the network is unavailable and neither exists, the caller can still train on
whatever is in ``data/samples/leaves`` (not meaningful, but exercises the code).
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

from labels import DEFAULT_CLASSES  # noqa: E402  (run as a script from model/)

REPO = "spMohanty/PlantVillage-Dataset"
BRANCH = "master"
CONTENTS = "https://api.github.com/repos/%s/contents/raw/color/{cls}?ref=%s" % (REPO, BRANCH)
RAW = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/raw/color/{{cls}}/{{name}}"
SAMPLE_DIR = Path(__file__).resolve().parents[1] / "data" / "samples" / "leaves"


def _headers() -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "User-Agent": "AgriSmart-AI/1.0"}
    if os.getenv("GITHUB_TOKEN"):
        h["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    return h


def list_class_files(client: httpx.Client, cls: str) -> list[str]:
    for attempt in range(4):
        r = client.get(CONTENTS.format(cls=cls), headers=_headers())
        if r.status_code == 200:
            return [e["name"] for e in r.json() if e.get("type") == "file"]
        if r.status_code in (403, 429):  # rate limited
            wait = 20 * (attempt + 1)
            print(f"  rate limited on {cls}; sleeping {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        r.raise_for_status()
    raise RuntimeError(f"could not list files for {cls}")


def download_one(client: httpx.Client, cls: str, name: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return True
    try:
        r = client.get(RAW.format(cls=cls, name=name), timeout=30)
        r.raise_for_status()
        dest.write_bytes(r.content)
        return True
    except httpx.HTTPError as exc:
        print(f"  failed {cls}/{name}: {exc}", file=sys.stderr)
        return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("data/plantvillage"))
    ap.add_argument("--per-class", type=int, default=150)
    ap.add_argument("--classes", nargs="*", default=list(DEFAULT_CLASSES))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    random.seed(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    total_ok = 0
    with httpx.Client(follow_redirects=True) as client:
        for cls in args.classes:
            cls_dir = args.out / cls
            cls_dir.mkdir(parents=True, exist_ok=True)
            names = list_class_files(client, cls)
            if not names:
                print(f"! {cls}: no files listed", file=sys.stderr)
                continue
            pick = random.sample(names, min(args.per_class, len(names)))
            ok = 0
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futs = {pool.submit(download_one, client, cls, n, cls_dir / n): n for n in pick}
                for fut in as_completed(futs):
                    ok += bool(fut.result())
            total_ok += ok
            print(f"  {cls:52s} {ok:4d}/{len(pick)}")
            # keep one image per class as a bundled demo sample
            first = next((p for p in sorted(cls_dir.iterdir()) if p.is_file()), None)
            if first:
                (SAMPLE_DIR / f"{cls}.jpg").write_bytes(first.read_bytes())

    print(f"\nDone: {total_ok} images in {args.out}")
    if total_ok == 0:
        sys.exit("No images downloaded — check your connection or pass --data-dir to train.py")


if __name__ == "__main__":
    main()
