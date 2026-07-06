#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_index.py — Genismo site indexer  (v1.0)
=============================================
Gera items.json e search-index.json a partir dos artigos HTML e PDFs do
repositório Genismo. Rode sempre que adicionar/alterar artigos — sem
precisar de IA.

USO (na raiz do repositório, onde está o index.html):

    pip install pypdf            (apenas uma vez, para indexar os PDFs)
    python build_index.py                -> gera tudo
    python build_index.py --no-pdf      -> pula os PDFs (mais rápido)

Depois faça commit & push de:  items.json  e  search-index.json
"""

import json
import re
import sys
import html
import argparse
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
ITEMS_JSON = REPO_ROOT / "items.json"
INDEX_JSON = REPO_ROOT / "search-index.json"

# Máximo de caracteres de texto guardados por artigo no índice de busca
MAX_TEXT = 18000

# ------------------------------------------------------------- categorias ---
# página de listagem -> (id, nome exibido)
CATEGORIES = [
    ("genismo2.htm",     "genismo",    "Genismo"),
    ("genetica2.htm",    "genetica",   "Genética e Evolução"),
    ("psicologia2.htm",  "psicologia", "Psicologia Evolutiva"),
    ("memetica2.htm",    "memetica",   "Memética"),
    ("logica2.htm",      "logica",     "Lógica e Método Científico"),
    ("filosofia2.htm",   "metaetica",  "Meta-Ética-Científica"),
    ("religioes2.htm",   "religiao",   "Religiões e Ateísmo"),
    ("englishtexts.htm", "english",    "English Texts"),
]

# PDFs na raiz: arquivo -> título exibido (edite à vontade)
PDFS = {
    "A Navalha de Jocax.pdf":  "A Navalha de Jocax",
    "GLIV.pdf":                "GLIV — Livro do Genismo",
    "JesusNunca.pdf":          "Jesus Nunca Existiu",
    "JesusNunca2.pdf":         "Jesus Nunca Existiu (v2)",
    "Jocax.pdf":               "Textos de Jocax",
    "Princ_Pub_Jocax.pdf":     "Principais Publicações de Jocax",
    "jocaxianArticles_2.pdf":  "Jocaxian Articles (English)",
    "Hubble.pdf":              "Hubble",
    "HU_DOC08.pdf":            "HU DOC 08",
    "Amazon_River.pdf":        "Amazon River",
}

# hrefs/títulos de navegação que NÃO são artigos
SKIP_TITLES = re.compile(r"^(voltar|anterior|pr[óo]ximo|textos?\b|>>|\.\.)", re.I)


# ---------------------------------------------------------------- helpers ---

def read_latin(path: Path) -> str:
    """Lê arquivos antigos (latin-1 / cp1252) sem quebrar."""
    raw = path.read_bytes()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace")


def strip_html(text: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def norm(text: str) -> str:
    """minúsculas + sem acentos (busca insensível a acentos)."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.lower()


def human_size(nbytes: int) -> str:
    kb = nbytes / 1024
    if kb < 1000:
        return f"{round(kb)} KB"
    return f"{kb / 1024:.1f} MB"


# ------------------------------------------------------------- extração -----

def parse_listing(page: Path):
    """Extrai (href, título) da página de listagem de uma categoria."""
    data = read_latin(page)
    out, seen = [], set()
    for href, txt in re.findall(
            r'<a\s+[^>]*href="([^"]+\.html?)"[^>]*>(.*?)</a>', data, re.I | re.S):
        title = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", txt))).strip()
        href = href.strip()
        if len(title) < 4 or SKIP_TITLES.search(title):
            continue
        if "://" in href or href.startswith("mailto"):
            continue
        if href in seen:
            continue
        seen.add(href)
        out.append((href, title))
    return out


def build():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pdf", action="store_true", help="não indexa PDFs")
    args = ap.parse_args()

    # mapa case-insensitive -> nome real do arquivo (GitHub Pages diferencia
    # maiúsculas/minúsculas; links antigos às vezes estão em minúsculas)
    real_names = {p.name.lower(): p.name for p in REPO_ROOT.iterdir() if p.is_file()}

    items, index = [], []
    total_articles = 0

    for listing, cat_id, cat_name in CATEGORIES:
        page = REPO_ROOT / listing
        if not page.exists():
            print(f"  AVISO: {listing} não encontrado — categoria pulada")
            continue
        arts = parse_listing(page)
        print(f"[{cat_name}] {len(arts)} artigos")
        for href, title in arts:
            href = real_names.get(href.lower(), href)   # corrige o case
            f = REPO_ROOT / href
            entry = {"href": href, "title": title, "cat": cat_id, "catName": cat_name}
            if f.exists():
                text = strip_html(read_latin(f))[:MAX_TEXT]
                index.append({"href": href, "title": title, "cat": cat_name,
                              "text": text})
            else:
                print(f"    aviso: {href} listado mas ausente no repositório")
            items.append(entry)
            total_articles += 1

    # ------------------------------------------------------------- PDFs -----
    pdf_items = []
    if not args.no_pdf:
        try:
            from pypdf import PdfReader
        except ImportError:
            print("AVISO: pypdf não instalado (pip install pypdf) — PDFs pulados")
            PdfReader = None
        if PdfReader:
            for fname, title in PDFS.items():
                f = REPO_ROOT / fname
                if not f.exists():
                    print(f"  aviso: {fname} não encontrado")
                    continue
                try:
                    reader = PdfReader(str(f))
                    text = " ".join((p.extract_text() or "") for p in reader.pages)
                    text = re.sub(r"\s+", " ", text).strip()[:MAX_TEXT]
                except Exception as e:
                    print(f"  erro lendo {fname}: {e}")
                    text = ""
                pdf_items.append({"href": fname, "title": title, "cat": "pdf",
                                  "catName": "PDFs", "size": human_size(f.stat().st_size)})
                index.append({"href": fname, "title": title, "cat": "PDFs",
                              "text": text})
            print(f"[PDFs] {len(pdf_items)} arquivos")

    # ----------------------------------------------------------- gravação ---
    payload = {"generated": True, "categories":
               [{"id": c, "name": n} for _, c, n in CATEGORIES] +
               ([{"id": "pdf", "name": "PDFs"}] if pdf_items else []),
               "items": items + pdf_items}
    ITEMS_JSON.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    INDEX_JSON.write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")

    print(f"\nOK: {total_articles} artigos + {len(pdf_items)} PDFs")
    print(f"  -> {ITEMS_JSON.name}  ({human_size(ITEMS_JSON.stat().st_size)})")
    print(f"  -> {INDEX_JSON.name}  ({human_size(INDEX_JSON.stat().st_size)})")
    print("\nAgora faça commit & push de items.json e search-index.json")


if __name__ == "__main__":
    build()
