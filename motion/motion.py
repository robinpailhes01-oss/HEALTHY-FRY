#!/usr/bin/env python3
"""Healthy Fry : vidéo d'au moins 61 s, accroche filmée (Veo) puis 100 % motion design.

Usage :
    python3 motion/motion.py motion/recettes/cookie-fondant.json [-o sortie.mp4]

Le fichier recette décrit les scènes (hook, promesse, ingredients, etape…, cuisson, resultat, astuce, cta),
le texte de la voix off et les objets détourés à utiliser. Voir motion/README.md.
Voix : ElevenLabs si ELEVENLABS_API_KEY est définie (sinon voix Edge gratuite).
Bruitages : bibliothèque motion/sfx/ (générée avec ElevenLabs par sfx.py), sinon bruitages synthétiques.
"""
import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent / "montage"))
import elevenlabs  # noqa: E402
from render import (DELAI_VOIX, SFX as SFX_SYNTH, duree, fichier_ass, instants_ingredients,  # noqa: E402
                    prepare_sfx, run, voix_off as voix_edge, VOIX_DEFAUT)

SFX_PRO = ICI / "sfx"
# durée minimale dont chaque animation a besoin ; au-delà, la scène dure exactement le temps de sa phrase
DUREE_MIN_SCENE = {"hook": 2.8, "promesse": 3.0, "ingredients": 2.5, "etape": 2.8, "cuisson": 5.0,
                   "resultat": 3.4, "astuce": 3.0, "cta": 3.0}
MARGE = 0.12          # respiration après chaque phrase


def son(nom):
    """Bruitage de qualité (ElevenLabs) s'il existe, sinon équivalent synthétique."""
    for ext in (".mp3", ".wav"):
        if (SFX_PRO / f"{nom}{ext}").exists():
            return SFX_PRO / f"{nom}{ext}"
    repli = {"stamp": "pop", "plop": "tick", "sparkle": "ding", "sizzle": None, "riser": "whoosh",
             "beep": "ding", "crunch": None, "swoosh": "whoosh", "impact": "pop"}.get(nom, nom)
    return SFX_SYNTH / f"{repli}.wav" if repli and (SFX_SYNTH / f"{repli}.wav").exists() else None


def parle(texte, r, sortie):
    v = r.get("voix", {})
    if elevenlabs.dispo() and v.get("elevenlabs_id"):
        return elevenlabs.voix_off(texte, v["elevenlabs_id"], sortie, v.get("modele", "eleven_multilingual_v2"),
                                   v.get("stabilite", 0.35), v.get("style", 0.45), v.get("vitesse", 1.05))
    return voix_edge(texte, v.get("edge", VOIX_DEFAUT), sortie, v.get("vitesse_edge", "+8%"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("recette")
    ap.add_argument("-o", "--sortie")
    ap.add_argument("--garder-temp", action="store_true")
    a = ap.parse_args()
    fichier = Path(a.recette).resolve()
    r = json.loads(fichier.read_text(encoding="utf-8"))
    base = fichier.parent
    sortie = Path(a.sortie or ICI / "sorties" / (fichier.stem + ".mp4")).resolve()
    sortie.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="hfm_"))
    prepare_sfx()
    cible = float(r.get("duree_min", 62))
    scenes = r["scenes"]
    nb_etapes = sum(1 for s in scenes if s["type"] == "etape")

    # ---- 1. voix off scène par scène
    print("▶ Voix off :", "ElevenLabs" if elevenlabs.dispo() and r.get("voix", {}).get("elevenlabs_id") else "Edge (gratuite)")
    for i, s in enumerate(scenes):
        mp3 = tmp / f"v{i}.mp3"
        s["_mots"] = parle(s["voix"], r, mp3) if s.get("voix") else []
        s["_mp3"] = mp3 if s.get("voix") else None
        dv = DELAI_VOIX + duree(mp3) + MARGE if s.get("voix") else 0
        s["_d"] = max(dv, DUREE_MIN_SCENE.get(s["type"], 3.0), float(s.get("duree", 0)))
        if s["type"] == "ingredients":
            rel = instants_ingredients([it.get("mot", it["label"]) for it in s["items"]], s["_mots"], s["_d"])
            s["_reveal"] = rel
            s["_d"] = max(s["_d"], rel[-1] + 0.9)

    # ---- 2. au moins `duree_min` secondes (monétisation)
    total = sum(s["_d"] for s in scenes)
    if total < cible:   # on préfère du contenu en plus ; sinon on répartit le manque sur toutes les scènes (sans trou visible)
        manque = cible - total
        if manque > 3:
            print(f"  ⚠️ texte trop court : {total:.1f}s naturelles, il manque {manque:.1f}s → ajoute une scène ou allonge la voix")
        for s in scenes:
            s["_d"] += manque * s["_d"] / total
        print(f"  durée naturelle {total:.1f}s → {cible:.1f}s")

    # ---- 3. timeline pour le moteur d'animation
    assets = {k: os.path.relpath((base / v).resolve(), ICI) for k, v in r["assets"].items()}
    assets.setdefault("airfryer", os.path.relpath(ICI / "cut" / "airfryer.png", ICI))
    T, t0, mots, pistes, sfx = {"assets": assets, "handle": r.get("handle", "@healthyfry"),
                                "hookVideo": bool(r.get("accroche_video")), "scenes": []}, 0.0, [], [], []
    k_etape = 0
    for i, s in enumerate(scenes):
        a_, b_ = t0, t0 + s["_d"]
        sc = {k: v for k, v in s.items() if not k.startswith("_") and k != "voix"}
        sc.update(a=round(a_, 3), b=round(b_, 3))
        if s["type"] == "etape":
            k_etape += 1
            sc.setdefault("num", k_etape)
            sc["total"] = nb_etapes
        if s["type"] == "ingredients":
            sc["reveal"] = [a_ + x for x in s["_reveal"]]
        T["scenes"].append(sc)
        if s["_mp3"]:
            pistes.append((s["_mp3"], a_ + DELAI_VOIX, 1.0))
            mots += [dict(m, t=m["t"] + a_ + DELAI_VOIX) for m in s["_mots"]]
        # design sonore
        if i:
            sfx.append(("swoosh", a_ - 0.25, .55))
        typ = s["type"]
        if typ == "hook":
            sfx += [("impact", a_ + .1, .5), ("impact", a_ + .3, .45), ("impact", a_ + .5, .5), ("stamp", a_ + 1.1, .7)]
        elif typ == "promesse":
            sfx += [("pop", a_ + .05, .45)] + [("pop", a_ + .35 + k * .45, .5) for k in range(len(s.get("stats", [])))]
        elif typ == "ingredients":
            sfx += [("pop", a_ + .05, .4)] + [("plop", a_ + x, .6) for x in s["_reveal"]] + [("riser", b_ - .7, .4)]
        elif typ == "etape":
            choc = a_ + min(1.3, s["_d"] * .35)
            sfx += [("pop", a_ + .05, .4), ("swoosh", a_ + .1, .35)]
            if s.get("items"):
                sfx.append(("impact", choc, .6))
            if s.get("resultat"):
                sfx.append(("sparkle", choc + .05, .45))
        elif typ == "cuisson":
            sfx += [("swoosh", a_ + .5, .5), ("beep", a_ + 1.2, .5), ("sizzle", a_ + 1.4, .35), ("beep", b_ - .6, .55)]
        elif typ == "resultat":
            sfx += [("sparkle", a_ + .05, .6), ("crunch", a_ + .3, .5), ("pop", a_ + .7, .45), ("pop", a_ + 1.3, .45)]
        elif typ == "astuce":
            sfx += [("stamp" if s.get("alerte") else "pop", a_ + .05, .5), ("pop", a_ + .25, .4)]
        elif typ == "cta":
            sfx += [("sparkle", a_ + .3, .45), ("pop", a_ + .25, .5)]
        t0 = b_
    T["total"] = round(t0, 3)
    (tmp / "timeline.json").write_text(json.dumps(T, ensure_ascii=False))
    print("  scènes :", " | ".join(f"{s['type']} {s['b'] - s['a']:.1f}s" for s in T["scenes"]), f"→ total {t0:.1f}s")

    # ---- 4. animation image par image
    print("▶ Animation")
    run(["node", str(ICI / "frames.js"), str(tmp / "timeline.json"), str(tmp / "anim.mp4")])
    video = tmp / "anim.mp4"
    if r.get("accroche_video"):
        dh = T["scenes"][0]["b"]
        clip = str((base / r["accroche_video"]).resolve())
        deb = str(r.get("accroche_debut", 0))
        run(["ffmpeg", "-y", "-v", "error", "-ss", deb, "-t", f"{dh:.3f}", "-i", clip,
             "-framerate", "30", "-i", str(tmp / "anim.mp4_hook" / "%04d.png"), "-i", str(tmp / "anim.mp4"),
             "-filter_complex",
             "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1,"
             "eq=contrast=1.05:saturation=1.08,tpad=stop_mode=clone:stop_duration=2[cv];"
             "[cv][1:v]overlay=0:0:shortest=1,format=yuv420p[h];[2:v]setsar=1,format=yuv420p[rr];[h][rr]concat=n=2:v=1:a=0[v]",
             "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", str(tmp / "mix.mp4")])
        run(["ffmpeg", "-y", "-v", "error", "-ss", deb, "-t", f"{dh:.3f}", "-i", clip, "-vn", "-ac", "2", "-ar", "48000",
             str(tmp / "hook_son.wav")])
        pistes.append((tmp / "hook_son.wav", 0.0, float(r.get("volume_son_accroche", 0.8))))
        video = tmp / "mix.mp4"

    # ---- 5. voix + bruitages + musique + sous-titres + export
    print("▶ Mixage et export")
    ass = tmp / "st.ass"
    fichier_ass(mots, ass, {"marge_bas_sous_titres": 470, "taille_sous_titres": 78})
    entrees, fc, labels, n = ["-i", str(video)], [], [], 1
    for chemin, dec, vol in pistes:
        entrees += ["-i", str(chemin)]
        ms = int(dec * 1000)
        fc.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,volume={vol},adelay={ms}|{ms}[a{n}]")
        labels.append(f"[a{n}]")
        n += 1
    nb_voix = len(labels)
    for nom, t, vol in sfx:
        f = son(nom)
        if not f:
            continue
        entrees += ["-i", str(f)]
        ms = int(max(0, t) * 1000)
        fc.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,volume={vol},adelay={ms}|{ms}[a{n}]")
        labels.append(f"[a{n}]")
        n += 1
    fc.append(f"{''.join(labels[:nb_voix])}amix=inputs={nb_voix}:duration=longest:normalize=0[voix]")
    fc.append(f"{''.join(labels[nb_voix:])}amix=inputs={len(labels) - nb_voix}:duration=longest:normalize=0[fxs]")
    musique = r.get("musique") and (base / r["musique"]).resolve()
    if musique and musique.exists():
        entrees += ["-stream_loop", "-1", "-i", str(musique)]
        fc += [f"[voix]asplit[v1][v2]",
               f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,volume={r.get('volume_musique', 0.18)},"
               f"afade=t=out:st={t0 - 2:.2f}:d=2[mu]",
               "[mu][v1]sidechaincompress=threshold=0.03:ratio=8:attack=15:release=350[mud]",
               "[v2][fxs][mud]amix=inputs=3:duration=first:normalize=0[pre]"]
    else:
        fc.append("[voix][fxs]amix=inputs=2:duration=first:normalize=0[pre]")
    fc.append("[pre]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]")
    fc.append(f"[0:v]ass={ass}:fontsdir={ICI.parent / 'montage' / 'fonts'}[v]")
    run(["ffmpeg", "-y", "-v", "error", *entrees, "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]",
         "-t", str(T["total"]), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(sortie)])
    run(["ffmpeg", "-y", "-v", "error", "-ss", "1.0", "-i", str(sortie), "-frames:v", "1", "-q:v", "3",
         str(sortie.with_suffix(".jpg"))])
    leg = r.get("legende", "") + ("\n\n" + " ".join("#" + h for h in r.get("hashtags", [])) if r.get("hashtags") else "")
    sortie.with_suffix(".txt").write_text(leg.strip() + "\n", encoding="utf-8")
    if a.garder_temp:
        print("  temporaires :", tmp)
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    d = duree(sortie)
    print(f"✅ {sortie} ({d:.1f}s)" + ("" if d >= 61 else "  ⚠️ MOINS D'1 MIN : non monétisable"))


if __name__ == "__main__":
    main()
