#!/usr/bin/env python3
"""Healthy Fry : montage automatique de vidéos TikTok 9:16 de 61 s ou plus.

Usage :
    python3 montage/render.py montage/exemple/cookie-fondant.json [-o sortie.mp4]

Entrée : un fichier recette JSON (voir montage/README.md) + des rushes (vidéos ou photos).
Sortie : MP4 1080x1920 30 fps, voix off FR, sous-titres mot à mot, overlays DA Healthy Fry,
         + une miniature (.jpg) et la légende TikTok (.txt).
"""
import argparse
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ICI = Path(__file__).resolve().parent
W, H, FPS = 1080, 1920, 30
VOIX_DEFAUT = "fr-FR-VivienneMultilingualNeural"
DELAI_VOIX = 0.15   # la voix démarre 150 ms après le début du plan
MARGE_FIN = 0.35    # silence après chaque phrase
EXTS_IMAGE = {".jpg", ".jpeg", ".png", ".webp"}


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.stderr.write(" ".join(map(str, cmd)) + "\n" + r.stderr[-3000:])
        raise SystemExit(f"Échec : {cmd[0]}")
    return r.stdout


def duree(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "default=nw=1:nk=1", str(path)]).strip())


def a_audio(path):
    return bool(run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                     "stream=index", "-of", "csv=p=0", str(path)]).strip())


# ---------------------------------------------------------------- voix off (gratuite)
def _patch_ca():
    """edge-tts force le bundle certifi : on le redirige vers le CA système si besoin."""
    ca = os.environ.get("SSL_CERT_FILE") or ("/root/.ccr/ca-bundle.crt" if Path("/root/.ccr/ca-bundle.crt").exists() else None)
    if ca:
        import certifi
        certifi.where = lambda: ca


async def _tts(texte, voix, sortie, vitesse):
    import edge_tts
    com = edge_tts.Communicate(texte, voix, rate=vitesse, boundary="WordBoundary")
    mots = []
    with open(sortie, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                mots.append({"t": ch["offset"] / 1e7, "d": ch["duration"] / 1e7, "mot": ch["text"]})
    return mots


def voix_off(texte, voix, sortie, vitesse="+8%"):
    _patch_ca()
    return asyncio.run(_tts(texte, voix, sortie, vitesse))


# ---------------------------------------------------------------- sous-titres ASS
def couleur_ass(hexa):
    hexa = hexa.lstrip("#")
    r, g, b = hexa[0:2], hexa[2:4], hexa[4:6]
    return f"&H00{b}{g}{r}".upper()


def ts(t):
    t = max(0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def nettoie(mot):
    return re.sub(r"[^\w'’,.!?:%°\-àâäéèêëîïôöùûüçœÀÂÉÈÊÎÔÙÛÇ]", "", mot)


def fichier_ass(mots, sortie, style):
    """Sous-titres façon TikTok : 3 mots max à l'écran, mot prononcé en vert."""
    actif = couleur_ass(style.get("couleur_mot_actif", "#9BE39F"))
    entete = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Poppins ExtraBold,{style.get('taille_sous_titres', 84)},&H00FFFFFF,&H00FFFFFF,{couleur_ass('#1F3A26')},&H64000000,0,0,0,0,100,100,0,0,1,7,3,2,90,150,{style.get('marge_bas_sous_titres', 560)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    # découpe en groupes de 3 mots (on coupe aussi après la ponctuation)
    groupes, cur = [], []
    for m in mots:
        m = dict(m, mot=nettoie(m["mot"]))
        if not m["mot"]:
            continue
        cur.append(m)
        if len(cur) == 3 or re.search(r"[.!?,:]$", m["mot"]):
            groupes.append(cur)
            cur = []
    if cur:
        groupes.append(cur)

    lignes = []
    for gi, g in enumerate(groupes):
        fin_groupe = g[-1]["t"] + g[-1]["d"] + 0.25
        if gi + 1 < len(groupes):
            fin_groupe = min(fin_groupe, groupes[gi + 1][0]["t"])
        for i, m in enumerate(g):
            debut = m["t"]
            fin = g[i + 1]["t"] if i + 1 < len(g) else fin_groupe
            txt = " \\h".join(
                (f"{{\\c{actif}\\fscx108\\fscy108}}{x['mot'].upper()}{{\\r}}" if j == i else x["mot"].upper())
                for j, x in enumerate(g))
            lignes.append(f"Dialogue: 0,{ts(debut)},{ts(fin)},Sub,,0,0,0,,{txt}")
    Path(sortie).write_text(entete + "\n".join(lignes) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- plans vidéo
def filtre_cadrage(mode):
    if mode == "contain":   # image entière sur fond flou (photos carrées, captures)
        return (f"split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:2,eq=brightness=-0.06[bg];"
                f"[b]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2")
    return f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"


def rendu_plan(seg, dossier, d, overlay_png, voix_mp3, sortie, idx):
    fondu = "" if seg.get("type") == "hook" else "fade=in:st=0.10:d=0.30:alpha=1,"
    """Fabrique un plan de durée d : rush (vidéo ou photo) + overlay + voix + son du rush."""
    rush = (dossier / seg["rush"]).resolve()
    if not rush.exists():
        raise SystemExit(f"Rush introuvable : {rush}")
    est_image = rush.suffix.lower() in EXTS_IMAGE
    mode = seg.get("cadrage", "contain" if est_image else "cover")
    nb_images = int(round(d * FPS))
    entrees, filtres = [], []

    if est_image:
        # photo : zoom lent (Ken Burns), sens alterné d'un plan à l'autre
        zin = idx % 2 == 0
        z = f"1+0.10*on/{nb_images}" if zin else f"1.10-0.10*on/{nb_images}"
        entrees += ["-loop", "1", "-framerate", str(FPS), "-t", f"{d:.3f}", "-i", str(rush)]
        filtres.append(f"[0:v]{filtre_cadrage(mode)},scale={W*2}:{H*2},"
                       f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},"
                       f"setsar=1,format=yuv420p[v0]")
    else:
        debut = float(seg.get("debut", 0))
        dispo = max(0.1, duree(rush) - debut)
        vitesse = float(seg.get("vitesse", 1.0))
        utile = dispo / vitesse
        tempo = f"setpts=PTS/{vitesse}," if vitesse != 1.0 else ""
        if utile < d:  # rush trop court : ralenti (jusqu'à x0.5), puis image figée
            ralenti = max(0.5, utile / d)
            tempo = f"setpts=PTS/{vitesse * ralenti:.4f},"
            utile = dispo / (vitesse * ralenti)
        gel = f",tpad=stop_mode=clone:stop_duration={max(0, d - utile) + 0.1:.3f}" if utile < d else ""
        entrees += ["-ss", f"{debut:.3f}", "-i", str(rush)]
        filtres.append(f"[0:v]{tempo}{filtre_cadrage(mode)},fps={FPS}{gel},trim=duration={d:.3f},"
                       f"setpts=PTS-STARTPTS,setsar=1,format=yuv420p[v0]")

    # overlay DA, fondu d'apparition
    entrees += ["-loop", "1", "-framerate", str(FPS), "-t", f"{d:.3f}", "-i", str(overlay_png)]
    filtres.append(f"[1:v]format=rgba,{fondu}null[ov];[v0][ov]overlay=0:0:shortest=1[v]")

    # audio : voix off + son d'ambiance du rush (crunch, grésillement…) en fond
    pistes = []
    n = 2
    if voix_mp3:
        entrees += ["-i", str(voix_mp3)]
        ms = int(DELAI_VOIX * 1000)
        filtres.append(f"[{n}:a]aresample=48000,adelay={ms}|{ms},volume=1.0[vo]")
        pistes.append("[vo]")
        n += 1
    vol_rush = float(seg.get("son_rush", 0.0 if voix_mp3 else 0.8))
    if not est_image and vol_rush > 0 and a_audio(rush):
        filtres.append(f"[0:a]aresample=48000,atrim=duration={d:.3f},volume={vol_rush}[ra]")
        pistes.append("[ra]")
    entrees += ["-f", "lavfi", "-t", f"{d:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    pistes.append(f"[{n}:a]")
    filtres.append(f"{''.join(pistes)}amix=inputs={len(pistes)}:duration=longest:normalize=0,"
                   f"aformat=channel_layouts=stereo,atrim=duration={d:.3f}[a]")

    run(["ffmpeg", "-y", "-v", "error", *entrees, "-filter_complex", ";".join(filtres),
         "-map", "[v]", "-map", "[a]", "-t", f"{d:.3f}", "-r", str(FPS),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", str(sortie)])


# ---------------------------------------------------------------- pipeline
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("recette")
    ap.add_argument("-o", "--sortie")
    ap.add_argument("--garder-temp", action="store_true")
    a = ap.parse_args()

    fichier = Path(a.recette).resolve()
    r = json.loads(fichier.read_text(encoding="utf-8"))
    dossier = fichier.parent
    sortie = Path(a.sortie or ICI / "sorties" / (fichier.stem + ".mp4")).resolve()
    sortie.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="hf_"))
    style = r.get("style", {})
    handle = r.get("handle", "@healthyfry")
    voix = r.get("voix", VOIX_DEFAUT)
    cible = float(r.get("duree_min", 62))
    segs = r["segments"]

    # 1. voix off de chaque plan
    print(f"▶ Voix off ({voix})")
    for i, s in enumerate(segs):
        s["_mots"], s["_voix"] = [], None
        if s.get("voix"):
            mp3 = tmp / f"voix_{i:02d}.mp3"
            s["_mots"] = voix_off(s["voix"], voix, mp3, r.get("vitesse_voix", "+8%"))
            s["_voix"] = mp3
            s["_d"] = DELAI_VOIX + duree(mp3) + MARGE_FIN
        else:
            s["_d"] = 0
        s["_d"] = max(s["_d"], float(s.get("duree", 0)), 1.2)

    # 2. on garantit la durée minimale (monétisation : vidéo de plus d'1 min)
    total = sum(s["_d"] for s in segs)
    if total < cible:
        extensibles = [s for s in segs if s.get("etirable")] or [segs[-2] if len(segs) > 1 else segs[-1]]
        bonus = (cible - total) / len(extensibles)
        for s in extensibles:
            s["_d"] += bonus
        print(f"  durée naturelle {total:.1f}s, allongée à {cible:.1f}s (plans étirables)")
    total = sum(s["_d"] for s in segs)

    # 3. overlays DA
    print("▶ Overlays DA")
    specs = []
    for i, s in enumerate(segs):
        data = dict(s.get("ecran", {}), handle=handle)
        s["_ov"] = tmp / f"ov_{i:02d}.png"
        specs.append({"type": s.get("type", "vide"), "out": str(s["_ov"]), "data": data})
    (tmp / "specs.json").write_text(json.dumps(specs, ensure_ascii=False))
    run(["node", str(ICI / "overlays.js"), str(tmp / "specs.json")])

    # 4. plans
    print("▶ Plans")
    liste, t0, mots = [], 0.0, []
    for i, s in enumerate(segs):
        p = tmp / f"plan_{i:02d}.mp4"
        rendu_plan(s, dossier, s["_d"], s["_ov"], s["_voix"], p, i)
        liste.append(f"file '{p}'")
        if s.get("sous_titres", True):
            mots += [dict(m, t=m["t"] + t0 + DELAI_VOIX) for m in s["_mots"]]
        print(f"  {i+1:02d}/{len(segs)}  {s.get('type','?'):<11} {s['_d']:5.1f}s  {s['rush']}")
        t0 += s["_d"]
    (tmp / "liste.txt").write_text("\n".join(liste))
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / "liste.txt"),
         "-c", "copy", str(tmp / "assemble.mp4")])

    # 5. sous-titres + musique (baissée automatiquement sous la voix)
    print("▶ Sous-titres + musique + export")
    ass = tmp / "sous_titres.ass"
    fichier_ass(mots, ass, style)
    vf = f"ass={ass}:fontsdir={ICI / 'fonts'}"
    musique = r.get("musique")
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(tmp / "assemble.mp4")]
    if musique and (dossier / musique).exists():
        vol = float(r.get("volume_musique", 0.22))
        cmd += ["-stream_loop", "-1", "-i", str(dossier / musique), "-filter_complex",
                f"[0:v]{vf}[v];[0:a]asplit[v1][v2];[1:a]aresample=48000,volume={vol},afade=t=out:st={total-1.5:.2f}:d=1.5[m];"
                f"[m][v1]sidechaincompress=threshold=0.04:ratio=6:attack=20:release=400[md];"
                f"[v2][md]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]",
                "-map", "[v]", "-map", "[a]"]
    else:
        cmd += ["-vf", vf, "-af", "alimiter=limit=0.95"]
    cmd += ["-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
            "-profile:v", "high", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(sortie)]
    run(cmd)

    # 6. miniature + légende prête à coller
    run(["ffmpeg", "-y", "-v", "error", "-ss", "1.2", "-i", str(sortie), "-frames:v", "1", "-q:v", "3",
         str(sortie.with_suffix(".jpg"))])
    legende = r.get("legende", "")
    if r.get("hashtags"):
        legende += "\n\n" + " ".join("#" + h.lstrip("#") for h in r["hashtags"])
    sortie.with_suffix(".txt").write_text(legende.strip() + "\n", encoding="utf-8")

    if not a.garder_temp:
        shutil.rmtree(tmp, ignore_errors=True)
    else:
        print(f"  fichiers temporaires : {tmp}")
    print(f"✅ {sortie}  ({duree(sortie):.1f}s)")


if __name__ == "__main__":
    main()
