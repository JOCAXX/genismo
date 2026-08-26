#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_root_index.py — Genismo ROOT-level indexer
========================================
Regenerates the root-level items.json and search-index.json — the files
ACTUALLY used by genismo/index.html (the live homepage). This is a
different, separate index from the one under site/ (which follows the
older DUniverse-style format and is used only by site/index.html and
site/search.html).

Run this from the genismo repository ROOT (same folder as index.html,
items.json, search-index.json).

USAGE:
    pip install pypdf          (only once, needed for PDF text extraction)
    python build_root_index.py              -> incremental: only new/changed files are extracted
    python build_root_index.py --force      -> re-extract everything from scratch

Then commit & push: items.json and search-index.json (at the repo root).
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
    PdfReader = None  # PDFs are optional here; most root content is .htm

# ---------------------------------------------------------------- config ----

ROOT = Path(__file__).resolve().parent
ITEMS_JSON = ROOT / "items.json"
SEARCH_JSON = ROOT / "search-index.json"

CATEGORIES = [
    {"id": "genismo",   "name": "Genismo"},
    {"id": "genetica",  "name": "Genética e Evolução"},
    {"id": "psicologia","name": "Psicologia Evolutiva"},
    {"id": "memetica",  "name": "Memética"},
    {"id": "logica",    "name": "Lógica e Método Científico"},
    {"id": "metaetica", "name": "Meta-Ética-Científica"},
    {"id": "religiao",  "name": "Religiões e Ateísmo"},
    {"id": "english",   "name": "English Texts"},
    {"id": "pdf",       "name": "PDFs"},
]
CAT_NAME = {c["id"]: c["name"] for c in CATEGORIES}
CAT_IDS = set(CAT_NAME)

# Filename-prefix patterns used to guess the category of files that are NOT
# already present in the existing items.json (i.e. genuinely new files).
# Order matters: checked top to bottom, first match wins.
PATTERN_RULES = [
    (re.compile(r'^genismo',    re.I), "genismo"),
    (re.compile(r'^genetica',   re.I), "genetica"),
    (re.compile(r'^psicologia', re.I), "psicologia"),
    (re.compile(r'^memetica',   re.I), "memetica"),
    (re.compile(r'^logica',     re.I), "logica"),
    (re.compile(r'^meta',       re.I), "metaetica"),
    (re.compile(r'^religia',    re.I), "religiao"),
    (re.compile(r'^religioes',  re.I), "religiao"),
    (re.compile(r'^english',    re.I), "english"),
]

# Manual overrides for files whose category can't be guessed from the
# filename pattern above. Add more entries here as needed, then re-run
# with --force (or just add the new filename — incremental runs already
# pick up brand-new files automatically).
MANUAL_CATEGORY_OVERRIDES = {
    "Maleficios_Deus.htm": "religiao",
}

# Default category for genuinely unrecognized new files (printed as a
# warning so it can be fixed manually afterwards, either by adding an
# entry to MANUAL_CATEGORY_OVERRIDES above or editing items.json directly).
FALLBACK_CATEGORY = "genismo"

# Site-infrastructure files at the root that must NOT be treated as articles.
SKIP_NAMES = {
    "index.html", "index (2).html", "index - Copia (2).html", "index - Copia.html",
    "noindex.html", "busca.html",
}

HTML_EXTENSIONS = (".htm", ".html")

# ---------------------------------------------------------------- helpers ---

def human_size(nbytes: int) -> str:
    kb = nbytes / 1024
    if kb < 1000:
        return f"{round(kb)} KB"
    mb = kb / 1024
    return f"{mb:.1f} MB"


def title_from_filename(stem: str) -> str:
    s = re.sub(r"[_\-]+", " ", stem)
    s = re.sub(r"\s+", " ", s).strip()
    words = []
    for w in s.split(" "):
        words.append(w if any(c.isupper() for c in w) or w.isdigit() else w.capitalize())
    return " ".join(words)


def guess_category(filename: str) -> str:
    if filename in MANUAL_CATEGORY_OVERRIDES:
        return MANUAL_CATEGORY_OVERRIDES[filename]
    if filename.lower().endswith(".pdf"):
        return "pdf"
    for pattern, cat in PATTERN_RULES:
        if pattern.match(filename):
            return cat
    return None  # unrecognized — caller decides fallback + warning


class _HTMLTextExtractor(HTMLParser):
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


def extract_pdf(pdf_path: Path) -> str:
    if PdfReader is None:
        return ""
    reader = PdfReader(str(pdf_path))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            pass
    text = " ".join(parts)
    return re.sub(r"\s+", " ", text).strip()


def scan_files():
    for f in sorted(ROOT.iterdir(), key=lambda p: p.name.lower()):
        if not f.is_file():
            continue
        if f.name in SKIP_NAMES:
            continue
        ext = f.suffix.lower()
        if ext in HTML_EXTENSIONS:
            yield f, "html"
        elif ext == ".pdf":
            yield f, "pdf"


# ---------------------------------------------------------------- main ------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="re-extract text of ALL documents (default: only new ones)")
    args = ap.parse_args()

    old_items_by_href = {}
    if ITEMS_JSON.is_file():
        try:
            old_data = json.loads(ITEMS_JSON.read_text(encoding="utf-8"))
            for it in old_data.get("items", []):
                old_items_by_href[it["href"]] = it
        except Exception:
            print("WARNING: could not read existing items.json; rebuilding all.")

    old_text_by_href = {}
    if SEARCH_JSON.is_file() and not args.force:
        try:
            old_search = json.loads(SEARCH_JSON.read_text(encoding="utf-8"))
            for e in old_search:
                old_text_by_href[e["href"]] = e
        except Exception:
            print("WARNING: could not read existing search-index.json; rebuilding all.")

    new_items = []
    new_search = []
    added, kept, failed, uncategorized = [], [], [], []

    for f, kind in scan_files():
        href = f.name
        prev_item = old_items_by_href.get(href)

        # ---- category
        if prev_item and not args.force:
            cat = prev_item["cat"]
        else:
            cat = guess_category(href)
            if cat is None:
                cat = FALLBACK_CATEGORY
                uncategorized.append(href)

        # ---- text + title (incremental unless --force)
        if href in old_text_by_href and not args.force:
            entry = old_text_by_href[href]
            text = entry["text"]
            title = prev_item["title"] if prev_item else (entry.get("title") or title_from_filename(f.stem))
            kept.append(href)
        else:
            print(f"  extracting ({kind}): {href} ...")
            try:
                if kind == "pdf":
                    text = extract_pdf(f)
                    html_title = None
                else:
                    html_title, text = extract_html(f)
                if not text:
                    print(f"    WARNING: no text extracted: {href}")
                title = prev_item["title"] if prev_item else (html_title or title_from_filename(f.stem))
                added.append(href)
            except Exception as e:
                print(f"    ERROR extracting {href}: {e}")
                text = ""
                title = prev_item["title"] if prev_item else title_from_filename(f.stem)
                failed.append(href)

        item = {
            "href": href,
            "title": title,
            "cat": cat,
            "catName": CAT_NAME.get(cat, cat),
        }
        if kind == "pdf":
            item["size"] = human_size(f.stat().st_size)
        new_items.append(item)

        new_search.append({
            "href": href,
            "title": title,
            "cat": CAT_NAME.get(cat, cat),
            "text": text,
        })

    removed = [h for h in old_items_by_href if h not in {it["href"] for it in new_items}]

    # ---- write items.json
    items_payload = {
        "generated": True,
        "categories": CATEGORIES,
        "items": new_items,
    }
    ITEMS_JSON.write_text(json.dumps(items_payload, ensure_ascii=False), encoding="utf-8")

    # ---- write search-index.json
    SEARCH_JSON.write_text(json.dumps(new_search, ensure_ascii=False), encoding="utf-8")

    # ---- summary
    print()
    print("=" * 60)
    print(f"Documents listed .......... {len(new_items)}")
    print(f"New files indexed .......... {len(added)}")
    for p in added:
        print(f"    + {p}")
    if removed:
        print(f"Removed (file deleted) .... {len(removed)}")
        for p in removed:
            print(f"    - {p}")
    if failed:
        print(f"FAILED extraction .......... {len(failed)}")
        for p in failed:
            print(f"    ! {p}")
    if uncategorized:
        print(f"UNCATEGORIZED (used '{FALLBACK_CATEGORY}', please verify) .. {len(uncategorized)}")
        for p in uncategorized:
            print(f"    ? {p}")
    print(f"Reused from old index ..... {len(kept)}")
    print("=" * 60)
    print("Updated: items.json  and  search-index.json  (repo root)")
    print("Now commit & push these two files.")


if __name__ == "__main__":
    main()
