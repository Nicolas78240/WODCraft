# Intégrer WODCraft dans oKo

Note de conception pour le PO. Rien n'est appliqué au dépôt oKo : ce document propose, il ne décide pas.

Contexte oKo (fourni par l'équipe) : app iOS SwiftUI, iOS 17, Swift 6 en concurrence stricte, **hors
ligne obligatoire**, SwiftData en local et Supabase comme source de vérité, packages SwiftPM locaux
`OkoCore` et `OkoData`, tests en Swift Testing, UI en français, identifiants en anglais.

## 1. Le principe : deux objets, jamais un seul

WODCraft décrit **la prescription**. oKo enregistre **le réalisé**. Les deux ne se mélangent pas :

```
prescription  = texte WODCraft (.wod)  →  document compilé (JSON, schéma versionné)
réalisé       = la ligne `wods` d'oKo  →  score, Rx, RPE, notes, rattachement à la séance HealthKit
```

Le réalisé référence la prescription ; il ne la recopie pas. C'est ce qui permet de comparer « ma Fran
de mars » et « ma Fran de septembre » : les deux pointent le même texte.

## 2. Ce que le document compilé donne à l'app, sans code métier

| Champ | Ce qu'oKo en fait |
|---|---|
| `score.type` | **pilote le formulaire de saisie** : `time` → un chrono ; `rounds+reps` → tours + reliquat ; `reps`, `rounds` → un entier ; `load` → une charge ; `multi` → un score par partie |
| `score.capped` | si l'athlète a pris le cap, bascule la saisie sur des reps |
| `blocks` | l'affichage tableau blanc, déjà rendu par `workout.whiteboard()` |
| `levels` | le sélecteur Rx / Scaled / Foundations, au lieu du booléen `rx` seul |
| `estimate` | « ~12 min » avant de lancer, et un contrôle de vraisemblance du temps saisi |
| `timeline()` | la liste d'intervalles qui pilotera un timer (EMOM, Every, Tabata) le jour où vous en voudrez un |
| `meta.vest`, `team` | le gilet lesté, la taille d'équipe |
| catalogue | les suggestions de mouvements, en français, et la normalisation des records |

Cas particulier utile pour votre `part = strength` : une partie de force s'écrit en une ligne —
`Back squat 5x5 @ 75% (rest 2:30)` — et le compilateur en déduit `score.type = "load"`, les cinq
séries, le repos entre séries, et la charge réelle une fois le 1RM de l'athlète connu.

## 3. Le raccordement au schéma existant

`wods` porte aujourd'hui : `format` (enum `amrap | emom | for_time | strength`), `movements` (jsonb
libre), `score` (jsonb `{value, unit}`), `part`, `time_cap_s`, `rx`, `rpe`, `notes`, `workout_id`.

La proposition ne touche à aucune colonne existante — les WODs déjà saisis restent lisibles tels quels :

```sql
-- supabase/migrations/<horodatage>_wods_wodcraft.sql
alter table public.wods
  add column source_dsl text,                 -- le texte WODCraft d'origine, la vérité
  add column compiled jsonb,                  -- le document compilé, cache dérivé
  add column wodcraft_version text;           -- "1.0" : la version de spec qui a produit `compiled`

comment on column public.wods.source_dsl is
  'Texte WODCraft. Quand il est présent, format/movements/score/time_cap_s en sont dérivés.';

-- cohérence : soit les trois colonnes ensemble, soit aucune
alter table public.wods
  add constraint wods_wodcraft_complete
  check (num_nonnulls(source_dsl, compiled, wodcraft_version) in (0, 3));
```

Points d'attention :

- **`compiled` est un cache, pas la vérité.** Il se régénère depuis `source_dsl`. Stocker
  `wodcraft_version` permet de recompiler en masse le jour où la spec passe en 1.1, sans deviner.
- **Pas de contrainte sur `movements`.** Les colonnes historiques restent alimentées par dérivation
  (§4), donc les écrans existants continuent de fonctionner sans être réécrits.
- **RLS** : rien de neuf, les colonnes suivent la ligne et sa politique `user_id = auth.uid()`.
- **Test pgTAP** à ajouter dans la même migration : les trois colonnes existent et sont `nullable` ;
  la contrainte rejette un `source_dsl` seul ; une ligne historique sans DSL reste acceptée.

## 4. La projection vers les colonnes existantes

Une fonction pure dans le package Swift (testable, sans réseau) dérive les colonnes historiques :

| Colonne oKo | Dérivée de |
|---|---|
| `format` | type du bloc principal, projeté sur l'enum : `for_time`/`rounds`/`ladder` → `for_time` ; `amrap` → `amrap` ; `emom`/`every`/`tabata`/`death_by` → `emom` ; `max_load` et séries de force → `strength` |
| `time_cap_s` | `blocks[0].cap_s` |
| `movements` | la liste aplatie des mouvements, enrichie de l'identifiant du catalogue : `{movement_id, name, reps, load_kg, height_cm, modifiers}` |
| `score` | `{value, unit}` saisi par l'athlète, l'unité venant de `score.type` (`time` → `s`, `load` → `kg`, `rounds+reps` → `rounds`) |
| `rx` | `true` quand la résolution a utilisé le niveau Rx |
| `name` | le titre du document |

### La projection de `format`, puis l'extension de l'enum

La projection perd de l'information : un Tabata et un « Death by » deviennent tous deux `emom`. C'est
acceptable pour ne pas toucher au schéma pendant que d'autres chantiers y écrivent, mais ça se voit à
l'écran — le format apparaît dans la liste des séances et dans les filtres, et `compiled` ne remonte
pas dans une liste. L'extension de l'enum est donc la cible :

```sql
-- migration 1 : ajouter les valeurs, et rien d'autre
alter type public.wod_format add value if not exists 'every';
alter type public.wod_format add value if not exists 'tabata';
alter type public.wod_format add value if not exists 'death_by';
alter type public.wod_format add value if not exists 'max_load';
alter type public.wod_format add value if not exists 'rounds';
alter type public.wod_format add value if not exists 'ladder';
```

```sql
-- migration 2, séparée : s'en servir et reprendre les lignes déjà projetées
update public.wods
   set format = (compiled -> 'blocks' -> 0 ->> 'type')::public.wod_format
 where compiled is not null
   and (compiled -> 'blocks' -> 0 ->> 'type') in ('every','tabata','death_by','max_load','rounds','ladder');
```

**Deux migrations, ce n'est pas du zèle** : Postgres applique une migration dans une transaction, et
une valeur ajoutée à un type énuméré ne peut pas être utilisée dans la transaction qui l'ajoute. Tout
faire d'un coup fait échouer `supabase db push` au milieu, sur une base distante.

## 5. Le catalogue comble le trou des mouvements

Aujourd'hui `wods.movements` est du texte libre et `personal_records.movement` aussi : « tractions »,
« Tractions », « pull ups » et « pull-up » sont quatre mouvements différents pour la base.

Le catalogue embarqué (212 mouvements) résout les quatre vers `pull_up`, avec les alias français de
série : `tractions`, `pompes`, `fentes`, `soulevé de terre`, `squat à vide`, `rameur`, `corde à
sauter`… Deux usages immédiats, par ordre de valeur :

1. **La saisie** : `WodEntryView` propose des mouvements normalisés au lieu d'une suggestion textuelle,
   avec la charge Rx de référence et la famille (haltéro, gym, mono).
2. **Les records** : une colonne `movement_id text` **nullable, à côté de `movement`**, jamais à la
   place. Le texte reste la vérité pour les anciens records et pour un mouvement absent du catalogue.

```sql
alter table public.personal_records add column movement_id text;
comment on column public.personal_records.movement_id is
  'Identifiant du catalogue WODCraft quand la résolution est certaine ; NULL sinon, le texte fait foi.';
```

   La reprise des données existantes suit la même règle : un script résout chaque `movement` par le
   catalogue et **laisse `movement_id` à NULL dès que la résolution est ambiguë**, sans jamais deviner.
   Côté app, l'historique et les records se groupent par `movement_id` quand il existe, par texte
   normalisé sinon — donc rien ne casse pendant la transition.

## 6. Le package Swift

`WODCraftKit` est prêt à être déposé en package local, comme `OkoCore` et `OkoData` :

```yaml
# app/project.yml
packages:
  WODCraftKit:
    path: ../packages/WODCraftKit
```

- Zéro dépendance tierce, Foundation seulement, iOS 17 / macOS 13, Swift 6 strict concurrency.
- Ressources JSON embarquées : **115 Ko** (catalogue 57 Ko, bibliothèque 40 WODs 54 Ko, schéma 7 Ko),
  à comparer au mégaoctet de `ciqual.sqlite` déjà embarqué.
- Tests en Swift Testing, exécutables par `swift test` sur macOS, sans simulateur.
- La garantie de justesse ne repose pas sur une relecture : le package passe les **64 cas de
  conformité** du standard et recompile les 40 WODs de la bibliothèque à l'identique de
  l'implémentation Python de référence.

```swift
let result = WODCraft.compile(text)
guard result.ok, case let .workout(wod)? = result.document else {
    return result.diagnostics.map { ($0.line, $0.col, $0.message, $0.suggestion) }  // à afficher sous l'éditeur
}
let mine = wod.resolved(for: profile)          // catégorie, niveau, unités, 1RM
board.text = mine.whiteboard(language: "fr")   // l'affichage
scoreKind = wod.score.type                     // le formulaire de saisie
```

## 7. Le parcours utilisateur visé

1. L'athlète colle ou saisit le WOD tel qu'il est écrit au tableau de la box.
2. Le compilateur répond **à la frappe, hors ligne** : ligne, colonne, message, suggestion
   (« Trusters » → « vouliez-vous dire Thruster ? », un box jump qui reçoit une charge, un EMOM
   intenable). Rien n'est enregistré tant que le texte ne compile pas.
3. L'app affiche le tableau blanc résolu à son profil : ses charges, dans son unité.
4. Après la séance, le formulaire de score est celui qu'impose `score.type`.
5. Le WOD est rattaché à la séance Apple Santé du jour, comme aujourd'hui.
6. Les records battus sont proposés, désormais rattachés à un mouvement du catalogue.

Bonus sans effort supplémentaire : l'athlète peut partir d'un des 40 benchmarks embarqués
(`use girls/fran`), et partager un WOD en envoyant six lignes de texte.

## 8. Ordre de mise en œuvre proposé

| Étape | Contenu | Dépendance |
|---|---|---|
| 1 | Déposer `WODCraftKit` dans `packages/`, le référencer dans `project.yml`, faire passer `swift test` en CI | dépôt oKo calme |
| 2 | Écran d'aperçu : coller un WOD, voir les diagnostics et le tableau blanc (lecture seule, rien en base) | 1 |
| 3 | Migration `source_dsl` / `compiled` / `wodcraft_version` + test pgTAP + dérivation des colonnes existantes | décision PO |
| 4 | Saisie assistée par le catalogue dans `WodEntryView`, formulaire de score piloté par `score.type` | 2, 3 |
| 5 | `movement_id` nullable sur `personal_records` + script de reprise prudent, regroupement des records | 4 |
| 6 | Extension de l'enum `wod_format` en **deux** migrations, puis reprise des lignes projetées | 3 |
| 7 | Timer à partir de `timeline()`, et Live Activity si le besoin se confirme | 4 |

Les étapes 1 et 2 ne touchent ni la base ni les écrans existants : elles sont réversibles en
supprimant le package.
