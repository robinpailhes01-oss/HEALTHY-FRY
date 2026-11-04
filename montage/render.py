#!/usr/bin/env python3
"""Healthy Fry : montage automatique de vidéos TikTok 9:16 de 61 s ou plus.

Usage :
    python3 montage/render.py montage/exemple/cookie-fondant.json [-o sortie.mp4]

Entrée : un fichier recette JSON (voir montage/README.md) + des visuels (clips vidéo IA ou photos).
Sortie : MP4 1080x1920 30 fps avec voix off FR, sous-titres animés mot à mot, overlays animés
         DA Healthy Fry, plans courts, bruitages, barre de progression,
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
import unicodedata
from pathlib import Path

ICI = Path(__file__).resolve().parent
SFX = ICI / "sfx"
W, H, FPS = 1080, 1920, 30
VOIX_DEFAUT = "fr-FR-VivienneMultilingualNeural"
DELAI_VOIX = 0.15     # la voix démarre 150 ms après le début du plan
MARGE_FIN = 0.30      # silence après chaque phrase
PLAN_CIBLE = 2.1      # durée visée d'un plan avant changement de cadrage (rythme TikTok)
EXTS_IMAGE = {".jpg", ".jpeg", ".png", ".webp"}
VERT_CLAIR = "6BAF6E"


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.stderr.write(" ".join(map(str, cmd))[:3000] + "\n" + r.stderr[-3000:])
        raise SystemExit(f"Échec : {cmd[0]}")
    return r.stdout


def duree(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                      "-of", "default=nw=1:nk=1", str(path)]).strip())


def a_audio(path):
    return bool(run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
                     "stream=index", "-of", "csv=p=0", str(path)]).strip())


def sans_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------- bruitages (générés, libres de droits)
SONS = {
    "whoosh": "anoisesrc=d=0.45:c=pink:a=0.9,highpass=f=600,lowpass=f=6000,"
              "afade=t=in:d=0.28:curve=exp,afade=t=out:st=0.28:d=0.17,volume=0.9",
    "pop":    "aevalsrc='0.8*sin(2*PI*(500+1800*exp(-45*t))*t)*exp(-28*t)':d=0.16:s=48000",
    "ding":   "aevalsrc='0.45*(sin(2*PI*1568*t)+0.45*sin(2*PI*3136*t)+0.2*sin(2*PI*4704*t))*exp(-3.2*t)':d=1.6:s=48000",
    "tick":   "aevalsrc='0.6*sin(2*PI*2400*t)*exp(-90*t)':d=0.05:s=48000",
}


def prepare_sfx():
    SFX.mkdir(exist_ok=True)
    for nom, src in SONS.items():
        f = SFX / f"{nom}.wav"
        if not f.exists():
            run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", src, "-ac", "2", "-ar", "48000", str(f)])


# ---------------------------------------------------------------- voix off (gratuite)
def _patch_ca():
    """edge-tts force le bundle certifi : on le redirige vers le CA système si besoin."""
    ca = os.environ.get("SSL_CERT_FILE") or ("/root/.ccr/ca-bundle.crt" if Path("/root/.ccr/ca-bundle.crt").exists() else None)
    if ca:
        import certifi
        certifi.where = lambda: ca


async def _tts(texte, voix, sortie, vitesse, hauteur):
    import edge_tts
    com = edge_tts.Communicate(texte, voix, rate=vitesse, pitch=hauteur, boundary="WordBoundary")
    mots = []
    with open(sortie, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                mots.append({"t": ch["offset"] / 1e7, "d": ch["duration"] / 1e7, "mot": ch["text"]})
    return mots


def voix_off(texte, voix, sortie, vitesse="+10%", hauteur="+0Hz"):
    _patch_ca()
    mots = asyncio.run(_tts(texte, voix, sortie, vitesse, hauteur))
    # edge-tts enlève la ponctuation : on la retrouve dans le texte source pour couper les sous-titres aux phrases
    pos = 0
    for m in mots:
        i = texte.find(m["mot"], pos)
        if i < 0:
            continue
        pos = i + len(m["mot"])
        suite = texte[pos:pos + 3].lstrip()
        m["fin"] = bool(suite[:1] and suite[0] in ".!?,:;…")
    if mots:
        mots[-1]["fin"] = True
    return mots


def instants_ingredients(liste, mots, n_defaut):
    """Fait apparaître chaque ingrédient quand la voix le prononce."""
    res, cur = [], 0
    for k, ing in enumerate(liste):
        cles = [w for w in re.findall(r"[a-zà-ÿœ]+", sans_accents(ing)) if len(w) >= 3
                and w not in {"pour", "des", "une", "cac", "cas", "pincee", "chimique"}]
        t = None
        for j in range(cur, len(mots)):
            if any(sans_accents(mots[j]["mot"]).startswith(c[:5]) for c in cles):
                t, cur = mots[j]["t"] + DELAI_VOIX - 0.1, j + 1
                break
        res.append(t)
    # trous éventuels : interpolation régulière
    fin = (mots[-1]["t"] if mots else n_defaut) + DELAI_VOIX
    for k, t in enumerate(res):
        if t is None:
            prev = next((res[j] for j in range(k - 1, -1, -1) if res[j] is not None), 0.3)
            res[k] = prev + 0.5
    return [max(0.3, min(t, fin)) for t in res]


# ---------------------------------------------------------------- sous-titres ASS
def couleur_ass(hexa):
    hexa = hexa.lstrip("#")
    return f"&H00{hexa[4:6]}{hexa[2:4]}{hexa[0:2]}".upper()


def ts(t):
    t = max(0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def nettoie(mot):
    return re.sub(r"[^\w'’,.!?:%°\-]", "", mot)


def fichier_ass(mots, sortie, style):
    """Sous-titres façon TikTok : 3 mots max, entrée en rebond, mot prononcé en vert."""
    actif = couleur_ass(style.get("couleur_mot_actif", "#9BE39F"))
    entete = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Poppins ExtraBold,{style.get('taille_sous_titres', 86)},&H00FFFFFF,&H00FFFFFF,{couleur_ass('#1F3A26')},&H64000000,0,0,0,0,100,100,1,0,1,7,3,2,90,150,{style.get('marge_bas_sous_titres', 560)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    groupes, cur = [], []
    for m in mots:
        m = dict(m, mot=nettoie(m["mot"]))
        if not m["mot"]:
            continue
        cur.append(m)
        if len(cur) == 3 or m.get("fin") or re.search(r"[.!?,:]$", m["mot"]):
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
            rebond = "{\\fscx70\\fscy70\\t(0,110,\\fscx100\\fscy100)}" if i == 0 else ""
            txt = " \\h".join(
                (f"{{\\c{actif}\\fscx110\\fscy110}}{x['mot'].upper()}{{\\r}}" if j == i else x["mot"].upper())
                for j, x in enumerate(g))
            lignes.append(f"Dialogue: 0,{ts(debut)},{ts(fin)},Sub,,0,0,0,,{rebond}{txt}")
    Path(sortie).write_text(entete + "\n".join(lignes) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- visuels
def cadrage(mode, fx=0.5, fy=0.5, serre=1.0):
    """Filtre ffmpeg produisant une image 1080x1920.
    contain = image entière sur fond flou ; cover = plein écran ; serre>1 = gros plan."""
    if mode == "contain":
        return (f"split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:2,eq=brightness=-0.06[bg];"
                f"[b]scale={W}:{H}:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2")
    s = f"crop=iw/{serre}:ih/{serre}:(iw-iw/{serre})*{fx}:(ih-ih/{serre})*{fy}," if serre > 1 else ""
    return (f"{s}scale={W}:{H}:force_original_aspect_ratio=increase,"
            f"crop={W}:{H}:(iw-{W})*{fx}:(ih-{H})*{fy}")


# variations de cadrage pour une photo : on alterne plan large / plan serré pour créer du rythme
CADRAGES_PHOTO = [
    ("contain", 0.5, 0.5, 1.0),
    ("cover",   0.5, 0.5, 1.0),
    ("cover",   0.3, 0.45, 1.5),
    ("contain", 0.5, 0.5, 1.0),
    ("cover",   0.7, 0.55, 1.6),
    ("cover",   0.5, 0.5, 1.25),
]


def plans_photo(chemin, d, idx_seg, premier, entrees, filtres, prefixe):
    """Découpe une photo en plusieurs plans courts (cadrages variés + zoom), renvoie le label de sortie."""
    n = max(1, round(d / PLAN_CIBLE))
    durees = [d / n] * n
    k = len(entrees) // 2  # indice d'entrée ffmpeg (paires "-i x")
    entrees += ["-loop", "1", "-framerate", str(FPS), "-t", f"{d + 0.5:.3f}", "-i", str(chemin)]
    k = entrees.count("-i") - 1
    filtres.append(f"[{k}:v]split={n}" + "".join(f"[{prefixe}s{i}]" for i in range(n)))
    labels = []
    for i, di in enumerate(durees):
        mode, fx, fy, serre = CADRAGES_PHOTO[(idx_seg * 2 + i) % len(CADRAGES_PHOTO)]
        nb = max(2, int(round(di * FPS)))
        if premier and i == 0:   # accroche : coup de zoom sur la 1re image
            z = f"if(lt(on,8),1.28-0.28*on/8,1+0.04*(on-8)/{nb})"
        elif i % 2 == 0:
            z = f"1+0.09*on/{nb}"
        else:
            z = f"1.09-0.09*on/{nb}"
        filtres.append(
            f"[{prefixe}s{i}]{cadrage(mode, fx, fy, serre)},scale={W*2}:{H*2},"
            f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={W}x{H}:fps={FPS},"
            f"trim=end_frame={nb},setpts=PTS-STARTPTS,setsar=1,format=yuv420p[{prefixe}p{i}]")
        labels.append(f"[{prefixe}p{i}]")
    if n == 1:
        return labels[0], k
    filtres.append("".join(labels) + f"concat=n={n}:v=1:a=0[{prefixe}out]")
    return f"[{prefixe}out]", k


def plan_video(chemin, d, seg, entrees, filtres, prefixe, idx=0):
    """Clip vidéo plein écran. Trop court : léger ralenti, puis aller-retour (boomerang).
    Long à l'écran : recoupé en plans de ~2,5 s alternant cadrage large et cadrage serré."""
    debut = float(seg.get("debut", 0))
    fin = min(float(seg.get("fin", 1e9)), duree(chemin))
    dispo = max(0.1, fin - debut)
    vitesse = float(seg.get("vitesse", 1.0))
    utile = dispo / vitesse
    if utile < d:
        vitesse *= max(0.75, utile / d)
        utile = dispo / vitesse
    boomerang = utile < d
    if boomerang:
        utile *= 2
    gel = f",tpad=stop_mode=clone:stop_duration={d - utile + 0.1:.3f}" if utile < d else ""
    entrees += ["-ss", f"{debut:.3f}", "-i", str(chemin)]
    k = entrees.count("-i") - 1
    chaine = f"[{k}:v]trim=duration={dispo:.3f},setpts=(PTS-STARTPTS)/{vitesse:.4f},fps={FPS}"
    if boomerang:
        chaine += f",split[{prefixe}f][{prefixe}b];[{prefixe}b]reverse[{prefixe}rv];[{prefixe}f][{prefixe}rv]concat=n=2:v=1:a=0"
    chaine += (f",{cadrage(seg.get('cadrage', 'cover'))}{gel},trim=duration={d:.3f},"
               f"setpts=PTS-STARTPTS,setsar=1,format=yuv420p")
    n = max(1, round(d / 2.5))
    if n == 1:
        filtres.append(chaine + f"[{prefixe}out]")
        return f"[{prefixe}out]", k
    filtres.append(chaine + f",split={n}" + "".join(f"[{prefixe}s{i}]" for i in range(n)))
    di, labels = d / n, []
    for i in range(n):
        f = f"[{prefixe}s{i}]trim=start={i * di:.3f}:duration={di:.3f},setpts=PTS-STARTPTS"
        if (i + idx) % 2 == 1:  # plan serré
            fx, fy = [(0.5, 0.45), (0.35, 0.55), (0.65, 0.5)][(i + idx) % 3]
            f += f",crop=iw/1.3:ih/1.3:(iw-iw/1.3)*{fx}:(ih-ih/1.3)*{fy},scale={W}:{H}"
        filtres.append(f + f",setsar=1[{prefixe}p{i}]")
        labels.append(f"[{prefixe}p{i}]")
    filtres.append("".join(labels) + f"concat=n={n}:v=1:a=0[{prefixe}out]")
    return f"[{prefixe}out]", k


def rendu_plan(seg, dossier, d, ov_concat, voix_mp3, sortie, idx):
    """Un segment = visuels (1 ou plusieurs, découpés en plans courts) + overlay animé + voix + son du clip."""
    rushes = seg["rush"] if isinstance(seg["rush"], list) else [seg["rush"]]
    rushes = [(dossier / r).resolve() for r in rushes]
    for r in rushes:
        if not r.exists():
            raise SystemExit(f"Visuel introuvable : {r}")
    entrees, filtres, labels, audio_clip = [], [], [], []
    part = d / len(rushes)
    for i, r in enumerate(rushes):
        if r.suffix.lower() in EXTS_IMAGE:
            lab, _ = plans_photo(r, part, idx + i, seg.get("type") == "hook" and i == 0, entrees, filtres, f"r{i}")
        else:
            lab, k = plan_video(r, part, seg, entrees, filtres, f"r{i}", idx + i)
            if a_audio(r) and float(seg.get("son_rush", 0.35)) > 0:
                audio_clip.append((k, part, i * part))
        labels.append(lab)
    if len(labels) > 1:
        filtres.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0[base]")
    else:
        filtres.append(f"{labels[0]}null[base]")

    # overlay animé (séquence PNG)
    entrees += ["-f", "concat", "-safe", "0", "-i", str(ov_concat)]
    k_ov = entrees.count("-i") - 1
    filtres.append(f"[{k_ov}:v]fps={FPS},format=rgba,tpad=stop_mode=clone:stop_duration={d:.3f}[ov];"
                   f"[base][ov]overlay=0:0:eof_action=repeat,trim=duration={d:.3f}[v]")

    # audio
    pistes = []
    if voix_mp3:
        entrees += ["-i", str(voix_mp3)]
        k = entrees.count("-i") - 1
        ms = int(DELAI_VOIX * 1000)
        filtres.append(f"[{k}:a]aresample=48000,adelay={ms}|{ms}[vo]")
        pistes.append("[vo]")
    for j, (k, dur, dec) in enumerate(audio_clip):
        vol = float(seg.get("son_rush", 0.35))
        ms = int(dec * 1000)
        filtres.append(f"[{k}:a]aresample=48000,atrim=duration={dur:.3f},volume={vol},adelay={ms}|{ms}[ca{j}]")
        pistes.append(f"[ca{j}]")
    entrees += ["-f", "lavfi", "-t", f"{d:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    pistes.append(f"[{entrees.count('-i') - 1}:a]")
    filtres.append(f"{''.join(pistes)}amix=inputs={len(pistes)}:duration=longest:normalize=0,"
                   f"aformat=channel_layouts=stereo,atrim=duration={d:.3f}[a]")

    run(["ffmpeg", "-y", "-v", "error", *entrees, "-filter_complex", ";".join(filtres),
         "-map", "[v]", "-map", "[a]", "-t", f"{d:.3f}", "-r", str(FPS),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p",
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
    for s in segs:  # visuels IA générés par generer_visuels.py
        if "rush" not in s and s.get("ia"):
            s["rush"] = [f"ia/{p['id']}.mp4" for p in s["ia"]]
    prepare_sfx()

    # 1. voix off
    print(f"▶ Voix off ({voix})")
    for i, s in enumerate(segs):
        s["_mots"], s["_voix"] = [], None
        if s.get("voix"):
            mp3 = tmp / f"voix_{i:02d}.mp3"
            s["_mots"] = voix_off(s["voix"], voix, mp3, r.get("vitesse_voix", "+10%"), r.get("hauteur_voix", "+0Hz"))
            s["_voix"] = mp3
            s["_d"] = DELAI_VOIX + duree(mp3) + MARGE_FIN
        else:
            s["_d"] = 0
        s["_d"] = max(s["_d"], float(s.get("duree", 0)), 1.2)

    # 2. durée minimale (monétisation : plus d'1 min)
    total = sum(s["_d"] for s in segs)
    if total < cible:
        ext = [s for s in segs if s.get("etirable")] or [segs[-2] if len(segs) > 1 else segs[-1]]
        for s in ext:
            s["_d"] += (cible - total) / len(ext)
        print(f"  durée naturelle {total:.1f}s, allongée à {cible:.1f}s")
    total = sum(s["_d"] for s in segs)

    # 3. overlays animés
    print("▶ Overlays animés")
    specs = []
    for i, s in enumerate(segs):
        ecran = dict(s.get("ecran", {}), handle=handle)
        reveal = []
        if s.get("type") == "ingredients":
            reveal = instants_ingredients(ecran.get("liste", []), s["_mots"], s["_d"])
        s["_reveal"] = reveal
        s["_ov"] = tmp / f"ov_{i:02d}"
        specs.append({"type": s.get("type", "vide"), "prefix": str(s["_ov"]), "duree": s["_d"],
                      "reveal": reveal, "data": ecran})
    (tmp / "specs.json").write_text(json.dumps(specs, ensure_ascii=False))
    run(["node", str(ICI / "overlays.js"), str(tmp / "specs.json")])

    # 4. segments
    print("▶ Plans")
    liste, t0, mots, sfx = [], 0.0, [], []
    for i, s in enumerate(segs):
        p = tmp / f"plan_{i:02d}.mp4"
        rendu_plan(s, dossier, s["_d"], Path(str(s["_ov"]) + ".ffconcat"), s["_voix"], p, i)
        liste.append(f"file '{p}'")
        if s.get("sous_titres", True):
            mots += [dict(m, t=m["t"] + t0 + DELAI_VOIX) for m in s["_mots"]]
        # bruitages : whoosh aux transitions, pop sur les textes, ding au résultat
        if i > 0:
            sfx.append(("whoosh", t0 - 0.22, 0.55))
        if s.get("type") in ("hook", "etape", "resultat", "cta"):
            sfx.append(("pop", t0 + 0.05, 0.45))
        if s.get("type") == "resultat":
            sfx.append(("ding", t0 + 0.05, 0.6))
        for tr in s["_reveal"]:
            sfx.append(("tick", t0 + tr, 0.5))
        rushes = s["rush"] if isinstance(s["rush"], list) else [s["rush"]]
        print(f"  {i+1:02d}/{len(segs)}  {s.get('type','?'):<11} {s['_d']:5.1f}s  {', '.join(rushes)}")
        t0 += s["_d"]
    (tmp / "liste.txt").write_text("\n".join(liste))
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / "liste.txt"),
         "-c", "copy", str(tmp / "assemble.mp4")])

    # 5. sous-titres + barre de progression + bruitages + musique
    print("▶ Sous-titres, bruitages, export")
    ass = tmp / "sous_titres.ass"
    fichier_ass(mots, ass, style)
    entrees = ["-i", str(tmp / "assemble.mp4"),
               "-f", "lavfi", "-i", f"color=c=0x{VERT_CLAIR}:s={W}x12:r={FPS}"]
    fc = [f"[0:v]ass={ass}:fontsdir={ICI / 'fonts'}[sub]",
          f"[sub][1:v]overlay=x='-W+W*t/{total:.3f}':y=0:shortest=1[v]"]
    pistes = ["[0:a]"]
    n = 2
    for j, (nom, t, vol) in enumerate(s for s in sfx if s[1] >= 0):
        entrees += ["-i", str(SFX / f"{nom}.wav")]
        ms = int(t * 1000)
        fc.append(f"[{n}:a]volume={vol},adelay={ms}|{ms}[x{j}]")
        pistes.append(f"[x{j}]")
        n += 1
    fc.append(f"{''.join(pistes)}amix=inputs={len(pistes)}:duration=first:normalize=0[mix]")
    musique = r.get("musique")
    if musique and (dossier / musique).exists():
        entrees += ["-stream_loop", "-1", "-i", str(dossier / musique)]
        vol = float(r.get("volume_musique", 0.22))
        fc += [f"[mix]asplit[m1][m2]",
               f"[{n}:a]aresample=48000,volume={vol},afade=t=out:st={total-1.5:.2f}:d=1.5[mu]",
               f"[mu][m1]sidechaincompress=threshold=0.04:ratio=6:attack=20:release=400[mud]",
               f"[m2][mud]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]"]
    else:
        fc.append("[mix]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]")
    run(["ffmpeg", "-y", "-v", "error", *entrees, "-filter_complex", ";".join(fc),
         "-map", "[v]", "-map", "[a]", "-t", f"{total:.3f}",
         "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-profile:v", "high",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(sortie)])

    # 6. miniature + légende
    run(["ffmpeg", "-y", "-v", "error", "-ss", "0.4", "-i", str(sortie), "-frames:v", "1", "-q:v", "3",
         str(sortie.with_suffix(".jpg"))])
    legende = r.get("legende", "")
    if r.get("hashtags"):
        legende += "\n\n" + " ".join("#" + h.lstrip("#") for h in r["hashtags"])
    sortie.with_suffix(".txt").write_text(legende.strip() + "\n", encoding="utf-8")

    if a.garder_temp:
        print(f"  fichiers temporaires : {tmp}")
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"✅ {sortie}  ({duree(sortie):.1f}s)")


if __name__ == "__main__":
    main()
