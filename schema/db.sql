-- enable extensions (once per DB)
CREATE EXTENSION IF NOT EXISTS vector;          -- pgvector
CREATE EXTENSION IF NOT EXISTS pg_trgm;         -- trigram for fuzzy search

-- Multi-tenant / multi-set friendly
CREATE TABLE tag_sets (
  id            bigserial PRIMARY KEY,
  code          text UNIQUE NOT NULL,           -- e.g., 'default'
  title         text NOT NULL,
  lang          text DEFAULT 'en',
  created_at    timestamptz DEFAULT now()
);

-- Tags and their embedding
CREATE TABLE tags (
  id            bigserial PRIMARY KEY,
  tag_set_id    bigint NOT NULL REFERENCES tag_sets(id) ON DELETE CASCADE,
  slug          text NOT NULL,
  name          text NOT NULL,
  description   text,
  url           text,
  aliases       jsonb DEFAULT '[]',
  embedding     vector(768),                    -- dim must match your model
  active        boolean DEFAULT true,
  created_at    timestamptz DEFAULT now(),
  UNIQUE (tag_set_id, slug)
);

-- Optional: searchable text column + indexes
ALTER TABLE tags
  ADD COLUMN tsv tsvector
  GENERATED ALWAYS AS (
    to_tsvector('english', coalesce(name,'') || ' ' || coalesce(description,''))
  ) STORED;

-- Full-text + fuzzy + vector indexes
CREATE INDEX tags_tsv_gin     ON tags USING GIN (tsv);               -- FTS
CREATE INDEX tags_name_trgm   ON tags USING GIN (name gin_trgm_ops); -- fuzzy
CREATE INDEX tags_slug_trgm   ON tags USING GIN (slug gin_trgm_ops); -- fuzzy
-- Vector index: choose HNSW (better speed/recall) or IVFFlat (faster build)
CREATE INDEX tags_embedding_hnsw ON tags USING hnsw (embedding vector_cosine_ops);
-- or: CREATE INDEX tags_embedding_ivf ON tags USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);


-- Optional: articles you score (helps analytics, not required for /suggest)
CREATE TABLE articles (
  id            bigserial PRIMARY KEY,
  external_id   text UNIQUE,     -- your CMS articleId
  section       text,
  text_hash     text,            -- sha1(title+dek+body)
  created_at    timestamptz DEFAULT now()
);

-- Store each /suggest call (for audit/AB tests)
CREATE TABLE suggestions (
  id            bigserial PRIMARY KEY,
  article_id    bigint REFERENCES articles(id) ON DELETE SET NULL,
  model_name    text NOT NULL,       -- e.g., 'e5-base-v2'
  model_dim     int  NOT NULL,       -- 768, 384, ...
  engine        text,                -- 'pgvector', 'faiss', etc.
  elapsed_ms    int,
  created_at    timestamptz DEFAULT now()
);

-- Candidate items returned by that call
CREATE TABLE suggestion_items (
  id               bigserial PRIMARY KEY,
  suggestion_id    bigint REFERENCES suggestions(id) ON DELETE CASCADE,
  tag_id           bigint REFERENCES tags(id) ON DELETE CASCADE,
  rank             int,
  score_dense      double precision,
  score_lexical    double precision,
  score_rerank     double precision
);

-- Editor feedback (like/dislike) for online learning
CREATE TABLE feedback (
  id            bigserial PRIMARY KEY,
  article_id    bigint REFERENCES articles(id) ON DELETE SET NULL,
  tag_id        bigint REFERENCES tags(id) ON DELETE CASCADE,
  text_hash     text,                     -- to dedupe variant texts
  label         text CHECK (label IN ('like','dislike')) NOT NULL,
  user_id       text,                     -- optional, for per-editor stats
  model_name    text,
  model_version text,
  created_at    timestamptz DEFAULT now(),
  UNIQUE (article_id, tag_id, text_hash, model_name, model_version)
);
