#!/usr/bin/env python3
"""Génère un MP3 expressif à partir de resume_tagge.txt.

Moteur : espeak-ng + voix française MBROLA (mb-fr1 / mb-fr4), ffmpeg pour l'encodage.
Les balises (pauses, souffles, intonation) sont décrites en tête de resume_tagge.txt.
"""
import re
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
SRC = HERE / "resume_tagge.txt"
VOICE = sys.argv[1] if len(sys.argv) > 1 else "mb-fr1"
OUT = HERE / "resume_pages_215-230.mp3"

BASE = {"s": 150, "p": 50, "a": 100}  # débit (mots/min), hauteur, volume espeak
PAUSES = {"s": 0.30, "m": 0.65, "l": 1.20, "xl": 2.00}
# style : (facteur de débit, delta de hauteur, facteur de volume)
STYLES = {
    "slow": (0.85, 0, 1.0),
    "fast": (1.12, 0, 1.0),
    "soft": (0.88, -6, 0.55),
    "emph": (0.92, 8, 1.15),
    "low": (0.95, -9, 0.95),
    "high": (1.0, 8, 1.0),
}
TOKEN = re.compile(r"(\[p:(?:s|m|l|xl)\]|\[b\]|\[B\]|</?(?:slow|fast|soft|emph|low|high)>)")
RATE = 22050
rng = np.random.default_rng(7)


def synth(text, style_stack):
    speed, pitch, amp = BASE["s"], BASE["p"], BASE["a"]
    for name in style_stack:
        f, dp, fa = STYLES[name]
        speed *= f
        pitch += dp
        amp *= fa
    with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
        subprocess.run(
            ["espeak-ng", "-v", VOICE, "-s", str(int(speed)), "-p", str(max(0, min(99, int(pitch)))),
             "-a", str(min(200, int(amp))), "-g", "2", "-w", tmp.name, text],
            check=True, stderr=subprocess.DEVNULL)
        with wave.open(tmp.name) as w:
            assert w.getsampwidth() == 2 and w.getnchannels() == 1
            rate = w.getframerate()
            data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    if rate != RATE:  # ré-échantillonnage linéaire simple
        n = int(len(data) * RATE / rate)
        data = np.interp(np.linspace(0, len(data) - 1, n), np.arange(len(data)), data)
    # léger fondu d'entrée/sortie pour éviter les clics
    k = min(len(data) // 4, int(0.012 * RATE))
    if k:
        data[:k] *= np.linspace(0, 1, k)
        data[-k:] *= np.linspace(1, 0, k)
    return data


def silence(sec):
    return np.zeros(int(sec * RATE), dtype=np.float32)


def breath(deep=False):
    """Souffle synthétique : bruit filtré, montée puis descente lentes (inspiration)."""
    dur = 0.85 if deep else 0.45
    n = int(dur * RATE)
    noise = rng.standard_normal(n).astype(np.float32)
    spec = np.fft.rfft(noise)
    freqs = np.fft.rfftfreq(n, 1 / RATE)
    band = np.exp(-((freqs - 1400) / 1300) ** 2) * (freqs > 250)
    x = np.fft.irfft(spec * band, n)
    x /= np.max(np.abs(x)) + 1e-9
    t = np.linspace(0, 1, n)
    env = np.sin(np.pi * t ** 0.8) ** 2  # inspiration : montée rapide, retombée douce
    return (x * env * (0.16 if deep else 0.10)).astype(np.float32)


def render(lines):
    audio, stack = [], []
    pending_gap = 0.0
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("# ") or line == "#":
            continue
        heading = line.startswith("## ")
        if heading:
            line = line[3:]
            audio.append(silence(1.1))
        style_base = ["slow", "low"] if heading else []
        stack = list(style_base)
        for tok in TOKEN.split(line):
            if not tok:
                continue
            if tok.startswith("[p:"):
                audio.append(silence(PAUSES[tok[3:-1]]))
            elif tok == "[b]":
                audio.append(silence(0.08)); audio.append(breath(False)); audio.append(silence(0.12))
            elif tok == "[B]":
                audio.append(silence(0.10)); audio.append(breath(True)); audio.append(silence(0.20))
            elif tok.startswith("</"):
                name = tok[2:-1]
                if name in stack:
                    stack.reverse(); stack.remove(name); stack.reverse()
            elif tok.startswith("<"):
                stack.append(tok[1:-1])
            elif re.search(r"\w", tok):
                audio.append(synth(tok.strip(), stack))
        audio.append(silence(0.9 if heading else 0.5))
    return np.concatenate(audio)


def main():
    lines = SRC.read_text(encoding="utf-8").splitlines()
    data = render(lines)
    wav_path = HERE / "_tmp_resume.wav"
    pcm = (np.clip(data, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(pcm.tobytes())
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path),
         "-af", "highpass=f=70,acompressor=threshold=-20dB:ratio=2.5:attack=8:release=200,"
                "aecho=0.8:0.6:40:0.12,loudnorm=I=-18:TP=-2",
         "-ar", "44100", "-codec:a", "libmp3lame", "-q:a", "3",
         "-metadata", "title=Résumé pages 215-230", str(OUT)], check=True)
    wav_path.unlink()
    print(f"OK : {OUT.name}  ({len(data) / RATE / 60:.1f} min, voix {VOICE})")


if __name__ == "__main__":
    main()
