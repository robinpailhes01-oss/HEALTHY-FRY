#!/usr/bin/env python3
"""Génère (une seule fois) la bibliothèque de bruitages de qualité avec ElevenLabs Sound Effects.

Usage : ELEVENLABS_API_KEY=... python3 motion/sfx.py [--refaire nom1,nom2]
Les fichiers vont dans motion/sfx/ et sont ensuite utilisés automatiquement par motion.py.
"""
import argparse
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent / "montage"))
import elevenlabs  # noqa: E402

BIBLIO = {  # nom : (description, durée en secondes)
    "swoosh":  ("Fast clean modern UI swoosh transition, airy whoosh, short, high quality motion design sound", 0.7),
    "pop":     ("Soft satisfying bubble pop for a text appearing in a motion graphics video, short, clean", 0.4),
    "plop":    ("Small food item dropping softly onto a wooden kitchen counter, gentle thud with light bounce, satisfying ASMR", 0.6),
    "impact":  ("Punchy deep cinematic impact boom for kinetic typography, short tight hit", 0.8),
    "stamp":   ("Heavy rubber stamp slam on paper, satisfying punchy thud", 0.6),
    "sparkle": ("Magical sparkle shimmer chime, bright and delightful, food reveal", 1.2),
    "riser":   ("Short tension riser whoosh building up before a reveal, modern, clean", 1.0),
    "beep":    ("Air fryer appliance digital beep, two short friendly electronic beeps", 0.8),
    "sizzle":  ("Air fryer fan humming with gentle hot air and light food sizzling, kitchen ambience", 4.0),
    "crunch":  ("Close-up ASMR crunch of biting into a crispy golden cookie, crumbly and satisfying", 1.0),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refaire", default="", help="noms à régénérer, séparés par des virgules")
    a = ap.parse_args()
    if not elevenlabs.dispo():
        raise SystemExit("ELEVENLABS_API_KEY manquante.")
    (ICI / "sfx").mkdir(exist_ok=True)
    refaire = set(filter(None, a.refaire.split(",")))
    for nom, (desc, d) in BIBLIO.items():
        f = ICI / "sfx" / f"{nom}.mp3"
        if f.exists() and nom not in refaire:
            print(f"  = {nom} (déjà là)")
            continue
        elevenlabs.effet_sonore(desc, f, duree=d, influence=0.6)
        print(f"  ✓ {nom}")


if __name__ == "__main__":
    main()
