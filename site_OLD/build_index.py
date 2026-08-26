#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_index.py — Genismo/DUniverse site indexer (PDF + HTML edition)
========================================
Regenerates site/search-index.json AND the ITEMS list inside site/index.html,
scanning the repository folders for PDFs *and* HTML/HTM articles. Run it
whenever you add, remove or replace documents — no AI assistance needed.

USAGE (from the repository root, where Articles.pdf / your .htm files live):

    pip install pypdf          (only once, needed for PDF text extraction)
    python build_index.py              -> incremental: only new/changed files are extracted
    python build_index.py --force      -> re-extract everything from scratch

Then commit & push:  site/search-index.json  and  site/index.html
"""

import json
import re
import sys
import argparse
from pathlib import Path
from html.parser import HTMLParser

try:
    from pypdf import PdfReader
except ImportError:
    print("ERROR: the 'pypdf' library is not installed.")
    print("Run:  pip install pypdf")
    sys.exit(1)

# ---------------------------------------------------------------- config ----

# This script lives INSIDE the "site" folder (genismo/site/build_index.py),
# so the repository root is one level UP from the script's own location.
REPO_ROOT = Path(__file__).resolve().parent.parent
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

# File extensions to index, in addition to PDF
HTML_EXTENSIONS = (".htm", ".html")

# files at repo root that should appear as featured
FEATURED = {"Articles.pdf"}

# Files to always skip when scanning for HTML (site infrastructure,
# not articles) — extend this list if the scanner picks up pages it shouldn't.
HTML_SKIP_NAMES = {
    "index.html", "search.html",
}

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


class _HTMLTextExtractor(HTMLParser):
    """Minimal HTML-to-text extractor using only the Python standard library.

    Strips <script> and <style> content entirely, keeps everything else as
    plain text, and separately captures the <title> tag if present.
    """
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._in_title = False
        self.title = ""
        self._chunks = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._in_title:
            self.title += data
        else:
            self._chunks.append(data)

    def get_text(self) -> str:
        text = " ".join(self._chunks)
        text = re.sub(r"\s+", " ", text).strip()
        return text


def extract_html(html_path: Path):
    """Return (title_or_None, full_text) for an .htm/.html file.

    Tries a few common encodings since many of these files were produced by
    older tools; falls back to permissive decoding rather than crashing.
    """
    raw_bytes = html_path.read_bytes()
    text_content = None
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            text_content = raw_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text_content is None:
        text_content = raw_bytes.decode("utf-8", errors="replace")

    parser = _HTMLTextExtractor()
    parser.feed(text_content)
    parser.close()
    title = parser.title.strip()
    return (title or None), parser.get_text()


def scan_documents():
    """Yield (rel_path_posix, Path, folder, label, kind) for every PDF and
    HTML/HTM article found in FOLDERS. kind is 'pdf' or 'html'."""
    for folder, label in FOLDERS.items():
        base = REPO_ROOT / folder if folder else REPO_ROOT
        if not base.is_dir():
            continue

        for pdf in sorted(base.glob("*.pdf"), key=lambda p: p.name.lower()):
            rel = f"{folder}/{pdf.name}" if folder else pdf.name
            yield rel, pdf, folder, label, "pdf"

        for ext in HTML_EXTENSIONS:
            for page in sorted(base.glob(f"*{ext}"), key=lambda p: p.name.lower()):
                if page.name.lower() in HTML_SKIP_NAMES:
                    continue
                rel = f"{folder}/{page.name}" if folder else page.name
                yield rel, page, folder, label, "html"


# ---------------------------------------------------------------- main ------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="re-extract text of ALL documents (default: only new ones)")
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

    for rel, doc, folder, label, kind in scan_documents():
        prev = old_items.get(rel)

        # text index (incremental unless --force)
        if rel in old_index and not args.force:
            new_index[rel] = old_index[rel]
            kept.append(rel)
            title = prev["title"] if prev else title_from_filename(doc.stem)
        else:
            print(f"  extracting ({kind}): {rel} ...")
            try:
                if kind == "pdf":
                    text = extract_text(doc)
                    html_title = None
                else:
                    html_title = None
                    detected_title, text = extract_html(doc)
                    if detected_title:
                        html_title = detected_title
                if not text:
                    print(f"    WARNING: no text extracted: {rel}")
                new_index[rel] = text
                added.append(rel)
                # Prefer an existing custom title, then the <title> tag (HTML
                # only), then a title derived from the filename.
                if prev:
                    title = prev["title"]
                elif html_title:
                    title = html_title
                else:
                    title = title_from_filename(doc.stem)
            except Exception as e:
                print(f"    ERROR extracting {rel}: {e}")
                new_index[rel] = ""
                failed.append(rel)
                title = prev["title"] if prev else title_from_filename(doc.stem)

        new_items.append({
            "path": rel,
            "folder": folder,
            "folder_label": label,
            "title": title,
            "size": human_size(doc.stat().st_size),
            "featured": rel in FEATURED,
            "kind": kind,
        })

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
    n_pdf = sum(1 for it in new_items if it["kind"] == "pdf")
    n_html = sum(1 for it in new_items if it["kind"] == "html")
    print()
    print("=" * 60)
    print(f"Documents listed .......... {len(new_items)}  ({n_pdf} PDF, {n_html} HTML)")
    print(f"New files indexed ......... {len(added)}")
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
