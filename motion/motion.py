#!/usr/bin/env python3
"""Healthy Fry : vidéo 100 % motion design (objets photoréalistes détourés + animation codée).

Usage : python3 motion/motion.py [-o sortie.mp4]
La voix off (gratuite) dicte le timing : chaque scène dure le temps de sa phrase,
les ingrédients tombent au moment exact où ils sont prononcés.
"""
import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent / "montage"))
from render import (DELAI_VOIX, SFX, duree, fichier_ass, instants_ingredients,  # noqa: E402
                    prepare_sfx, run, voix_off, VOIX_DEFAUT)

SCENES = [  # (clé, voix off, durée minimale de l'animation)
    ("hook", "Le cookie le plus fondant que tu puisses faire à l'airfryer.", 3.4),
    ("ingr", "Il te faut un œuf, du sucre roux, de la farine, du beurre mou, et des pépites de chocolat.", 0),
    ("prep", "Mélange tout, forme de grosses boules, et direction l'airfryer : cent soixante degrés, huit minutes.", 6.0),
    ("result", "Et voilà : croustillant dehors, fondant dedans.", 3.6),
    ("cta", "Enregistre la recette, et abonne-toi !", 2.8),
]
INGREDIENTS = ["œuf", "sucre roux", "farine", "beurre", "pépites chocolat"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--sortie", default=str(ICI / "sorties" / "cookie-motion.mp4"))
    ap.add_argument("--accroche-video", help="clip vidéo (ex. Veo) pour l'accroche, à la place de l'animation")
    ap.add_argument("--accroche-debut", type=float, default=0.0, help="seconde de départ dans le clip d'accroche")
    a = ap.parse_args()
    sortie = Path(a.sortie)
    sortie.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="hfm_"))
    prepare_sfx()

    print("▶ Voix off")
    T, t0, mots, pistes, sfx = {}, 0.0, [], [], []
    for i, (cle, texte, dmin) in enumerate(SCENES):
        mp3 = tmp / f"v{i}.mp3"
        m = voix_off(texte, VOIX_DEFAUT, mp3, "+8%")
        d = max(DELAI_VOIX + duree(mp3) + 0.35, dmin)
        if cle == "ingr":
            rel = instants_ingredients(INGREDIENTS, m, d)
            T["reveal"] = [t0 + r for r in rel]
            d = max(d, rel[-1] + 1.2)
            sfx += [("pop", t0 + r, 0.5) for r in rel]
        T[cle] = [round(t0, 3), round(t0 + d, 3)]
        mots += [dict(x, t=x["t"] + t0 + DELAI_VOIX) for x in m]
        pistes.append((mp3, t0 + DELAI_VOIX))
        if i:
            sfx.append(("whoosh", t0 - 0.2, 0.6))
        t0 += d
    T["total"] = round(t0, 3)
    T["hookVideo"] = bool(a.accroche_video)
    p = T["prep"][0]
    sfx += [("pop", T["hook"][0] + 0.15, .5), ("pop", T["hook"][0] + .35, .5), ("pop", T["hook"][0] + .55, .5),
            ("tick", T["hook"][0] + 1.1, .7), ("whoosh", p + .45, .5), ("pop", p + .6, .5),
            ("whoosh", p + 1.0, .6), ("tick", p + 1.9, .6), ("ding", T["result"][0], .6),
            ("pop", T["result"][0] + .7, .5), ("pop", T["result"][0] + 1.3, .5), ("pop", T["cta"][0] + .2, .5)]
    (tmp / "timeline.json").write_text(json.dumps(T))
    print("  ", {k: v for k, v in T.items() if k != "reveal"})

    print("▶ Animation (rendu image par image)")
    run(["node", str(ICI / "frames.js"), str(tmp / "timeline.json"), str(tmp / "anim.mp4")])
    video = tmp / "anim.mp4"
    if a.accroche_video:  # clip réel + calque des titres, puis l'animation
        dh = T["hook"][1]
        run(["ffmpeg", "-y", "-v", "error", "-ss", str(a.accroche_debut), "-t", f"{dh:.3f}", "-i", a.accroche_video,
             "-framerate", "30", "-i", str(tmp / "anim.mp4_hook" / "%04d.png"), "-i", str(tmp / "anim.mp4"),
             "-filter_complex",
             "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1,"
             "eq=contrast=1.05:saturation=1.08[cv];[cv][1:v]overlay=0:0:shortest=1,format=yuv420p[h];"
             "[2:v]setsar=1,format=yuv420p[r];[h][r]concat=n=2:v=1:a=0[v]",
             "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", str(tmp / "mix.mp4")])
        run(["ffmpeg", "-y", "-v", "error", "-ss", str(a.accroche_debut), "-t", f"{dh:.3f}", "-i", a.accroche_video,
             "-vn", "-ac", "2", "-ar", "48000", str(tmp / "hook_son.wav")])
        pistes.append((tmp / "hook_son.wav", 0.0))
        video = tmp / "mix.mp4"

    print("▶ Voix, bruitages, sous-titres, export")
    ass = tmp / "st.ass"
    fichier_ass(mots, ass, {"marge_bas_sous_titres": 470, "taille_sous_titres": 78})
    entrees = ["-i", str(video)]
    fc, labels, n = [], [], 1
    for mp3, dec in pistes:
        entrees += ["-i", str(mp3)]
        ms = int(dec * 1000)
        fc.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[a{n}]")
        labels.append(f"[a{n}]")
        n += 1
    for nom, t, vol in sfx:
        entrees += ["-i", str(SFX / f"{nom}.wav")]
        ms = int(max(0, t) * 1000)
        fc.append(f"[{n}:a]volume={vol},adelay={ms}|{ms}[a{n}]")
        labels.append(f"[a{n}]")
        n += 1
    fc.append(f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,"
              f"loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]")
    fc.append(f"[0:v]ass={ass}:fontsdir={ICI.parent / 'montage' / 'fonts'}[v]")
    run(["ffmpeg", "-y", "-v", "error", *entrees, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
         "-t", str(T["total"]), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(sortie)])
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"✅ {sortie} ({duree(sortie):.1f}s)")


if __name__ == "__main__":
    main()
