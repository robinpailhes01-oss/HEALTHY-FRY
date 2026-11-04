# Montage automatique Healthy Fry (vidéos de 61 s ou plus, monétisables)

À partir d'un fichier recette JSON et de visuels (clips vidéo IA ou photos), le script sort une vidéo TikTok prête à publier :

- format **1080×1920, 30 fps, d'au moins 62 s** (seuil du programme de rémunération des créateurs)
- **voix off FR gratuite** (Microsoft Edge TTS, voix `fr-FR-VivienneMultilingualNeural`)
- **rythme TikTok** : un changement de plan toutes les 2 s environ (cadrages large et serré alternés, zooms), coup de zoom sur l'accroche
- **sous-titres mot à mot animés** : 3 mots à l'écran, entrée en rebond, le mot prononcé passe en vert, coupure aux fins de phrase
- **overlays animés dans la DA Healthy Fry** :
  - titre d'accroche visible dès la 1re image
  - ingrédients qui apparaissent **au moment où la voix les prononce**
  - pastilles d'étapes qui glissent, badges qui rebondissent
  - écran final « Enregistre la recette »
- **bruitages** générés et libres de droits : whoosh aux transitions, pop sur les textes, tic à chaque ingrédient, ding au résultat
- **barre de progression** verte en haut de l'écran (elle augmente la rétention)
- **son normalisé à -14 LUFS** (le standard TikTok), son des clips conservé sous la voix
- une **miniature** `.jpg` et la **légende** `.txt` avec les hashtags

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

## Astuces pour des vidéos qui performent

- **Accroche** : la 1re phrase doit être une phrase choc (« Arrête de rater tes cookies ») sur le plan le plus appétissant.
- **Boucle** : termine la vidéo sur le même visuel que le début, pour que le revisionnage s'enchaîne naturellement.
- `rush` accepte une **liste** de visuels : le temps du plan est réparti entre eux.
- À la publication, ajoute un **son tendance** dans TikTok à 5-10 % du volume, et coche **« contenu généré par IA »** si les visuels sont générés.

## Exemple fourni

`exemple/` contient une recette de démo (le cookie fondant, qui avait fait 211k vues en carrousel).
Les visuels sont des **photos tirées des anciens carrousels**, juste pour tester le pipeline.
La prochaine étape remplace ces photos par des **clips vidéo IA** générés automatiquement.

## Visuels 100 % IA avec kie.ai (sans rien filmer)

Chaque segment de la recette peut décrire ses plans IA au lieu d'un `rush` :

```jsonc
"style_visuel": "Warm soft natural window light, light oak kitchen counter, beige linen cloth, cream ceramic tableware…",
"segments": [
  { "type": "etape", "voix": "…", "ecran": { "num": 1, "texte": "Beurre mou + sucre" },
    "ia": [ { "id": "melange_beurre",
              "image": "Top view of a cream ceramic mixing bowl containing soft butter and brown sugar, a metal whisk",
              "video": "A hand whisks the soft butter and brown sugar together until creamy, top-down view",
              "modele": "wan" } ] }
]
```

Commandes, dans l'ordre :

```bash
export KIE_API_KEY=ta_cle
```

```bash
python3 montage/generer_visuels.py montage/exemple/cookie-fondant-ia.json --estimer
```

```bash
python3 montage/generer_visuels.py montage/exemple/cookie-fondant-ia.json
```

```bash
python3 montage/render.py montage/exemple/cookie-fondant-ia.json
```

- Chaque plan = 1 image **Nano Banana 2.1** (4 crédits), animée en clip de 5 s 720p par **Wan 2.6 Flash** (20 crédits) ou **Seedance 2.0 Mini** (41 crédits, plus réaliste, à réserver à l'accroche).
- Les clips sont mis en cache dans `ia/` : relancer ne repaie rien. Pour refaire un plan raté, supprime son `.mp4`.
- Le `style_visuel` commun à tous les plans garde le même décor d'un plan à l'autre.

**Coût réel de la vidéo d'exemple : 1 plan Seedance + 10 plans Wan ≈ 285 crédits ≈ 1,40 $.**
En réutilisant le même plan d'accroche à la fin (effet boucle) et en restant sur Wan : **environ 1,20 $ par vidéo**.
