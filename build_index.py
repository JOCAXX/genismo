#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_index.py — Gerador do índice de busca do site Genismo
=============================================================
Adaptado do fluxo do DUniverse para o Genismo (jocaxx.github.io/genismo).

O que ele faz:
  1. Lê o items.json (a lista oficial de artigos, títulos e categorias).
  2. Para cada item, abre o arquivo local (.htm/.html ou .pdf) e extrai o texto.
  3. Gera o search-index.json no formato que o index.html espera:
       [ { "href": ..., "title": ..., "cat": <nome da categoria>, "text": ... } ]

Como usar:
  1. Coloque este arquivo na RAIZ do repositório genismo (junto do items.json).
  2. Abra o terminal (cmd) nessa pasta e rode:
        python build_index.py
  3. Ele cria/atualiza o search-index.json na mesma pasta.
  4. Commit + push pelo GitHub Desktop, como de costume.

Requisito para PDFs (só na primeira vez):
        pip install pypdf
  (Se o pypdf não estiver instalado, os .htm são indexados normalmente
   e os PDFs são apenas pulados, com aviso.)
"""

import json
import os
import re
import sys
from html.parser import HTMLParser

# ----------------------------- configurações -----------------------------

ITEMS_FILE  = "items.json"          # entrada: lista de artigos
OUTPUT_FILE = "search-index.json"   # saída: índice de busca
MAX_TEXT    = 18000                 # nº máximo de caracteres de texto por artigo

# Tags de HTML cujo conteúdo NÃO deve entrar no índice
SKIP_TAGS = {"script", "style", "head", "title", "noscript"}

# ------------------------- extração de texto: HTML -----------------------

class TextExtractor(HTMLParser):
    """Extrai apenas o texto visível de um arquivo HTML."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            self.parts.append(data)

def read_html_text(path):
    """Lê um .htm tentando UTF-8 e caindo para Windows-1252 (sites antigos)."""
    raw = open(path, "rb").read()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            html = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        html = raw.decode("utf-8", errors="replace")
    p = TextExtractor()
    try:
        p.feed(html)
    except Exception:
        pass  # HTML malformado: usa o que conseguiu extrair até aqui
    return " ".join(p.parts)

# ------------------------- extração de texto: PDF ------------------------

def read_pdf_text(path):
    """Extrai texto de um PDF usando pypdf. Retorna None se pypdf faltar."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    try:
        reader = PdfReader(path)
        pages = []
        total = 0
        for page in reader.pages:
            t = page.extract_text() or ""
            pages.append(t)
            total += len(t)
            if total >= MAX_TEXT:      # já temos texto suficiente
                break
        return " ".join(pages)
    except Exception as e:
        print(f"    AVISO: falha ao ler PDF ({e})")
        return ""

# ------------------------------ utilidades -------------------------------

def clean(text):
    """Normaliza espaços em branco e trunca no limite."""
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_TEXT]

# --------------------------------- main ----------------------------------

def main():
    if not os.path.exists(ITEMS_FILE):
        sys.exit(f"ERRO: {ITEMS_FILE} não encontrado. "
                 f"Rode este script na raiz do repositório genismo.")

    data = json.load(open(ITEMS_FILE, encoding="utf-8"))
    cat_names = {c["id"]: c["name"] for c in data["categories"]}
    items = data["items"]

    index = []
    pulados, sem_pypdf = [], []

    print(f"Indexando {len(items)} artigos...\n")

    for i, item in enumerate(items, 1):
        href = item["href"]
        # nome da categoria: usa catName se existir, senão resolve pelo id
        cat = item.get("catName") or cat_names.get(item.get("cat", ""), item.get("cat", ""))
        # caminho local (remove âncoras/query e decodifica %20 etc.)
        from urllib.parse import unquote
        path = unquote(href.split("#")[0].split("?")[0])

        if not os.path.exists(path):
            pulados.append(href)
            print(f"[{i:3}/{len(items)}] PULADO (arquivo não existe): {href}")
            continue

        ext = os.path.splitext(path)[1].lower()
        if ext in (".htm", ".html"):
            text = read_html_text(path)
        elif ext == ".pdf":
            text = read_pdf_text(path)
            if text is None:
                sem_pypdf.append(href)
                print(f"[{i:3}/{len(items)}] PULADO (instale pypdf): {href}")
                continue
        else:
            pulados.append(href)
            print(f"[{i:3}/{len(items)}] PULADO (tipo não suportado): {href}")
            continue

        index.append({
            "href": href,
            "title": item["title"],
            "cat": cat,
            "text": clean(text),
        })
        print(f"[{i:3}/{len(items)}] OK: {item['title'][:60]}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))

    tamanho_mb = os.path.getsize(OUTPUT_FILE) / 1e6
    print(f"\n{'='*60}")
    print(f"Concluído! {len(index)} artigos indexados em {OUTPUT_FILE} "
          f"({tamanho_mb:.1f} MB)")
    if pulados:
        print(f"Pulados ({len(pulados)}): " + ", ".join(pulados[:10])
              + (" ..." if len(pulados) > 10 else ""))
    if sem_pypdf:
        print(f"PDFs pulados por falta do pypdf ({len(sem_pypdf)}). "
              f"Instale com:  pip install pypdf   e rode de novo.")

if __name__ == "__main__":
    main()