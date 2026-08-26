#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_index.py — DUniverse site indexer
========================================
Regenerates site/search-index.json AND the ITEMS list inside site/index.html,
scanning the repository folders for PDFs. Run it whenever you add, remove or
replace PDFs — no AI assistance needed.

USAGE (from the repository root, where Articles.pdf lives):

    pip install pypdf          (only once)
    python build_index.py              -> incremental: only new/changed PDFs are extracted
    python build_index.py --force      -> re-extract everything from scratch

Then commit & push:  site/search-index.json  and  site/index.html
"""

import json
import re
import sys
import argparse
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    print("ERROR: the 'pypdf' library is not installed.")
    print("Run:  pip install pypdf")
    sys.exit(1)

# ---------------------------------------------------------------- config ----

REPO_ROOT = Path(__file__).resolve().parent
SITE_DIR = REPO_ROOT / "site"
INDEX_JSON = SITE_DIR / "search-index.json"
INDEX_HTML = SITE_DIR / "index.html"

# folder -> label shown on the site ("" = repository root)
FOLDERS = {
    "": "Main Article",
    "Todos": "Full Archive",
    "Novos": "Recent Articles",
    "Shorts": "Short Texts & AI Reviews",
    "Abstract": "Abstracts",
    "Entrevistas": "Interviews",
}

# files at repo root that should appear as featured
FEATURED = {"Articles.pdf"}

# ---------------------------------------------------------------- helpers ---

def human_size(nbytes: int) -> str:
    """299 KB / 1.8 MB — same style used by the site."""
    kb = nbytes / 1024
    if kb < 1000:
        return f"{round(kb)} KB"
    mb = kb / 1024
    return f"{mb:.1f} MB"


def title_from_filename(stem: str) -> str:
    """DUT_AI_1_ENG -> 'DUT AI 1 ENG'; jocaxians-train -> 'Jocaxians Train'."""
    s = re.sub(r"[_\-]+", " ", stem)
    s = re.sub(r"\s+", " ", s).strip()
    words = []
    for w in s.split(" "):
        # keep acronyms / codes as-is; capitalize normal lowercase words
        words.append(w if any(c.isupper() for c in w) or w.isdigit() else w.capitalize())
    return " ".join(words)


def extract_text(pdf_path: Path) -> str:
    """Extract and normalize the full text of a PDF."""
    reader = PdfReader(str(pdf_path))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            pass  # skip unreadable pages, keep going
    text = " ".join(parts)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def scan_pdfs():
    """Yield (rel_path_posix, Path, folder, label) for every PDF in FOLDERS."""
    for folder, label in FOLDERS.items():
        base = REPO_ROOT / folder if folder else REPO_ROOT
        if not base.is_dir():
            continue
        for pdf in sorted(base.glob("*.pdf"), key=lambda p: p.name.lower()):
            rel = f"{folder}/{pdf.name}" if folder else pdf.name
            yield rel, pdf, folder, label


# ---------------------------------------------------------------- main ------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="re-extract text of ALL PDFs (default: only new ones)")
    args = ap.parse_args()

    if not INDEX_HTML.is_file():
        print(f"ERROR: {INDEX_HTML} not found. Run this script from the repo root.")
        sys.exit(1)

    # ---- load existing data (to preserve custom titles + skip re-extraction)
    old_index = {}
    if INDEX_JSON.is_file() and not args.force:
        try:
            old_index = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
        except Exception:
            print("WARNING: could not read existing search-index.json; rebuilding all.")

    html = INDEX_HTML.read_text(encoding="utf-8")
    m = re.search(r"const ITEMS = (\[.*?\]);", html, flags=re.DOTALL)
    if not m:
        print("ERROR: could not find 'const ITEMS = [...];' inside site/index.html")
        sys.exit(1)
    old_items = {it["path"]: it for it in json.loads(m.group(1))}

    # ---- scan folders
    new_index = {}
    new_items = []
    added, kept, failed = [], [], []

    for rel, pdf, folder, label in scan_pdfs():
        # ITEMS entry (preserve custom title if it already existed)
        prev = old_items.get(rel)
        title = prev["title"] if prev else title_from_filename(pdf.stem)
        new_items.append({
            "path": rel,
            "folder": folder,
            "folder_label": label,
            "title": title,
            "size": human_size(pdf.stat().st_size),
            "featured": rel in FEATURED,
        })

        # text index (incremental unless --force)
        if rel in old_index:
            new_index[rel] = old_index[rel]
            kept.append(rel)
        else:
            print(f"  extracting: {rel} ...")
            try:
                text = extract_text(pdf)
                if not text:
                    print(f"    WARNING: no text extracted (scanned image PDF?): {rel}")
                new_index[rel] = text
                added.append(rel)
            except Exception as e:
                print(f"    ERROR extracting {rel}: {e}")
                new_index[rel] = ""
                failed.append(rel)

    removed = [p for p in old_items if p not in {it["path"] for it in new_items}]

    # ---- write search-index.json
    INDEX_JSON.write_text(
        json.dumps(new_index, ensure_ascii=False),
        encoding="utf-8",
    )

    # ---- rewrite ITEMS inside index.html
    items_js = json.dumps(new_items, ensure_ascii=False)
    html = html[:m.start(1)] + items_js + html[m.end(1):]
    INDEX_HTML.write_text(html, encoding="utf-8")

    # ---- summary
    print()
    print("=" * 60)
    print(f"Documents listed .......... {len(new_items)}")
    print(f"New PDFs indexed .......... {len(added)}")
    for p in added:
        print(f"    + {p}")
    if removed:
        print(f"Removed (file deleted) .... {len(removed)}")
        for p in removed:
            print(f"    - {p}")
    if failed:
        print(f"FAILED extraction ......... {len(failed)}  (indexed with empty text)")
        for p in failed:
            print(f"    ! {p}")
    print(f"Reused from old index ..... {len(kept)}")
    print("=" * 60)
    print("Updated: site/search-index.json  and  site/index.html")
    print("Now commit & push these two files.")


if __name__ == "__main__":
    main()
