# Motion design Healthy Fry (100 % automatique, sans tournage)

Vidéo animée entièrement par le code, avec des **objets photoréalistes détourés** :
- le cookie fondant arrive avec des éclats de miettes et les mots du titre claquent un par un ;
- chaque ingrédient tombe **au moment où la voix le prononce**, avec sa quantité ;
- tout fusionne en cookie, qui part dans l'airfryer : compteur de température, minuteur qui défile, anneau de progression, halo de chaleur, vapeur ;
- le cookie revient en plan héros avec des flèches « croustillant / fondant » ;
- carte finale « Enregistre la recette ».

S'y ajoutent la voix off FR gratuite, les sous-titres animés, les bruitages, du grain photo et un son normalisé à -14 LUFS.

```bash
python3 motion/motion.py
```

Le résultat arrive dans `motion/sorties/cookie-motion.mp4` (environ 4 min de rendu).

| Fichier | Rôle |
|---|---|
| `scene.html` | La scène et toute l'animation, calculée image par image (fonction `render(t)`) |
| `frames.js` | Capture 30 images par seconde avec Chromium et encode la vidéo |
| `motion.py` | Voix off, calage du timing, bruitages, sous-titres, export |
| `cut/` | Objets détourés (générés avec Nano Banana 2.1 sur kie.ai à 4 crédits l'image, puis détourés avec `rembg`) |

**Coût d'une nouvelle recette : environ 8 à 10 images à 4 crédits, soit environ 0,20 $.**
