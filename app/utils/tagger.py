from __future__ import annotations
import os, json, time
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

import numpy as np
import pandas as pd

# Try FAISS; if unavailable (e.g., macOS Apple Silicon without conda), fall back to a NumPy inner-product index
try:
    import faiss  # type: ignore
except Exception:  # pragma: no cover
    faiss = None  # type: ignore

from sentence_transformers import SentenceTransformer

from ..config.settings import settings
from ..utils.helpers import clean_html, normalize_arabic, keyword_overlap_reason


# ---- Minimal NumPy IP index with FAISS-like API ----
class NumpyIPIndex:
    def __init__(self, dim: int):
        self.dim = dim
        self._X: Optional[np.ndarray] = None

    def add(self, X: np.ndarray) -> None:
        # X should be L2-normalized already
        self._X = X.astype("float32", copy=False)

    def search(self, Q: np.ndarray, k: int) -> Tuple[np.ndarray, np.ndarray]:
        if self._X is None:
            raise RuntimeError("Index is empty")
        # Similarity scores via dot product (cosine, since normalized)
        S = np.matmul(Q, self._X.T)  # (q, n)
        # Partial top-k selection
        k = min(k, S.shape[1])
        idx = np.argpartition(-S, kth=k - 1, axis=1)[:, :k]
        part = np.take_along_axis(S, idx, axis=1)
        order = np.argsort(-part, axis=1)
        top_idx = np.take_along_axis(idx, order, axis=1)
        top_scores = np.take_along_axis(S, top_idx, axis=1)
        return top_scores.astype("float32"), top_idx.astype("int64")


def _normalize_L2_inplace(X: np.ndarray) -> None:
    # L2-normalize rows in-place
    n = np.linalg.norm(X, axis=1, keepdims=True)
    n[n == 0] = 1.0
    X /= n


@dataclass
class TagRow:
    name: str
    slug: str
    url: Optional[str]
    description: Optional[str]


class TagSuggester:
    def __init__(self):
        self.model_name = settings.EMBEDDING_MODEL
        self.device = settings.DEVICE
        self.embedder: Optional[SentenceTransformer] = None
        self.cross_encoder = None
        self.tags: List[TagRow] = []
        self.tag_texts: List[str] = []
        self.embeddings: Optional[np.ndarray] = None
        self.index = None  # faiss.Index or NumpyIPIndex
        self.index_path = os.path.join(settings.STORAGE_DIR, "tag_index.faiss")
        self.emb_path = os.path.join(settings.STORAGE_DIR, "tag_emb.npy")
        self.meta_path = os.path.join(settings.STORAGE_DIR, "tags.json")
        self.last_loaded_ts: float = 0.0

    # ---------- public ----------
    def load(self, force_rebuild: bool = False) -> None:
        self._load_models()
        csv_mtime = (
            os.path.getmtime(settings.TAGS_CSV)
            if os.path.exists(settings.TAGS_CSV)
            else 0
        )
        cache_ok = (not force_rebuild) and self._cache_is_valid(csv_mtime)
        if cache_ok:
            self._load_cache()
        else:
            self._build_from_csv()
            self._save_cache(csv_mtime)
        self.last_loaded_ts = time.time()

    def _hybrid_score(self, text: str, tag_text: str, semantic_score: float, alpha=0.8):
        kw_reason = keyword_overlap_reason(text, tag_text)
        overlap = 0.0
        if "Shared terms:" in kw_reason:
            words = kw_reason.split(":")[1].split(",")
            overlap = min(0.5, len(words) / 10.0)
        return alpha * semantic_score + (1 - alpha) * overlap

    def _preprocess_text(self, text: str) -> str:
        import re
        from unidecode import unidecode

        # Normalize Arabic if enabled
        if settings.NORMALIZE_ARABIC:
            text = normalize_arabic(text)

        # Transliterate mixed scripts (optional, keeps embeddings cleaner)
        text = unidecode(text)

        # Remove URLs, HTML, emoji, and excessive punctuation
        text = re.sub(r"http\S+|www\S+|<[^>]+>|[^\w\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        text = clean_html(text)

        return text

    def suggest(
        self,
        text: str,
        k: int = 5,
        min_score: float = 0.2,
        use_reranker: Optional[bool] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:

        text_proc = self._preprocess_text(text)

        qstr = f"query: {text_proc}" if "e5" in self.model_name.lower() else text_proc
        qv = self._embed_texts([qstr]).astype("float32")

        if self.embeddings is None or qv.shape[1] != self.embeddings.shape[1]:
            # model was changed since the last build → rebuild index now
            self.reload()
            # re-embed the query with the current model
            qv = self._embed_texts(
                [
                    (
                        text_proc
                        if "e5" not in self.model_name.lower()
                        else f"query: {text_proc}"
                    )
                ]
            ).astype("float32")
            if faiss is not None:
                faiss.normalize_L2(qv)
            else:
                _normalize_L2_inplace(qv)

        # normalize for cosine
        if faiss is not None:
            faiss.normalize_L2(qv)
        else:
            _normalize_L2_inplace(qv)

        k = max(1, min(k, len(self.tags)))
        D, I = self.index.search(qv, min(100, max(k, 1)))  # shortlist up to 100
        scores = D[0].tolist()
        indices = I[0].tolist()

        items = []
        for score, idx in zip(scores, indices):
            if idx < 0:
                continue
            tag = self.tags[idx]
            if not tag.slug or not tag.name:  # guard against empty tags
                continue
            ttext = self.tag_texts[idx]
            if score < min_score:
                continue

            score = self._hybrid_score(text_proc, ttext, score)
            reason = keyword_overlap_reason(text_proc, ttext)
            items.append(
                {
                    "slug": tag.slug,
                    "name": tag.name,
                    "url": tag.url,
                    "description": "",  # tag.description,
                    "score": float(round(score, 4)),
                    "reason": reason,
                }
            )
        # Optional rerank
        use_ce = (
            settings.USE_CROSS_ENCODER if use_reranker is None else bool(use_reranker)
        )

        avg_score = np.mean([it["score"] for it in items]) if items else 0
        if use_ce and items and avg_score < 0.6:
            items = self._rerank_with_cross_encoder(text_proc, items)

        return items[:k], {
            "model": self.model_name,
            "count": len(self.tags),
            "csv": settings.TAGS_CSV,
            "reranker": settings.CROSS_ENCODER_MODEL if use_ce else None,
            "engine": "faiss" if faiss is not None else "numpy",
        }

    def reload(self) -> None:
        self.load(force_rebuild=True)

    # ---------- internal ----------
    def _load_models(self):
        if self.embedder is None:
            self.embedder = SentenceTransformer(self.model_name, device=self.device)
        if settings.USE_CROSS_ENCODER and self.cross_encoder is None:
            try:
                from sentence_transformers import CrossEncoder

                self.cross_encoder = CrossEncoder(
                    settings.CROSS_ENCODER_MODEL, device=self.device
                )
            except Exception:
                self.cross_encoder = None

    def _cache_is_valid(self, csv_mtime: float) -> bool:
        paths = [self.emb_path, self.meta_path]
        if getattr(faiss, "__name__", None):  # if FAISS is available
            paths.append(self.index_path)
        if not all(os.path.exists(p) for p in paths):
            return False

        # csv must not be newer than cache
        cache_mtime = min(os.path.getmtime(p) for p in paths)
        if cache_mtime < csv_mtime:
            return False

        # model / dim must match
        try:
            meta = json.load(open(self.meta_path, "r", encoding="utf-8"))
            if meta.get("model") != self.model_name:
                return False
            if "dim" not in meta:
                return False
        except Exception:
            return False
        return True

    def _load_cache(self):
        if faiss is not None and os.path.exists(self.index_path):
            self.index = faiss.read_index(self.index_path)
        meta = json.load(open(self.meta_path, "r", encoding="utf-8"))
        self.tags = [TagRow(**row) for row in meta["tags"]]
        self.tag_texts = meta["tag_texts"]
        self.embeddings = np.load(self.emb_path)
        # build index if FAISS was not stored
        if self.index is None:
            self.index = NumpyIPIndex(self.embeddings.shape[1])
            self.index.add(self.embeddings)

    def _build_from_csv(self):
        print(f"Loading tags from {os.path.curdir}")
        try:
            if not os.path.exists(settings.TAGS_CSV):
                raise FileNotFoundError(f"CSV not found at {settings.TAGS_CSV}")
            # read CSV robustly: treat everything as str & preserve empty strings
            df = pd.read_csv(
                settings.TAGS_CSV,
                dtype=str,
                keep_default_na=False,
                encoding="utf-8-sig",
            )
            # ensure required columns
            for col in ("name", "slug", "url", "description"):
                if col not in df.columns:
                    raise ValueError(f"Missing column '{col}' in CSV")
            # strip whitespace
            df = df.applymap(lambda x: x.strip() if isinstance(x, str) else "")
            # drop rows where name or slug is blank
            before = len(df)
            df = df[(df["name"] != "") & (df["slug"] != "")]
            after = len(df)
            dropped = before - after
            if dropped > 0:
                print(f"[build] Dropped {dropped} tag rows with empty name/slug")

            # now build TagRow list
            self.tags = []
            for _, r in df.iterrows():
                t = TagRow(
                    name=r["name"],
                    slug=r["slug"],
                    url=r["url"] or None,
                    description="",  # r["description"] or None,
                )
                self.tags.append(t)

            # rest remains the same
            self.tag_texts = [self._render_tag_text(t) for t in self.tags]
            texts = (
                [normalize_arabic(t) for t in self.tag_texts]
                if settings.NORMALIZE_ARABIC
                else self.tag_texts
            )

            X = self._embed_texts(texts).astype("float32")
            if faiss is not None:
                faiss.normalize_L2(X)
            else:
                _normalize_L2_inplace(X)
            self.embeddings = X

            if faiss is not None:
                self.index = faiss.IndexFlatIP(X.shape[1])
                self.index.add(X)
            else:
                self.index = NumpyIPIndex(X.shape[1])
                self.index.add(X)
        except Exception as e:
            print(f"Error building from CSV: {e}")

    def _save_cache(self, csv_mtime: float):
        if faiss is not None and self.index is not None:
            try:
                faiss.write_index(self.index, self.index_path)
            except Exception:
                pass
        np.save(self.emb_path, self.embeddings)
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "tags": [t.__dict__ for t in self.tags],
                    "tag_texts": self.tag_texts,
                    "csv_mtime": csv_mtime,
                    "model": self.model_name,
                    "dim": int(self.embeddings.shape[1]),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    def _render_tag_text(self, t: TagRow) -> str:
        parts = [t.name]
        if t.description:
            parts.append(t.description)
        if t.slug:
            parts.append(f"slug:{t.slug}")
        if t.url:
            parts.append(f"url:{t.url}")
        text = " — ".join(parts)
        return f"passage: {text}" if "e5" in self.model_name.lower() else text

    def _embed_texts(self, texts: List[str]) -> np.ndarray:
        embs = self.embedder.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=False,
            batch_size=64,
            show_progress_bar=False,
        )
        return embs

    def _rerank_with_cross_encoder(
        self, query_text: str, items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        if self.cross_encoder is None:
            return items
        from sentence_transformers.util import batch_to_device

        pairs = [(query_text, self._item_text(i)) for i in items]
        scores = self.cross_encoder.predict(pairs).tolist()
        for it, sc in zip(items, scores):
            it["score"] = float(sc)
        items.sort(key=lambda x: x["score"], reverse=True)
        return items

    def _item_text(self, item: Dict[str, Any]) -> str:
        slug = item.get("slug", "")
        name = item.get("name", "")
        desc = item.get("description", "") or ""
        url = item.get("url", "") or ""
        return " — ".join([x for x in [name, desc, f"slug:{slug}", f"url:{url}"] if x])
