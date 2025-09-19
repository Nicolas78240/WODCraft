# WODCraft — Guide des Bonnes Pratiques

Ce guide couvre les erreurs courantes, conventions recommandées, et patterns efficaces pour WODCraft.

## 🚨 Erreurs Courantes & Solutions

### 1. **Syntaxe des scores**

❌ **Erreur courante** :
```wod
score AMRAP { rounds: Rounds, reps: Reps }  // Virgule non supportée (anciennes versions)
```

✅ **Solution (v0.3.2+)** :
```wod
score AMRAP { rounds: Rounds, reps: Reps }  // ✓ Virgules maintenant acceptées
score AMRAP {
  rounds: Rounds
  reps: Reps
}  // ✓ Multi-lignes toujours supporté
```

### 2. **Alias de session incorrects**

❌ **Erreur courante** :
```wod
session "Training" {
  components {
    metcon import wod.fran@v1  // "metcon" n'existe pas
  }
}
```

✅ **Solution** :
```wod
session "Training" {
  components {
    strength import wod.squats.heavy@v1  // Force/puissance
    wod import wod.fran@v1               // Conditioning (metcon)
  }
}
```

**Alias supportés** : `warmup`, `skill`, `strength`, `wod`

### 3. **Unités non reconnues**

❌ **Erreur courante** :
```wod
10 Box_Jump @24inches  // "inches" non supporté
```

✅ **Solution** :
```wod
10 Box_Jump @24in/20in  // ✓ Unités supportées : in, cm, ft
```

### 4. **Position de REST incorrecte**

❌ **Erreur courante** :
```wod
wod AMRAP 15:00 {
  10 Burpee
}
REST 2:00  // ❌ REST en dehors du WOD
wod EMOM 10:00 { ... }
```

✅ **Solution** :
```wod
wod AMRAP 15:00 {
  10 Burpee
  REST 2:00  // ✓ REST à l'intérieur du WOD
  15 Thruster
}
```

## 💡 Conventions Recommandées

### 1. **Nommage des modules**

✅ **Bonne pratique** :
```wod
module wod.strength.deadlift v1    // Catégorie.type.nom
module wod.metcon.cindy v1         // Métabolique
module wod.benchmark.fran v1       // Benchmark reconnu
```

### 2. **Organisation des sessions**

✅ **Pattern recommandé** :
```wod
session "Competition Prep" {
  components {
    warmup import wod.warmup.dynamic@v1     // Échauffement
    skill import wod.skill.handstand@v1     // Technique
    strength import wod.strength.squat@v1   // Force principale
    wod import wod.metcon.helen@v1          // Conditioning
  }
  scoring {
    strength EMOM load
    wod ForTime time
  }
}
```

### 3. **Charges avec conversions**

✅ **Exploiter les conversions automatiques** :
```wod
// En livres - convertit automatiquement
21 Thruster @95lb/65lb    // → "95lb (~43.1kg)/65lb (~29.5kg)"

// En kg - pas de conversion nécessaire
21 Thruster @43kg/30kg    // → "43kg/30kg"
```

### 4. **Progressions claires**

✅ **Patterns utiles** :
```wod
// Progression de charge
5 Back_Squat PROGRESS("+5kg/semaine") @80%1RM

// Progression de volume
400m Run PROGRESS("+100m/round")

// Progression temporelle
EMOM 12:00 PROGRESS("+2min/semaine") { ... }
```

## 🏋️ Patterns d'Entraînement

### 1. **Session Strength + Metcon**

```wod
module strength.squat.cycle v1 {
  wod EMOM 12:00 {
    3 Back_Squat @85%1RM
  }
  score EMOM { rounds: Rounds }
}

module metcon.conditioning v1 {
  wod AMRAP 15:00 {
    10 Thruster @95lb/65lb
    15 Pull_up
    20 Burpee
  }
  score AMRAP { rounds: Rounds, reps: Reps }
}

session "Daily Training" {
  components {
    strength import strength.squat.cycle@v1
    wod import metcon.conditioning@v1
  }
  scoring {
    strength EMOM rounds
    wod AMRAP rounds+reps
  }
}
```

### 2. **WOD avec scaling intégré**

```wod
module wod.benchmark.fran v1 {
  notes: {
    rx: "21-15-9 Thruster @95lb/65lb, Pull-up",
    scaled: "Réduire charge Thruster, Ring Row au lieu de Pull-up"
  }

  wod ForTime cap 5:00 {
    21 Thruster @95lb/65lb
    21 Pull_up
    15 Thruster @95lb/65lb
    15 Pull_up
    9 Thruster @95lb/65lb
    9 Pull_up
  }

  score ForTime { time: Time, reps: Reps }
}
```

### 3. **EMOM avec variations**

```wod
module skill.complex.pulling v1 {
  wod EMOM 16:00 {
    // Min 1-4: Strict
    4 Strict_Pull_up
    REST 1:00

    // Min 5-8: Kipping
    8 Kipping_Pull_up
    REST 1:00

    // Min 9-12: Chest-to-bar
    6 Chest_To_Bar_Pull_up
    REST 1:00

    // Min 13-16: Muscle-ups
    2 Muscle_up
    REST 1:00
  }

  score EMOM { rounds: Rounds }
}
```

## 🎯 Validation & Tests

### 1. **Vérification avant publication**

```bash
# Lint complet
wodc lint myworkout.wod

# Parse pour vérifier la structure
wodc parse myworkout.wod

# Compilation de session
wodc session mysession.wod --format json
```

### 2. **Patterns de test**

```wod
// Test des types de score
score AMRAP {
  rounds: Rounds,           // ✓ Entier
  reps: Reps,               // ✓ Entier
  distance: Distance(m),    // ✓ Avec unité
  load: Load(kg)            // ✓ Avec unité
}

// Test des unités
10 Box_Jump @24in/20in      // ✓ Hauteurs
15 Deadlift @225lb/155lb    // ✓ Poids avec conversion
400m Run                    // ✓ Distance
```

## 🔧 Dépannage

### Erreurs fréquentes et solutions :

1. **"Syntax error at '25'"**
   → Ajouter le type de WOD : `AMRAP 25:00` au lieu de `25:00`

2. **"Unexpected token metcon"**
   → Utiliser `wod` au lieu de `metcon` dans les sessions

3. **"Expected RBRACE"**
   → Vérifier les accolades ouvrantes/fermantes `{}`

4. **Conversions lb→kg invisibles**
   → Utiliser WODCraft v0.3.2+ pour les conversions automatiques

5. **Mouvement non reconnu**
   → Utiliser snake_case : `Pull_up` au lieu de `Pull-up`

---

💡 **Astuce** : Commencez toujours par les exemples dans `wodcraft://examples/basic` et adaptez selon vos besoins !