"""Client ElevenLabs : voix off avec timing mot à mot + génération d'effets sonores.
Clé lue dans la variable d'environnement ELEVENLABS_API_KEY."""
import base64
import json
import os
import urllib.request

# api.us.elevenlabs.io : adresse officielle (région US), utilisée car le proxy de cet environnement
# réécrit l'authentification vers api.elevenlabs.io.
API = os.environ.get("ELEVENLABS_API_BASE", "https://api.us.elevenlabs.io/v1")


def dispo():
    return bool(os.environ.get("ELEVENLABS_API_KEY"))


def _req(chemin, corps=None, brut=False):
    req = urllib.request.Request(API + chemin, data=json.dumps(corps).encode() if corps is not None else None,
                                 method="POST" if corps is not None else "GET",
                                 headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = r.read()
    return data if brut else json.loads(data)


def voix_off(texte, voice_id, sortie, modele="eleven_v3", stabilite=0.5, style=0.45, vitesse=1.0):
    """Génère la voix et renvoie les mots avec leurs instants [{t, d, mot}]."""
    rep = _req(f"/text-to-speech/{voice_id}/with-timestamps?output_format=mp3_44100_128", {
        "text": texte, "model_id": modele,
        "voice_settings": {"stability": stabilite, "similarity_boost": 0.8, "style": style,
                           "use_speaker_boost": True, "speed": vitesse}})
    with open(sortie, "wb") as f:
        f.write(base64.b64decode(rep["audio_base64"]))
    al = rep.get("normalized_alignment") or rep["alignment"]
    mots, cur, debut, fin = [], "", None, 0
    for c, a, b in zip(al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]):
        if c.isspace():
            if cur:
                mots.append({"t": debut, "d": fin - debut, "mot": cur})
            cur, debut = "", None
            continue
        if debut is None:
            debut = a
        cur += c
        fin = b
    if cur:
        mots.append({"t": debut, "d": fin - debut, "mot": cur})
    # les balises d'émotion v3 ([excited], [laughs]…) ne doivent pas apparaître dans les sous-titres
    propres, dans_balise = [], False
    for m in mots:
        if m["mot"].startswith("["):
            dans_balise = True
        if not dans_balise:
            propres.append(m)
        if m["mot"].endswith("]") or "]" in m["mot"]:
            dans_balise = False
            reste = m["mot"].split("]", 1)[1]
            if reste:
                propres.append(dict(m, mot=reste))
    return propres


def effet_sonore(description, sortie, duree=None, influence=0.5):
    corps = {"text": description, "prompt_influence": influence}
    if duree:
        corps["duration_seconds"] = duree
    with open(sortie, "wb") as f:
        f.write(_req("/sound-generation?output_format=mp3_44100_128", corps, brut=True))
    return sortie


def chercher_voix(requete="", langue="fr", genre="female", n=30):
    """Voix de la bibliothèque partagée (pour choisir une voix FR naturelle)."""
    q = urllib.parse.urlencode({"page_size": n, "search": requete, "language": langue, "gender": genre, "sort": "usage_character_count_1y"})
    return _req(f"/shared-voices?{q}")["voices"]


import urllib.parse  # noqa: E402
