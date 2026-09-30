#!/usr/bin/env python3
"""OCR de photos de pages de livre -> texte propre, dans l'ordre des pages.

Usage :  python3 ocr_pages.py DOSSIER_IMAGES [sortie.txt]

- lit toutes les images du dossier (jpg, jpeg, png, webp, tif) ;
- fait l'OCR en français avec Tesseract ;
- détecte le numéro de page imprimé (ligne ne contenant qu'un nombre) et trie dessus ;
  à défaut, l'ordre alphabétique des noms de fichiers est conservé ;
- retire l'en-tête courant (titre en capitales espacées en haut de page) et le numéro ;
- recolle les mots coupés en fin de ligne et les lignes d'un même paragraphe ;
- écrit un bloc « ===== Page N ===== » par page (pratique pour ElevenLabs).

Prérequis :  apt install tesseract-ocr tesseract-ocr-fra   (ou brew install tesseract tesseract-lang)
Relisez le résultat : l'OCR confond parfois des lettres (surtout sur photos floues ou de travers).
"""
import re
import subprocess
import sys
from pathlib import Path

EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}


def ocr(path):
    r = subprocess.run(["tesseract", str(path), "-", "-l", "fra", "--psm", "4"],
                       capture_output=True, text=True, check=True)
    return r.stdout


def clean(raw):
    lines = [l.rstrip() for l in raw.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    page = None
    # numéro de page : ligne réduite à un nombre, en haut ou en bas
    for idx in list(range(min(3, len(lines)))) + list(range(len(lines) - 1, max(len(lines) - 5, -1), -1)):
        m = re.fullmatch(r"\s*(\d{1,4})(?:\s+\S)?\s*", lines[idx])
        if m:
            page = int(m.group(1))
            lines.pop(idx)
            break
    # en-tête courant : première ligne en capitales (ex. « LE BOL DU MENDIANT »)
    if lines:
        head = re.sub(r"[^A-Za-zÀ-ÿ]", "", lines[0])
        if head and head.isupper() and len(lines[0].split()) <= 8:
            lines.pop(0)
    # paragraphes : ligne vide = fin ; sinon on recolle
    paras, cur = [], []
    for l in lines:
        if not l.strip():
            if cur:
                paras.append(cur)
                cur = []
        else:
            cur.append(l.strip())
    if cur:
        paras.append(cur)
    out = []
    for p in paras:
        txt = ""
        for l in p:
            if txt.endswith("-") and l[:1].islower():
                txt = txt[:-1] + l  # mot coupé
            else:
                txt += ("" if not txt else " ") + l
        # paragraphe coupé à tort par l'OCR : la phrase précédente n'est pas terminée
        if out and not re.search(r"[.!?»:;…\"')]\s*$", out[-1]) and txt[:1].islower():
            out[-1] += " " + txt
        else:
            out.append(txt)
    return page, "\n\n".join(out)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    folder = Path(sys.argv[1])
    dest = Path(sys.argv[2]) if len(sys.argv) > 2 else folder / "texte_complet.txt"
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in EXTS)
    if not files:
        sys.exit("Aucune image trouvée.")
    pages = []
    for i, f in enumerate(files):
        page, text = clean(ocr(f))
        pages.append((page if page is not None else 10_000 + i, page, f.name, text))
        print(f"{f.name}: page {page if page is not None else '?'}", file=sys.stderr)
    pages.sort(key=lambda t: t[0])
    blocks = [f"===== Page {p if p is not None else '?'} =====\n\n{t}" for _, p, _, t in pages]
    dest.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
    print(f"OK : {dest} ({len(pages)} pages)", file=sys.stderr)


if __name__ == "__main__":
    main()
