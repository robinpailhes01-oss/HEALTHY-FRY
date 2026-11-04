#!/usr/bin/env python3
"""Génère les clips vidéo IA d'une recette via kie.ai (image Nano Banana 2.1, puis animation Wan ou Seedance).

Usage :
    python3 montage/generer_visuels.py montage/exemple/cookie-fondant-ia.json [--estimer]

Dans la recette, chaque segment peut avoir une clé "ia" : liste de plans
    {"id": "melange_beurre", "image": "prompt image", "video": "prompt mouvement", "modele": "wan" | "seedance"}
Les clips sont enregistrés dans <dossier recette>/ia/<id>.mp4. Un clip déjà présent n'est PAS regénéré
(aucun crédit dépensé). render.py utilise ensuite automatiquement ces clips comme visuels.
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kie  # noqa: E402

MODELES = {
    # nom court : (modèle kie, construction de l'entrée, coût mesuré en crédits pour 5 s en 720p)
    "wan": ("wan/2-6-flash-image-to-video",
            lambda img, p: {"prompt": p, "image_urls": [img], "duration": "5", "resolution": "720p",
                            "audio": False, "multi_shots": False}, 20),
    "seedance": ("bytedance/seedance-2-mini",
                 lambda img, p: {"prompt": p, "first_frame_url": img, "resolution": "720p", "aspect_ratio": "9:16",
                                 "duration": 5, "generate_audio": False}, 41),
}
COUT_IMAGE = 4
NEGATIF = "ultra realistic, appetizing, no text, no logo, no face"


def plan_complet(p, style):
    img = f"Vertical 9:16 food video frame. {p['image']}. {style}. {NEGATIF}"
    vid = f"{p['video']}. Realistic food video, natural motion, hands only, no face, stable camera."
    return img, vid


def generer(p, style, dossier):
    sortie = dossier / "ia" / f"{p['id']}.mp4"
    img_prompt, vid_prompt = plan_complet(p, style)
    t = time.time()
    tid = kie.creer("nano-banana-2-1", {"prompt": img_prompt, "aspect_ratio": "9:16", "resolution": "1K", "output_format": "jpg"})
    urls, _ = kie.attendre(tid, pas=4)
    kie.telecharger(urls[0], sortie.with_suffix(".jpg"))
    modele, entree, _ = MODELES[p.get("modele", "wan")]
    tid = kie.creer(modele, entree(urls[0], vid_prompt))
    urls, info = kie.attendre(tid, pas=8)
    kie.telecharger(urls[0], sortie)
    return p["id"], info.get("creditsConsumed"), round(time.time() - t)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("recette")
    ap.add_argument("--estimer", action="store_true", help="affiche le coût sans rien générer")
    ap.add_argument("--paralleles", type=int, default=4)
    a = ap.parse_args()
    fichier = Path(a.recette).resolve()
    r = json.loads(fichier.read_text(encoding="utf-8"))
    style = r.get("style_visuel", "")
    plans = [p for s in r["segments"] for p in s.get("ia", [])]
    vus, a_faire = set(), []
    for p in plans:
        if p["id"] in vus:
            continue
        vus.add(p["id"])
        if not (fichier.parent / "ia" / f"{p['id']}.mp4").exists():
            a_faire.append(p)
    cout = sum(COUT_IMAGE + MODELES[p.get("modele", "wan")][2] for p in a_faire)
    print(f"{len(vus)} plans IA, {len(vus) - len(a_faire)} déjà en cache, {len(a_faire)} à générer")
    print(f"coût estimé : {cout} crédits (≈ {cout * 0.005:.2f} $)")
    if a.estimer or not a_faire:
        return
    solde = kie.credits()
    print(f"solde kie.ai : {solde} crédits")
    if solde < cout:
        raise SystemExit("Solde insuffisant.")
    total = 0
    with ThreadPoolExecutor(a.paralleles) as ex:
        for fut in [ex.submit(generer, p, style, fichier.parent) for p in a_faire]:
            try:
                pid, cr, sec = fut.result()
                total += (cr or 0) + COUT_IMAGE
                print(f"  ✓ {pid}  ({cr} crédits vidéo, {sec}s)")
            except Exception as e:  # on continue les autres plans
                print(f"  ✗ {e}")
    print(f"terminé, environ {total} crédits dépensés, solde : {kie.credits()}")


if __name__ == "__main__":
    main()
