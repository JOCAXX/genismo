#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_index.py v2 — Gerador do índice de busca do site Genismo
================================================================
Fluxo igual ao do DUniverse: basta colocar o arquivo novo (.htm ou .pdf)
na raiz e rodar o script — ele detecta, registra e indexa sozinho.

USO (na raiz do repositório genismo):

    pip install pypdf              (só na primeira vez, para indexar PDFs)
    python build_index.py          -> indexa tudo; ARQUIVOS NOVOS são
                                      registrados e indexados automaticamente

Depois: commit + push de search-index.json e items.json (GitHub Desktop).

COMO ELE SABE O QUE É ARTIGO E O QUE É PÁGINA DO SITE?
  O arquivo nao_indexar.txt guarda a lista de páginas antigas do site
  (menus, notícias, versões velhas) que nunca devem entrar na busca.
  - Arquivo novo na pasta  -> vira artigo (registrado no items.json).
  - Não quer que algo seja indexado? Adicione o nome dele (uma linha)
    no nao_indexar.txt.
  O título é gerado a partir do nome do arquivo e a categoria é
  adivinhada pelo prefixo (geneticatexto* -> Genética, etc.). Você pode
  depois corrigir título/categoria editando o items.json — o script
  preserva suas edições nas próximas execuções.
"""

import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote

# ----------------------------- configurações -----------------------------

RAIZ         = Path(__file__).resolve().parent
ITEMS_FILE   = RAIZ / "items.json"
OUTPUT_FILE  = RAIZ / "search-index.json"
IGNORE_FILE  = RAIZ / "nao_indexar.txt"
MAX_TEXT     = 18000          # nº máximo de caracteres de texto por artigo
EXTENSOES    = (".htm", ".html", ".pdf")

# prefixo do nome do arquivo -> id da categoria (para arquivos novos)
PREFIXO_CAT = {
    "genismotexto":   "genismo",
    "geneticatexto":  "genetica",
    "psicologiatexto":"psicologia",
    "memeticatexto":  "memetica",
    "logicatexto":    "logica",
    "metatexto":      "metaetica",
    "religiaotexto":  "religiao",
    "englishtext":    "english",
}
CAT_PADRAO_HTM = "genismo"    # categoria padrão p/ .htm novos sem prefixo
CAT_PADRAO_PDF = "pdf"        # categoria padrão p/ .pdf novos

# ------------------------- extração de texto: HTML -----------------------

from html.parser import HTMLParser

SKIP_TAGS = {"script", "style", "head", "title", "noscript"}

class TextExtractor(HTMLParser):
    """Extrai apenas o texto visível de um arquivo HTML."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self._skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS: self._skip += 1
    def handle_endtag(self, tag):
        if tag in SKIP_TAGS and self._skip > 0: self._skip -= 1
    def handle_data(self, data):
        if self._skip == 0: self.parts.append(data)

def read_html_text(path: Path) -> str:
    """Lê um .htm tentando UTF-8 e caindo para Windows-1252 (sites antigos)."""
    raw = path.read_bytes()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            html = raw.decode(enc); break
        except UnicodeDecodeError:
            continue
    else:
        html = raw.decode("utf-8", errors="replace")
    p = TextExtractor()
    try: p.feed(html)
    except Exception: pass
    return " ".join(p.parts)

# ------------------------- extração de texto: PDF ------------------------

def read_pdf_text(path: Path):
    """Extrai texto de um PDF via pypdf. Retorna None se pypdf faltar."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    try:
        reader = PdfReader(str(path))
        parts, total = [], 0
        for page in reader.pages:
            t = page.extract_text() or ""
            parts.append(t); total += len(t)
            if total >= MAX_TEXT: break
        return " ".join(parts)
    except Exception as e:
        print(f"    AVISO: falha ao ler PDF ({e})")
        return ""

# ------------------------------ utilidades -------------------------------

def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()[:MAX_TEXT]

def titulo_do_nome(nome: str) -> str:
    """'Aqui esta o build.pdf' -> 'Aqui Esta O Build'."""
    stem = Path(nome).stem
    s = re.sub(r"[_\-]+", " ", stem)
    s = re.sub(r"\s+", " ", s).strip()
    return " ".join(w if any(c.isupper() for c in w) or w.isdigit()
                    else w.capitalize() for w in s.split(" "))

def categoria_do_nome(nome: str) -> str:
    base = nome.lower()
    if base.endswith(".pdf"):
        return CAT_PADRAO_PDF
    for prefixo, cat in PREFIXO_CAT.items():
        if base.startswith(prefixo):
            return cat
    return CAT_PADRAO_HTM

# --------------------------------- main ----------------------------------

def main():
    if not ITEMS_FILE.is_file():
        sys.exit("ERRO: items.json não encontrado. "
                 "Rode este script na raiz do repositório genismo.")

    data = json.loads(ITEMS_FILE.read_text(encoding="utf-8"))
    cat_nome = {c["id"]: c["name"] for c in data["categories"]}
    items = data["items"]

    # ---------- arquivos no disco ----------
    disco = {f for f in os.listdir(RAIZ)
             if f.lower().endswith(EXTENSOES) and (RAIZ / f).is_file()}

    registrados = {unquote(i["href"].split("#")[0].split("?")[0]) for i in items}

    # ---------- lista de exclusão ----------
    if IGNORE_FILE.is_file():
        ignorar = {l.strip() for l in
                   IGNORE_FILE.read_text(encoding="utf-8").splitlines()
                   if l.strip() and not l.startswith("#")}
    else:
        # primeira execução: tudo que está no disco e não é artigo
        # registrado vira "página do site" e entra na lista de exclusão
        ignorar = disco - registrados
        IGNORE_FILE.write_text(
            "# Arquivos que NÃO devem ser indexados na busca\n"
            "# (páginas do site, menus, versões antigas).\n"
            "# Uma linha por arquivo. Linhas com # são comentários.\n"
            + "\n".join(sorted(ignorar)) + "\n", encoding="utf-8")
        print(f"Criado {IGNORE_FILE.name} com {len(ignorar)} páginas do site "
              f"que ficarão fora da busca.\n"
              f"(Revise esse arquivo se algum artigo verdadeiro entrou nele.)\n")

    # ---------- detectar arquivos NOVOS ----------
    novos = sorted(disco - registrados - ignorar)
    if novos:
        print(f"ARQUIVOS NOVOS detectados ({len(novos)}) — registrando no items.json:")
        for nome in novos:
            cat = categoria_do_nome(nome)
            item = {"href": nome, "title": titulo_do_nome(nome),
                    "cat": cat, "catName": cat_nome.get(cat, cat)}
            items.append(item)
            print(f"  + {nome}  ->  título: \"{item['title']}\" | "
                  f"categoria: {item['catName']}")
        print("  (Ajuste título/categoria no items.json se quiser; "
              "suas edições serão preservadas.)\n")

    # ---------- avisar sobre registrados que sumiram do disco ----------
    sumidos = sorted(registrados - disco)
    if sumidos:
        print(f"AVISO: {len(sumidos)} artigo(s) do items.json não existem "
              f"na pasta e ficarão fora do índice:")
        for s in sumidos[:15]:
            print(f"  - {s}")
        if len(sumidos) > 15: print("  ...")
        print()

    # ---------- indexação ----------
    index, sem_pypdf = [], []
    print(f"Indexando {len(items)} artigos...")
    for i, item in enumerate(items, 1):
        nome = unquote(item["href"].split("#")[0].split("?")[0])
        path = RAIZ / nome
        if not path.is_file():
            continue  # já avisado acima
        cat = item.get("catName") or cat_nome.get(item.get("cat", ""),
                                                  item.get("cat", ""))
        if nome.lower().endswith(".pdf"):
            text = read_pdf_text(path)
            if text is None:
                sem_pypdf.append(nome); continue
        else:
            text = read_html_text(path)
        index.append({"href": item["href"], "title": item["title"],
                      "cat": cat, "text": clean(text)})
        if i % 50 == 0 or i == len(items):
            print(f"  ... {i}/{len(items)}")

    # ---------- gravar ----------
    OUTPUT_FILE.write_text(
        json.dumps(index, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8")
    if novos:
        ITEMS_FILE.write_text(
            json.dumps(data, ensure_ascii=False, separators=(", ", ": ")),
            encoding="utf-8")

    mb = OUTPUT_FILE.stat().st_size / 1e6
    print(f"\n{'='*60}")
    print(f"Concluído! {len(index)} artigos indexados em "
          f"{OUTPUT_FILE.name} ({mb:.1f} MB)")
    if novos:
        print(f"items.json atualizado com {len(novos)} artigo(s) novo(s).")
        print("Commit + push:  search-index.json  e  items.json")
    else:
        print("Commit + push:  search-index.json")
    if sem_pypdf:
        print(f"\nPDFs pulados por falta do pypdf ({len(sem_pypdf)}): "
              + ", ".join(sem_pypdf[:5]))
        print("Instale com:  pip install pypdf   e rode de novo.")

if __name__ == "__main__":
    main()
