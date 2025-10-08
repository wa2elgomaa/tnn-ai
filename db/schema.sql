-- schema.sql
BEGIN;
-- 0) Extensions
CREATE EXTENSION IF NOT EXISTS vector;
-- pgvector
CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- trigram (fuzzy)
-- CREATE EXTENSION IF NOT EXISTS btree_gin; -- optional
/* ============================================================
 TAGS (for tag suggestion) – pgvector kNN inside Postgres
 ============================================================ */
CREATE TABLE IF NOT EXISTS tag_sets (
  id BIGSERIAL PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  lang TEXT DEFAULT 'en',
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS tags (
  id BIGSERIAL PRIMARY KEY,
  tag_set_id BIGINT NOT NULL REFERENCES tag_sets(id) ON DELETE CASCADE,
  slug TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT,
  url TEXT,
  aliases JSONB DEFAULT '[]',
  embedding VECTOR(768),
  -- <- adjust if your model dim differs
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE (tag_set_id, slug)
);
-- Full-text helper for quick lexical score/autocomplete
ALTER TABLE tags
ADD COLUMN IF NOT EXISTS tsv TSVECTOR GENERATED ALWAYS AS (
    to_tsvector(
      'english',
      coalesce(name, '') || ' ' || coalesce(description, '')
    )
  ) STORED;
CREATE INDEX IF NOT EXISTS tags_tsv_gin ON tags USING GIN (tsv);
CREATE INDEX IF NOT EXISTS tags_slug_trgm ON tags USING GIN (slug gin_trgm_ops);
CREATE INDEX IF NOT EXISTS tags_name_trgm ON tags USING GIN (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS tags_embedding_hnsw ON tags USING hnsw (embedding vector_cosine_ops);
-- Alternative vector index (faster build, tunable): ivfflat with lists
-- CREATE INDEX tags_embedding_ivf ON tags USING ivfflat (embedding vector_cosine_ops) WITH (lists = 200);
/* ============================================================
 ARTICLES (for related-articles & analytics)
 ============================================================ */
-- Core article table (store important fields + raw payload)
CREATE TABLE IF NOT EXISTS articles (
  id BIGSERIAL PRIMARY KEY,
  document_id TEXT UNIQUE NOT NULL,
  -- Root._id
  canonical_url TEXT,
  subtype TEXT,
  created_date TIMESTAMPTZ,
  display_date TIMESTAMPTZ,
  first_publish_date TIMESTAMPTZ,
  publish_date TIMESTAMPTZ,
  last_updated_date TIMESTAMPTZ,
  -- concatenated ContentElement.content (plain)
  -- vector for related-article ANN
  embedding VECTOR(768),
  -- <- adjust to your model
  -- raw JSON blobs (keep full fidelity)
  headline TEXT,
  subheadline TEXT,
  description TEXT,
  label TEXT,
  content_elements JSONB,
  promo_items JSONB,
  credits JSONB,
  taxonomy JSONB,
  raw JSONB,
  -- entire original payload (optional)
  text_hash TEXT,
  -- stable fingerprint of title+dek+body (for caching/feedback)
  created_at TIMESTAMPTZ DEFAULT now()
);
-- FTS over main text fields
ALTER TABLE articles
ADD COLUMN IF NOT EXISTS tsv TSVECTOR GENERATED ALWAYS AS (
    to_tsvector(
      'english',
      coalesce(headline, '') || ' ' || coalesce(subheadline, '') || ' ' || coalesce(description, '')
    )
  ) STORED;
CREATE INDEX IF NOT EXISTS articles_tsv_gin ON articles USING GIN (tsv);
CREATE INDEX IF NOT EXISTS articles_canonical_trgm ON articles USING GIN (canonical_url gin_trgm_ops);
CREATE INDEX IF NOT EXISTS article_embedding_hnsw ON articles USING hnsw (embedding vector_cosine_ops);
/* ============================================================
 SUGGESTION LOGS (optional, useful for evaluation/ablation)
 ============================================================ */
CREATE TABLE IF NOT EXISTS suggestions (
  id BIGSERIAL PRIMARY KEY,
  article_id BIGINT REFERENCES articles(id) ON DELETE
  SET NULL,
    model_name TEXT NOT NULL,
    -- e.g. 'e5-base-v2'
    model_dim INT NOT NULL,
    -- 768, 384, ...
    engine TEXT,
    -- 'pgvector', 'faiss', etc.
    elapsed_ms INT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS suggestion_items (
  id BIGSERIAL PRIMARY KEY,
  suggestion_id BIGINT REFERENCES suggestions(id) ON DELETE CASCADE,
  tag_id BIGINT REFERENCES tags(id) ON DELETE CASCADE,
  rank INT,
  score_dense DOUBLE PRECISION,
  score_lexical DOUBLE PRECISION,
  score_rerank DOUBLE PRECISION
);
/* ============================================================
 FEEDBACK (your specified schema, with referential links)
 ============================================================ */
CREATE TABLE IF NOT EXISTS feedback (
  id BIGSERIAL PRIMARY KEY,
  article_id BIGINT REFERENCES articles(id) ON DELETE
  SET NULL,
    tag_id BIGINT REFERENCES tags(id) ON DELETE
  SET NULL,
    -- if you map to your catalog
    slug TEXT NOT NULL,
    -- keep raw slug from UI, too
    text_hash TEXT NOT NULL,
    -- fingerprint of text at time of feedback
    label TEXT NOT NULL CHECK (label IN ('like', 'dislike')),
    score DOUBLE PRECISION,
    reason TEXT,
    model_name TEXT,
    model_version TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (
      article_id,
      slug,
      text_hash,
      model_name,
      model_version
    )
);
CREATE INDEX IF NOT EXISTS feedback_article_idx ON feedback(article_id);
CREATE INDEX IF NOT EXISTS feedback_slug_idx ON feedback(slug);
CREATE INDEX IF NOT EXISTS feedback_label_idx ON feedback(label);
COMMIT;