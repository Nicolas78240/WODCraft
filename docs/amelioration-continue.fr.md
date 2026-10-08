# Améliorer WODCraft depuis une application : la boucle

Ce document met à plat la façon dont WODCraft s'améliore à partir de l'usage réel — aujourd'hui celui
d'oKo — et la façon dont l'application récupère ces améliorations. Il formalise ce qui a été décidé et
pratiqué entre le 24 septembre et le 8 octobre 2026 (sessions oKo : lot B / WODCraft 1.1, boucle de
validation des mouvements L-4, benchmarks Heroes et Girls, CrossFit Total).

## En une phrase

**Un manque constaté dans l'application se corrige à la source, dans WODCraft, après validation
humaine, avec ses preuves ; l'application le récupère en montant de version, jamais en bricolant de
son côté.**

```
   oKo (usage réel)                    WODCraft (le standard)                 oKo (récupération)
 ┌───────────────────┐   proposition   ┌──────────────────────────┐  release  ┌─────────────────────┐
 │ photo de tableau  │ ──────────────▶ │ tri : alias, mouvement,  │ ────────▶ │ une PR « WODCraft   │
 │ texte collé       │   validée par   │ benchmark ou langage     │  vX.Y.Z   │ X.Y.Z » met à jour  │
 │ import d'historique│  le PO         │ + preuves (tests, spec,  │  (tag,    │ tous les consomma-  │
 │ demande d'un coach│                 │   conformité, Swift)     │   PyPI)   │ teurs d'un coup     │
 └───────────────────┘                 └──────────────────────────┘           └─────────────────────┘
          ▲                                                                              │
          └──────────────── la séance suivante se lit mieux ◀────────────────────────────┘
```

## Les principes

1. **Corriger à la source.** Si WODCraft ne sait pas écrire ou reconnaître quelque chose qu'un coach
   écrit naturellement, c'est WODCraft qu'on corrige — pas un contournement durable dans l'app.
   *« Il faudrait que WODCraft gère ce genre de WOD »* (CrossFit Total, 8 octobre).
2. **D'abord vérifier ce que WODCraft sait déjà.** Avant toute extension, on compile le cas avec la
   version actuelle. Le 29 septembre, l'essentiel des besoins d'oKo était déjà couvert ; seuls les vrais
   manques sont devenus la 1.1.
3. **Ne jamais bloquer l'athlète.** Tant que le manque n'est pas corrigé, la séance s'enregistre quand
   même : le passage non compris va dans une `note:`, le mouvement inconnu reste saisissable.
4. **Ne rien inventer.** Un terme inconnu devient une *proposition*, jamais une devinette. Le coach IA
   et la lecture de photo n'ajoutent rien au catalogue d'eux-mêmes.
5. **Un seul validateur humain : le PO.** Toute entrée au catalogue, à la bibliothèque ou à la
   grammaire est validée par Nicolas (fonction derrière un *feature flag*, pour lui seul).
6. **Chaque changement arrive avec ses preuves.** Un changement de langage contient, dans le même
   commit : la spécification, les cas de conformité, l'implémentation Python et l'implémentation Swift.
   Les deux implémentations sont comparées entre elles (`make swift-diff`).
7. **Rien ne casse.** Un document existant compile exactement comme avant ; le champ `"wodcraft"` d'un
   document ne monte de version que s'il utilise une nouveauté.
8. **Rien n'est poussé ni publié sans accord explicite.** Les outils préparent (branche, commit,
   tests) ; la publication est une décision.
9. **Le catalogue est public.** Il fait partie du standard : pas de texte sous droits (on décrit un
   benchmark, on ne recopie pas une source), et les noms proposés par un LLM sont filtrés (caractères
   autorisés) avant d'entrer dans un prompt ou dans le catalogue.

## Trier : quatre sortes de changements

| Sorte | Exemple réel | Où | Ce qu'il faut | Version |
|---|---|---|---|---|
| **Alias** | une abréviation de tableau, un nom français | `catalog/movements.toml` | l'alias français reste obligatoire | correctif (1.1.**x**) |
| **Mouvement** | Harlow, Commando push-up, Box bar muscle-up (7 octobre) | `catalog/movements.toml` | identifiant `snake_case`, groupe, type de quantité, équipement, alias FR ; ni nom ni alias déjà pris | correctif |
| **Benchmark** | Christine et 41 Heroes (3 octobre) ; G.I. Jane et Hopper en attente | `library/` | une source citée, des charges vérifiées sur la prescription officielle, aucun texte recopié | correctif |
| **Langage** | ergomètre, alternatives, aller-retour (1.1) ; score total et essais (CrossFit Total, 1.2 proposée) | `spec/SPEC.md` d'abord | spec → conformité → Python → Swift → bibliothèque et docs | mineure (1.**y**) |

Pour un changement de langage, la discussion de syntaxe se fait sur des exemples compilés, variante par
variante, jusqu'à la validation du PO — c'est ce qui a été fait pour le CrossFit Total (quatre
variantes, la A retenue et améliorée, « l'un ou l'autre » pour les caps).

## Le parcours d'une amélioration

### 1. Repérer (dans l'app)

Les manques arrivent par quatre portes :

- la **lecture d'un tableau** (photo ou texte collé) qui bute sur un terme ;
- le bouton **« Signaler une erreur de lecture »** (réservé au PO pour l'instant) ;
- un **import d'historique** dont une description ne compile pas ;
- une **demande de coach** pour un format (le CrossFit Total).

Chaque manque devient une proposition (`movement_proposals` côté oKo : `proposed → approved/rejected
→ added`).

### 2. Valider (le PO)

Dans l'admin, le PO accepte ou refuse, et complète ce qui manque (groupe, quantité, équipement, alias
français). Valider **ne modifie pas** WODCraft : c'est une décision, pas une publication.

### 3. Appliquer (dans WODCraft)

- **Alias, mouvement** : le script d'oKo `scripts/wodcraft_movements.py apply` écrit les propositions
  validées dans `movements.toml` sur une branche `catalog/oko-<date>` partie d'`origin/main`,
  regénère les ressources Swift (`wodc bundle`), lance `pytest` et `swift test`, ne commite que si tout
  passe, puis pousse la branche et ouvre une PR que le PO fusionne.
- **Benchmark** : un `.wod` dans `library/`, avec sa source en commentaire de PR.
- **Langage** : une branche `feat/...` qui suit l'ordre spec → conformité → Python → Swift.

### 4. Publier (WODCraft)

Une PR vers `main`, la CI verte (Python 3.11–3.13, Swift, schéma, bibliothèque canonique), puis une
release GitHub `vX.Y.Z` : le workflow `publish.yml` publie sur PyPI. Le CHANGELOG dit ce qui change.

### 5. Récupérer (dans l'app)

Une seule PR côté oKo, « WODCraft X.Y.Z », met à jour **tous** les consommateurs à la même version :

| Consommateur | Ce qui change |
|---|---|
| App iOS (`WODCraftKit`, compilateur embarqué hors ligne) | la version du paquet Swift ; arrive aux athlètes au build TestFlight suivant |
| Lecture de tableaux (`wod-read`) | son contexte regénéré (catalogue, benchmarks), avec une nouvelle version de contexte |
| Admin | le catalogue regénéré |
| Coaching (table `exercises`) | regénérée depuis le même catalogue |
| Service Cloud Run `wodcraft` (web coach) | redéployé avec `ref = vX.Y.Z` |

Les séances déjà enregistrées gardent leur `wodcraft_version` et leur JSON : rien n'est recompilé de
force, et une version plus récente du compilateur les relit toujours.

## Ce que ça apporte à oKo

- **Chaque amélioration sert partout à la fois** : la lecture de photo, la saisie, le coach IA, le
  tableau affiché et le web coach parlent la même langue, parce qu'ils lisent le même catalogue.
- **La qualité ne dépend pas de l'app** : les tests de WODCraft (près de 2 000), sa suite de conformité
  et la comparaison Python/Swift garantissent qu'un ajout ne casse rien de ce qui marchait.
- **Le travail profite aux autres** : WODCraft est public. Ce qu'oKo fait progresser, une autre app peut
  le réutiliser — et inversement.

## Où on en est (8 octobre 2026)

Ce qui marche déjà :

- La 1.1 (lot B) est née exactement de cette boucle, et elle est sur PyPI.
- La boucle de validation des mouvements a tourné une première fois le 7 octobre : 5 mouvements
  (catalogue 223 → 228).

Ce qui a été remis dans le parcours le 8 octobre :

1. **Les 5 mouvements du 7 octobre sont publiés** dans la 1.1.1 (GitHub et PyPI) ; ils ne vivaient
   jusque-là que sur une branche locale.
2. **WODCraftKit s'épingle par tag** grâce au `Package.swift` racine ; l'app quitte les chemins locaux
   (`~/Dev/WODCraft`, worktree `oko-seances`), qui faisaient voir 212, 223 ou 228 mouvements selon le
   consommateur.
3. **Le script d'application part d'`origin/main` et ouvre une PR** au lieu de commiter sur une branche
   locale.

Reste à faire : mettre à jour `integration-oko.fr.md` (212 mouvements, 40 benchmarks, 64 cas de
conformité).

## Les décisions prises le 8 octobre

| Question | Décision |
|---|---|
| Comment l'app iOS épingle WODCraftKit | un `Package.swift` à la racine du dépôt WODCraft, pour que l'app dépende de `github.com/Nicolas78240/WODCraft` à un tag précis (ce qui ouvre aussi la Swift Package Index) |
| D'où part le script d'application | de `origin/main`, et il ouvre une PR au lieu de commiter sur une branche locale (le PO fusionne) |
| Où tourne l'application des propositions | en local pour l'instant ; plus tard une GitHub Action qui ouvre la PR (trois secrets à prévoir) |
| Rythme des versions | un correctif (1.1.x) dès qu'un lot de mouvements, d'alias ou de benchmarks est validé ; une mineure (1.2) par évolution de langage |
| Suivi des demandes | une issue GitHub par manque (les modèles `movement`, `benchmark`, `language` existent déjà) |

## La file d'attente connue

| Manque | Sorte | État |
|---|---|---|
| Harlow, Commando push-up, Box bar muscle-up, Kettlebell side bend, Press back | mouvements | publiés en 1.1.1 ; Harlow et Press back restent à décrire |
| CrossFit Total : score total, essais, cap global ou par barre, bibliothèque `benchmarks/` | langage + benchmark | publié en 1.2.0 (`use benchmarks/crossfit_total`) |
| Quantités différentes à chaque passage (8/12/16/20) | langage | constaté le 6 octobre, contourné par une `note:` |
| Double-unders en durée (`E033` : « measured in reps ») ; `Clean & jerk` (`E001` sur le `&`) | langage, alias | notés le 29 septembre, confirmés le 8 octobre |
| G.I. Jane, Hopper | benchmarks | demandés (Jason et The Seven sont déjà dans la bibliothèque) |
| Snatch pull, pike HSPU, pike-up | mouvements | absents du catalogue (vérifié le 8 octobre) |
| Défauts de cap trouvés en testant le Total (caps par bloc non additionnés, cap global accroché au premier bloc, combinaison silencieuse) | compilateur | corrigés en 1.2.0 (E037 pour la combinaison) |
