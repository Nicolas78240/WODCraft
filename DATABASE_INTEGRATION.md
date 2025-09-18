# DATABASE_INTEGRATION.md

Guide des bonnes pratiques pour intégrer WODCraft avec des bases de données et applications.

## 🎯 Objectif

Ce document explique comment structurer et requêter efficacement les données WODCraft dans des applications de type box CrossFit, plateformes d'entraînement, ou outils d'analytics.

## 📊 Architecture de données recommandée

### Schéma principal

```sql
-- Table principale des définitions de WODs
CREATE TABLE wod_definitions (
    id UUID PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    dsl_source TEXT NOT NULL,              -- Code source WODCraft complet
    ast_json JSONB NOT NULL,               -- AST parsé pour requêtes rapides
    compiled_json JSONB,                   -- Version compilée avec résolutions
    source_hash VARCHAR(64) UNIQUE,        -- SHA-256 du DSL pour déduplication
    movements_list TEXT[],                 -- Index des mouvements (array pour performance)
    equipment_list TEXT[],                 -- Équipements requis
    duration_seconds INT,                  -- Durée estimée
    difficulty_score INT CHECK (difficulty_score BETWEEN 0 AND 100),
    modality_tags TEXT[],                  -- ["strength", "cardio", "gymnastics"]
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    version INT DEFAULT 1
);

-- Index pour requêtes fréquentes
CREATE INDEX idx_wod_movements ON wod_definitions USING GIN (movements_list);
CREATE INDEX idx_wod_modality ON wod_definitions USING GIN (modality_tags);
CREATE INDEX idx_wod_duration ON wod_definitions (duration_seconds);
CREATE INDEX idx_wod_difficulty ON wod_definitions (difficulty_score);
CREATE INDEX idx_wod_source_hash ON wod_definitions (source_hash);

-- Sessions programmées (instances de WODs)
CREATE TABLE scheduled_sessions (
    id UUID PRIMARY KEY,
    wod_definition_id UUID REFERENCES wod_definitions(id),
    session_date DATE NOT NULL,
    session_time TIME,
    track VARCHAR(20) DEFAULT 'RX',        -- RX, SCALED, INTERMEDIATE
    gender_mode VARCHAR(10) DEFAULT 'MIXED', -- M, F, MIXED
    team_size INT DEFAULT 1,
    location VARCHAR(255),
    coach_notes TEXT,
    max_participants INT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Résultats individuels
CREATE TABLE athlete_results (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES scheduled_sessions(id),
    athlete_id UUID NOT NULL,              -- Référence externe vers système athletes
    score_type VARCHAR(20) NOT NULL,       -- TIME, REPS, ROUNDS, LOAD, CALORIES
    score_value DECIMAL(10,3),             -- Valeur principale (secondes, reps, kg, etc.)
    score_secondary DECIMAL(10,3),         -- Valeur secondaire (reps pour AMRAP, etc.)
    score_unit VARCHAR(10),                -- kg, lb, cal, m, etc.
    is_rx BOOLEAN DEFAULT true,
    is_dnf BOOLEAN DEFAULT false,          -- Did Not Finish
    notes TEXT,
    realized_events JSONB,                 -- Timeline détaillée des événements
    recorded_at TIMESTAMP DEFAULT NOW()
);

-- Événements temps réel (pour apps live tracking)
CREATE TABLE realized_events (
    id UUID PRIMARY KEY,
    session_id UUID REFERENCES scheduled_sessions(id),
    athlete_id UUID NOT NULL,
    timestamp_offset INT NOT NULL,         -- Secondes depuis début de session
    movement VARCHAR(100),
    quantity_completed DECIMAL(10,2),
    quantity_unit VARCHAR(20),            -- reps, kg, m, cal, etc.
    event_type VARCHAR(20) DEFAULT 'COMPLETE', -- COMPLETE, START, REST, etc.
    metadata JSONB,                       -- Données supplémentaires
    recorded_at TIMESTAMP DEFAULT NOW()
);

-- Index pour performance temps réel
CREATE INDEX idx_events_session_time ON realized_events (session_id, timestamp_offset);
CREATE INDEX idx_events_athlete ON realized_events (athlete_id, timestamp_offset);
```

### Tables de métadonnées

```sql
-- Catalogue des mouvements enrichi
CREATE TABLE movement_catalog (
    id UUID PRIMARY KEY,
    canonical_name VARCHAR(100) UNIQUE NOT NULL,
    aliases TEXT[],                        -- ["Push_up", "push-up", "pushup"]
    category VARCHAR(50),                  -- weightlifting, gymnastics, cardio, etc.
    muscle_groups TEXT[],                  -- ["chest", "triceps", "shoulders"]
    equipment_required TEXT[],             -- ["barbell", "plates"]
    modality VARCHAR(20),                  -- strength, cardio, gymnastics
    complexity_level INT CHECK (complexity_level BETWEEN 1 AND 5),
    default_loads JSONB,                   -- Standards RX/Scaled par genre
    scaling_options JSONB,                 -- Options d'adaptation
    created_at TIMESTAMP DEFAULT NOW()
);

-- Index pour recherche de mouvements
CREATE INDEX idx_movement_aliases ON movement_catalog USING GIN (aliases);
CREATE INDEX idx_movement_equipment ON movement_catalog USING GIN (equipment_required);
CREATE INDEX idx_movement_muscles ON movement_catalog USING GIN (muscle_groups);
```

## 🔍 Patterns de requêtes courantes

### 1. Recherche de WODs par mouvements

```sql
-- Trouver tous les WODs contenant push-ups ET thrusters
SELECT w.id, w.title, w.movements_list, w.difficulty_score
FROM wod_definitions w
WHERE w.movements_list @> ARRAY['push_up', 'thrusters'];

-- WODs avec au moins un mouvement de la liste
SELECT w.id, w.title, w.movements_list
FROM wod_definitions w
WHERE w.movements_list && ARRAY['deadlift', 'squat', 'bench_press'];

-- WODs par catégorie de mouvement via jointure
SELECT DISTINCT w.id, w.title
FROM wod_definitions w
JOIN movement_catalog mc ON mc.canonical_name = ANY(w.movements_list)
WHERE mc.category = 'weightlifting';
```

### 2. Filtrage par durée et difficulté

```sql
-- WODs courts (5-15 minutes) de difficulté modérée
SELECT w.id, w.title, w.duration_seconds, w.difficulty_score
FROM wod_definitions w
WHERE w.duration_seconds BETWEEN 300 AND 900
AND w.difficulty_score BETWEEN 40 AND 70
ORDER BY w.difficulty_score;

-- WODs AMRAP avec durée spécifique
SELECT w.id, w.title, w.ast_json->>'form' as wod_type
FROM wod_definitions w
WHERE w.ast_json->>'form' = 'AMRAP'
AND w.duration_seconds = 720;  -- 12 minutes
```

### 3. Analytics et leaderboards

```sql
-- Top 10 des meilleurs temps sur "Fran"
SELECT ar.athlete_id, ar.score_value as time_seconds,
       ar.is_rx, ar.recorded_at
FROM athlete_results ar
JOIN scheduled_sessions ss ON ar.session_id = ss.id
JOIN wod_definitions wd ON ss.wod_definition_id = wd.id
WHERE wd.title = 'Fran'
AND ar.score_type = 'TIME'
AND ar.is_rx = true
ORDER BY ar.score_value ASC
LIMIT 10;

-- Progression d'un athlète sur un mouvement
SELECT DATE(ss.session_date) as workout_date,
       wd.title,
       ar.score_value,
       ar.score_type
FROM athlete_results ar
JOIN scheduled_sessions ss ON ar.session_id = ss.id
JOIN wod_definitions wd ON ss.wod_definition_id = wd.id
WHERE ar.athlete_id = 'athlete-uuid-here'
AND wd.movements_list @> ARRAY['deadlift']
ORDER BY ss.session_date DESC;
```

### 4. Requêtes temps réel

```sql
-- Progression live d'une session AMRAP
SELECT re.athlete_id,
       SUM(re.quantity_completed) as total_reps,
       MAX(re.timestamp_offset) as last_activity_time
FROM realized_events re
WHERE re.session_id = 'session-uuid'
AND re.event_type = 'COMPLETE'
GROUP BY re.athlete_id
ORDER BY total_reps DESC;

-- Timeline complète d'un athlète
SELECT re.timestamp_offset,
       re.movement,
       re.quantity_completed,
       re.quantity_unit
FROM realized_events re
WHERE re.session_id = 'session-uuid'
AND re.athlete_id = 'athlete-uuid'
ORDER BY re.timestamp_offset;
```

## ⚙️ Bonnes pratiques d'intégration

### 1. Hashing et déduplication

```python
import hashlib
import json

def generate_wod_hash(dsl_source: str) -> str:
    """Génère un hash unique pour déduplication"""
    # Normaliser le DSL (espaces, casse, etc.)
    normalized = dsl_source.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()

def store_wod_if_new(dsl_source: str, ast_json: dict) -> str:
    """Stocke un WOD seulement s'il n'existe pas déjà"""
    source_hash = generate_wod_hash(dsl_source)

    # Vérifier existence
    existing = db.execute(
        "SELECT id FROM wod_definitions WHERE source_hash = %s",
        [source_hash]
    ).fetchone()

    if existing:
        return existing['id']

    # Extraire métadonnées pour indexation
    movements = extract_movements_from_ast(ast_json)
    duration = estimate_duration_from_ast(ast_json)
    difficulty = calculate_difficulty_score(ast_json)

    wod_id = str(uuid.uuid4())
    db.execute("""
        INSERT INTO wod_definitions
        (id, title, dsl_source, ast_json, source_hash, movements_list,
         duration_seconds, difficulty_score)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, [wod_id, ast_json.get('title', 'Untitled'), dsl_source,
          json.dumps(ast_json), source_hash, movements, duration, difficulty])

    return wod_id
```

### 2. Cache intelligent avec invalidation

```python
class WODCraftCache:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.cache_ttl = 3600  # 1 heure

    def get_compiled_session(self, dsl_source: str) -> dict:
        """Cache de compilation avec invalidation par hash"""
        source_hash = generate_wod_hash(dsl_source)
        cache_key = f"compiled:{source_hash}"

        # Vérifier cache
        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        # Compiler et cacher
        from wodcraft import sdk
        compiled = sdk.compile_session(dsl_source)
        self.redis.setex(cache_key, self.cache_ttl, json.dumps(compiled))

        return compiled

    def invalidate_pattern(self, pattern: str):
        """Invalider un pattern de clés (ex: "compiled:*")"""
        for key in self.redis.scan_iter(match=pattern):
            self.redis.delete(key)
```

### 3. API GraphQL pour requêtes flexibles

```graphql
type WODDefinition {
  id: ID!
  title: String!
  dslSource: String!
  movements: [String!]!
  equipment: [String!]!
  duration: Int
  difficulty: Int
  modalities: [String!]!
  createdAt: DateTime!
}

type Query {
  # Recherche flexible par critères multiples
  searchWODs(
    movements: [String!]
    equipment: [String!]
    durationMin: Int
    durationMax: Int
    difficultyMin: Int
    difficultyMax: Int
    modalities: [String!]
    limit: Int = 20
    offset: Int = 0
  ): [WODDefinition!]!

  # Leaderboard pour un WOD spécifique
  leaderboard(
    wodId: ID!
    track: String = "RX"
    limit: Int = 10
  ): [AthleteResult!]!
}

# Exemple de requête
{
  searchWODs(
    movements: ["thrusters", "pull_up"]
    durationMin: 300
    durationMax: 1200
    difficultyMax: 80
  ) {
    id
    title
    movements
    duration
    difficulty
  }
}
```

### 4. Event sourcing pour tracking

```python
class RealtimeTracker:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.start_time = datetime.now()

    def record_movement_completion(self, athlete_id: str, movement: str,
                                 quantity: float, unit: str = "reps"):
        """Enregistre la completion d'un mouvement"""
        offset_seconds = int((datetime.now() - self.start_time).total_seconds())

        event = {
            'session_id': self.session_id,
            'athlete_id': athlete_id,
            'timestamp_offset': offset_seconds,
            'movement': movement,
            'quantity_completed': quantity,
            'quantity_unit': unit,
            'event_type': 'COMPLETE'
        }

        # Stocker en DB
        db.execute("""
            INSERT INTO realized_events
            (id, session_id, athlete_id, timestamp_offset, movement,
             quantity_completed, quantity_unit, event_type)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, [str(uuid.uuid4()), **event])

        # Publier pour temps réel
        self.publish_live_update(event)

    def get_live_leaderboard(self) -> list:
        """Leaderboard temps réel basé sur les événements"""
        return db.execute("""
            SELECT athlete_id,
                   SUM(quantity_completed) as total_reps,
                   MAX(timestamp_offset) as last_update
            FROM realized_events
            WHERE session_id = %s AND event_type = 'COMPLETE'
            GROUP BY athlete_id
            ORDER BY total_reps DESC, last_update ASC
        """, [self.session_id]).fetchall()
```

## 🚀 Optimisations recommandées

### 1. Dénormalisation pour performance
- Stocker les mouvements comme array pour requêtes GIN rapides
- Pré-calculer durée et difficulté lors de l'import
- Matérialiser les vues pour analytics fréquentes

### 2. Partitioning par date
```sql
-- Partitionner les résultats par mois
CREATE TABLE athlete_results_y2024m01 PARTITION OF athlete_results
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

### 3. Index spécialisés
```sql
-- Index partiel pour WODs récents uniquement
CREATE INDEX idx_recent_wods ON wod_definitions (created_at)
    WHERE created_at > NOW() - INTERVAL '90 days';

-- Index composé pour requêtes complexes
CREATE INDEX idx_wod_search ON wod_definitions
    (difficulty_score, duration_seconds)
    INCLUDE (title, movements_list);
```

---

## 📝 Notes d'implémentation

- **Consistance** : Utiliser des transactions pour maintenir la cohérence entre WOD et métadonnées
- **Monitoring** : Logger les requêtes lentes et optimiser en continu
- **Backup** : Sauvegarder le DSL source pour régénération des données
- **Versioning** : Gérer les évolutions du schéma AST avec des migrations

Cette architecture permet une intégration robuste du langage WODCraft dans des applications production tout en conservant la flexibilité pour des requêtes complexes et des analytics avancées.