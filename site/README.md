# WODCraft — site vitrine

https://wodcraft.dev (anglais) · https://wodcraft.dev/fr/ (français)

Page statique (HTML, CSS, JS, sans framework). Toutes les sorties affichées viennent du vrai compilateur.

## Construire

```bash
python3 build_data.py "$(which wodc)"   # data.js depuis wods/*.wod (sorties réelles de wodc)
pip wheel --no-deps .. -w py/            # la roue chargée par le bac à sable (Pyodide)
python3 build_site.py                    # public/ : /, /fr/, sitemap.xml, robots.txt, 404 (beautifulsoup4 requis)
```

- `index.html` est le modèle, en français ; `en.json` le traduit en anglais (clé = sélecteur CSS,
  `sélecteur@attribut` pour un attribut). Les textes générés par le script sont dans `main.js` (`t(fr, en)`).
- Chaque langue a son URL, son titre, sa description, `canonical`, `hreflang` (`x-default` = anglais),
  Open Graph, Twitter et JSON-LD. Les panneaux de code sont pré-remplis : la page se lit sans JavaScript.
- Langue : un navigateur en `fr*` qui arrive sur `/` est envoyé vers `/fr/` ; le sélecteur FR · EN de
  l'en-tête mémorise le choix (`localStorage`, clé `wodcraft-lang`). Les robots restent sur `/`.
- Images de partage `og-en.png` et `og-fr.png` (1200 × 630) : capture de `og/og.html#en` et `#fr`.

## Déployer

Firebase Hosting, site `wodcraft` du projet GCP `oko-coaching-dev` :

```bash
firebase deploy --only hosting
```

Domaine `wodcraft.dev` acheté via Cloud Domains (même projet), DNS dans la zone Cloud DNS `wodcraft-dev`
(A + TXT pour Firebase, `www` en CNAME, redirigé vers l'apex). Certificat géré par Firebase.
