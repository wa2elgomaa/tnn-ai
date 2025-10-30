# news-tag-suggester

FastAPI service that suggests tags from a controlled taxonomy (`tags.csv`) given article text. Uses multilingual sentence embeddings + cosine similarity. Prefers FAISS when available; otherwise falls back to a NumPy inner‑product index (works great on macOS Apple Silicon without extra installs).


## Models 
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
cross-encoder/ms-marco-MiniLM-L-6-v2 
intfloat/multilingual-e5-base 
BAAI/bge-base-en-v1.5



# Download local models 

```bash
pip install huggingface_hub
huggingface-cli download intfloat/e5-base-v2  --local-dir ./models/intfloat/e5-base-v2
huggingface-cli download cross-encoder/ms-marco-MiniLM-L-6-v2  --local-dir ./models/cross-encoder/ms-marco-MiniLM-L-6-v2
```

# Using Ollama for GPT-OSS models 
```bash
docker exec tnn-ai-ollama-1 ollama pull openai/gpt-oss-20b:Q4_K_M
```

## Quick start

```bash
# make sure this python is your new 3.11+, not /Applications/Xcode.../3.9
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
# # run without uvloop/httptools and single-process:
# UVICORN_NO_UVLOOP=1 UVICORN_NO_HTTP_TOOLS=1 TOKENIZERS_PARALLELISM=false \
# HF_HUB_OFFLINE=1 EMBEDDING_MODEL=./models/paraphrase-multilingual-MiniLM-L12-v2 \
python -m uvicorn app.main:app --port 8000 --loop asyncio --http h11 --workers 1
uvicorn app.main:app --port 8000 --reload --loop asyncio --http h11
uvicorn app.main:app --port 8000 --reload --loop asyncio --http h11 --workers 1
```


Open: http://localhost:8000/docs


### Test
```bash
curl -s -X POST 'http://localhost:8000/suggest' \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "ADNOC announced a new upstream concession in Abu Dhabi; analysts say the IPO market is heating up in the UAE.",
    "k": 5
  }' | jq
```

### macOS (Apple Silicon) notes
- The `requirements.txt` **skips** `faiss-cpu` automatically on Apple Silicon. You can run with the built‑in NumPy index (no extra steps).
- If you want FAISS on Apple Silicon, use Conda:
  ```bash
  conda create -n news-tags python=3.11 -y
  conda activate news-tags
  conda install -c conda-forge faiss-cpu=1.8.0 -y
  pip install -r requirements.txt
  ```
  Then start the server as usual.

## CSV Format
Required header columns: `name,slug,url,description`.

Each row describes a tag; the service concatenates these fields for embedding (e.g., `"{name} — {description} — slug:{slug} — url:{url}"`).

## API
- `GET /health` → status, model info
- `POST /suggest` → `{ text, k?, min_score?, use_reranker? }`
- `POST /reload` → rebuilds index from CSV

Response example:
```json
{
  "suggestions": [
    {"slug":"adnoc","name":"ADNOC","url":"...","description":"...","score":0.83,"reason":"Shared terms: adnoc, abu"},
    {"slug":"ipo","name":"IPO","url":"...","description":"...","score":0.79,"reason":"Semantic similarity to tag description"}
  ],
  "meta": {"elapsed_ms": 42, "engine": "numpy", "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", "count": 500}
}
```

## Docker
Docker uses Linux images, so `faiss-cpu` installs fine inside the container regardless of your host OS.
```Dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY data ./data
COPY .env.example ./.env
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Tuning
- Increase `min_score` to filter weak matches (e.g., `0.35`).
- Optional cross-encoder reranker via `.env`.
- Add section/desk priors by boosting scores before sorting (extend `tagger.py`).

## License
MIT
```
bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env if needed (path to CSV, model name)
uvicorn app.main:app --reload --port 8000
```

Open: http://localhost:8000/docs

### Test
```bash
curl -s -X POST 'http://localhost:8000/suggest' \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "ADNOC announced a new upstream concession in Abu Dhabi; analysts say the IPO market is heating up in the UAE.",
    "k": 5
  }' | jq
```

## CSV Format
Required header columns: `name,slug,url,description`.

Each row describes a tag; the service concatenates these fields for embedding (e.g., `"{name} — {description} — slug:{slug} — url:{url}"`).

## API
- `GET /health` → status, model info
- `POST /suggest` → JSON body `{ text: string, k?: number, min_score?: number, use_reranker?: boolean }`
- `POST /reload` → rebuilds index from CSV

Response example:
```json
{
  "suggestions": [
    {"slug":"adnoc","name":"ADNOC","url":"...","description":"...","score":0.83,"reason":"Shared terms: adnoc, abu"},
    {"slug":"ipo","name":"IPO","url":"...","description":"...","score":0.79,"reason":"Semantic similarity to tag description"}
  ],
  "meta": {"elapsed_ms": 42, "model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", "count": 500}
}
```

## Reranker (optional)
Enable a cross-encoder reranker (slower but sharper ranking):
```env
USE_CROSS_ENCODER=true
CROSS_ENCODER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
```
This re-scores the shortlist using pairwise similarity between the article text and each tag text.

## Arabic/Multilingual Notes
- Default embedding model is multilingual; switch to `BAAI/bge-m3` for stronger performance (heavier).
- `NORMALIZE_ARABIC=true` applies light normalization before embedding.
- You can add Arabic/English aliases into `description` fields to improve matching.

## Persistence & Hot Reload
- On startup, the service builds (or loads) a FAISS index + embeddings into `./storage`.
- If `tags.csv` changes, call `POST /reload` to rebuild.

## Docker
```Dockerfile
FROM python:3.11-slim

# (faiss runtime)
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data
COPY .env.example ./.env

ENV PORT=8000
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Build & run:
```bash
docker build -t news-tag-suggester .
docker run --rm -p 8000:8000 -e TAGS_CSV=/app/data/tags.csv news-tag-suggester
```

## Tuning
- Increase `min_score` to filter weak matches (e.g., `0.35`).
- Add section/desk priors by boosting scores before sorting (extend `tagger.py`).
- Swap to `pgvector` if you prefer Postgres (replace FAISS in `tagger.py`).

## License
MIT (adapt as needed)
