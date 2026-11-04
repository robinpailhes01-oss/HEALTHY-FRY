"""Petit client kie.ai (images et vidéos IA). Clé lue dans la variable d'environnement KIE_API_KEY."""
import json
import os
import time
import urllib.request
from pathlib import Path

API = "https://api.kie.ai/api/v1"


def _cle():
    k = os.environ.get("KIE_API_KEY")
    if not k:
        raise SystemExit("KIE_API_KEY manquante (ajoute-la dans les variables d'environnement).")
    return k


def _req(methode, chemin, corps=None):
    data = json.dumps(corps).encode() if corps is not None else None
    req = urllib.request.Request(API + chemin, data=data, method=methode, headers={
        "Authorization": f"Bearer {_cle()}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        rep = json.load(r)
    if rep.get("code") != 200:
        raise RuntimeError(f"kie.ai {chemin} : {rep.get('code')} {rep.get('msg')}")
    return rep.get("data")


def credits():
    return _req("GET", "/chat/credit")


def creer(modele, entree):
    return _req("POST", "/jobs/createTask", {"model": modele, "input": entree})["taskId"]


def attendre(task_id, delai_max=900, pas=6):
    """Attend la fin d'une tâche, renvoie (urls, infos)."""
    debut = time.time()
    while time.time() - debut < delai_max:
        d = _req("GET", f"/jobs/recordInfo?taskId={task_id}")
        etat = d.get("state")
        if etat == "success":
            res = json.loads(d.get("resultJson") or "{}")
            urls = (res.get("resultUrls") or (res.get("data") or {}).get("result_urls")
                    or res.get("result_urls") or (res.get("data") or {}).get("origin_urls") or [])
            return urls, d
        if etat == "fail":
            raise RuntimeError(f"Tâche {task_id} échouée : {d.get('failMsg') or d.get('failCode')}")
        time.sleep(pas)
    raise TimeoutError(f"Tâche {task_id} trop longue")


def telecharger(url, chemin):
    Path(chemin).parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=180) as r, open(chemin, "wb") as f:
        f.write(r.read())
    return chemin
