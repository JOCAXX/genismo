#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
converte_utf8.py — Converte todos os .htm do site para UTF-8
=============================================================
Corrige de vez o problema dos acentos aparecendo como "�":
os arquivos antigos estão gravados em Windows-1252, mas o GitHub Pages
sempre serve as páginas como UTF-8 — e o navegador obedece ao servidor.

O que ele faz, para cada .htm/.html (raiz + pastas *_arquivos):
  1. Se o arquivo já é UTF-8 válido -> não mexe.
  2. Se está em Windows-1252 -> reconverte o conteúdo para UTF-8
     e corrige a declaração <meta charset> para utf-8.

USO (na raiz do repositório genismo):

    python converte_utf8.py           -> converte tudo
    python converte_utf8.py --teste   -> só mostra o que SERIA convertido

Depois: confira algumas páginas no navegador e faça commit + push.
(Se algo der errado, o GitHub Desktop permite reverter tudo com 1 clique.)
"""

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

# padrões de declaração de charset a corrigir (qualquer variação)
RE_META_HTTP = re.compile(
    r'(<meta[^>]*content\s*=\s*["\']?text/html;\s*charset=)[\w\-]+',
    re.IGNORECASE)
RE_META_CHARSET = re.compile(
    r'(<meta\s+charset\s*=\s*["\']?)[\w\-]+', re.IGNORECASE)


def arquivos_alvo():
    """Todos os .htm/.html da raiz e das pastas *_arquivos (frames do Word)."""
    yield from sorted(RAIZ.glob("*.htm"))
    yield from sorted(RAIZ.glob("*.html"))
    for pasta in sorted(RAIZ.glob("*_arquivos")):
        if pasta.is_dir():
            yield from sorted(pasta.glob("*.htm"))
            yield from sorted(pasta.glob("*.html"))


def main():
    teste = "--teste" in sys.argv
    convertidos, ja_ok, erros = [], 0, []

    for f in arquivos_alvo():
        raw = f.read_bytes()

        # 1) já é UTF-8 válido? então não mexe
        try:
            raw.decode("utf-8")
            ja_ok += 1
            continue
        except UnicodeDecodeError:
            pass

        # 2) decodifica como Windows-1252 (cp1252) ou latin-1
        try:
            texto = raw.decode("cp1252")
        except UnicodeDecodeError:
            try:
                texto = raw.decode("latin-1")
            except UnicodeDecodeError:
                erros.append(f)
                continue

        # 3) corrige a declaração de charset no HTML
        texto = RE_META_HTTP.sub(r"\1utf-8", texto)
        texto = RE_META_CHARSET.sub(r"\1utf-8", texto)

        rel = f.relative_to(RAIZ)
        if teste:
            print(f"  converteria: {rel}")
        else:
            f.write_bytes(texto.encode("utf-8"))
            print(f"  convertido : {rel}")
        convertidos.append(f)

    print(f"\n{'='*60}")
    acao = "seriam convertidos" if teste else "convertidos para UTF-8"
    print(f"{len(convertidos)} arquivo(s) {acao}; "
          f"{ja_ok} já estavam em UTF-8.")
    if erros:
        print(f"ERRO ao ler {len(erros)} arquivo(s): "
              + ", ".join(str(e.name) for e in erros[:10]))
    if not teste and convertidos:
        print("\nAgora confira algumas páginas no navegador e faça o commit.")


if __name__ == "__main__":
    main()
