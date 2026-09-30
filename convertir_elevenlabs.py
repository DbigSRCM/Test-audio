#!/usr/bin/env python3
"""Convertit resume_tagge.txt au format ElevenLabs.

  v3  -> resume_elevenlabs_v3.txt  (balises [..] + MAJUSCULES pour l'insistance)
  v2  -> resume_elevenlabs_v2.txt  (Multilingual v2 : <break time="Xs" />, pas de balises d'émotion)
Un bloc « ===== TITRE ===== » = une génération à coller (chaque page reste sous ~3000 caractères).
"""
import re
from pathlib import Path

HERE = Path(__file__).parent
TOK = re.compile(r"(\[p:(?:s|m|l|xl)\]|\[b\]|\[B\]|</?(?:slow|fast|soft|emph|low|high)>)")

V3 = {"p:s": " ... ", "p:m": " [short pause] ", "p:l": " [long pause] ", "p:xl": " [long pause] ... ",
      "b": " [inhales] ", "B": " [inhales deeply] ",
      "slow": " [slowly] ", "fast": " [quickly] ", "soft": " [whispers] ", "low": " [solemnly] ", "high": " [lightly] "}
V2 = {"p:s": ' <break time="0.3s" /> ', "p:m": ' <break time="0.7s" /> ', "p:l": ' <break time="1.2s" /> ',
      "p:xl": ' <break time="2.0s" /> ', "b": ' <break time="0.5s" /> ', "B": ' <break time="0.9s" /> '}


def convert(lines, mode):
    out, cur = [], None
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") and not line.startswith("##"):
            continue
        if line.startswith("## "):
            if cur:
                out.append(cur)
            cur = ["===== " + line[3:] + " =====", ""]
            continue
        emph = False
        parts = []
        for t in TOK.split(line):
            if not t:
                continue
            if t.startswith("[p:"):
                parts.append((V3 if mode == 3 else V2)[t[1:-1]])
            elif t in ("[b]", "[B]"):
                parts.append((V3 if mode == 3 else V2)[t[1:-1]])
            elif t.startswith("</"):
                emph = emph and t != "</emph>"
            elif t.startswith("<"):
                name = t[1:-1]
                if name == "emph":
                    emph = True
                elif mode == 3:
                    parts.append(V3[name])
            else:
                parts.append(t.upper() if emph and mode == 3 else t)
        text = re.sub(r"[ \t]{2,}", " ", "".join(parts)).strip()
        cur.append(text)
    out.append(cur)
    return "\n\n".join("\n".join(b) for b in out) + "\n"


lines = (HERE / "resume_tagge.txt").read_text(encoding="utf-8").splitlines()
for mode, name in ((3, "resume_elevenlabs_v3.txt"), (2, "resume_elevenlabs_v2.txt")):
    txt = convert(lines, mode)
    (HERE / name).write_text(txt, encoding="utf-8")
    blocks = txt.split("===== ")[1:]
    print(name, len(txt), "car. ; plus grand bloc :", max(len(b) for b in blocks))
