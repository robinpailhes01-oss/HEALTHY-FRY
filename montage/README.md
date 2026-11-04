# Montage automatique Healthy Fry (vidéos de 61 s ou plus, monétisables)

Tu filmes tes rushes au téléphone (mains et airfryer, sans visage) et tu remplis un fichier recette JSON.
Le script sort une vidéo TikTok prête à publier :

- format **1080×1920, 30 fps, d'au moins 62 s** (seuil du programme de rémunération des créateurs)
- **voix off FR gratuite** (Microsoft Edge TTS, voix `fr-FR-VivienneMultilingualNeural`)
- **sous-titres mot à mot** façon TikTok (3 mots à l'écran, le mot prononcé passe en vert)
- **overlays dans la DA Healthy Fry** : titre d'accroche, carte ingrédients, pastilles d'étapes numérotées, badge température et temps, carte d'appel à l'action finale, @healthyfry discret
- son d'ambiance des rushes conservé (le croustillant, le grésillement), musique optionnelle baissée automatiquement sous la voix
- une **miniature** `.jpg` et la **légende** `.txt` avec les hashtags, prête à coller

Coût : **0 €**. Tout tourne en local (ffmpeg + Chromium + edge-tts).

## Installation (une seule fois)

```bash
pip install edge-tts
```

```bash
npm i -g playwright && npx playwright install chromium
```

Il faut aussi `ffmpeg` (`brew install ffmpeg` sur Mac, ou `sudo apt install ffmpeg`).

## Utilisation

```bash
python3 montage/render.py montage/exemple/cookie-fondant.json
```

Le résultat arrive dans `montage/sorties/cookie-fondant.mp4`, avec le `.jpg` et le `.txt` à côté. Compter environ 2-3 min de rendu.

## Le fichier recette

```jsonc
{
  "handle": "@healthyfry",
  "voix": "fr-FR-VivienneMultilingualNeural",   // ou fr-FR-RemyMultilingualNeural (voix d'homme)
  "vitesse_voix": "+8%",
  "duree_min": 62,                    // la vidéo est allongée si besoin pour dépasser 1 min
  "musique": null,                    // "musique/lofi.mp3" : à éviter, ajoute plutôt un son tendance dans TikTok
  "legende": "…", "hashtags": ["airfryer", "…"],
  "segments": [
    { "type": "hook",        "rush": "rushes/final.mp4", "voix": "…", "ecran": { "titre": "…", "badge": "Prêt en 8 min" } },
    { "type": "ingredients", "rush": "rushes/ingr.mp4",  "voix": "…", "ecran": { "titre": "Pour 4 cookies", "liste": ["1 œuf", "…"] } },
    { "type": "etape",       "rush": "rushes/e1.mp4",    "voix": "…", "ecran": { "num": 1, "texte": "Beurre mou + sucre", "badge": "160°C · 8 min" } },
    { "type": "resultat",    "rush": "rushes/coupe.mp4", "voix": "…", "etirable": true, "ecran": { "titre": "Le résultat", "macros": "…" } },
    { "type": "cta",         "rush": "rushes/fin.mp4",   "voix": "…", "ecran": { "titre": "Enregistre la recette", "texte": "…", "handle": "@healthyfry" } }
  ]
}
```

Options par segment :

| Clé | Effet |
|---|---|
| `rush` | Vidéo (`.mp4`, `.mov`) ou photo (`.jpg`, `.png`). Les photos reçoivent un zoom lent automatique |
| `debut` | Seconde de départ dans le rush (par défaut 0) |
| `vitesse` | 2 = accéléré x2 (pratique pour les mélanges) |
| `son_rush` | Volume du son d'origine (par exemple 0.3 pour garder le croustillant sous la voix) |
| `cadrage` | `cover` (plein écran, défaut pour les vidéos) ou `contain` (fond flou, défaut pour les photos) |
| `duree` | Durée minimale du plan, utile s'il n'y a pas de voix |
| `etirable` | Ce plan est allongé si la vidéo fait moins de `duree_min` |
| `sous_titres` | `false` pour masquer les sous-titres de ce plan |

**Durée d'un plan = durée de sa phrase de voix off.** Si le rush est trop court, il est ralenti (jusqu'à x0,5), puis la dernière image reste figée.

## Méthode de tournage (environ 1 h par semaine pour 4-5 vidéos)

1. Téléphone en **4K/1080p vertical**, sur trépied au-dessus du plan de travail, avec de la lumière du jour.
2. Pour chaque recette, filmer **8 plans de 5-10 s** :
   - le **plan final appétissant** (cookie coupé, fromage qui file), qui sert de hook ET de résultat
   - les ingrédients alignés
   - un plan par étape (on ne voit que les mains)
   - l'ouverture du panier de l'airfryer en gros plan
3. Nommer les fichiers `hook.mp4`, `ingr.mp4`, `e1.mp4`… dans `rushes/` et dupliquer la recette JSON.
4. Lancer le rendu, puis publier dans TikTok en ajoutant un **son tendance à 5-10 %**.

Le script et la voix off se génèrent avec Claude : il suffit de donner le nom de la recette et les rushes disponibles.

## Exemple fourni

`exemple/` contient une recette de démo (le cookie fondant, qui avait fait 211k vues en carrousel).
Les « rushes » sont des **photos tirées des anciens carrousels**, juste pour tester le pipeline.
**Ne pas publier cette démo telle quelle** : TikTok ne rémunère que les vidéos originales filmées.
