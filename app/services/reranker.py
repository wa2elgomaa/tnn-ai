from datetime import datetime
from sentence_transformers import CrossEncoder, InputExample, SentenceTransformer
from torch.utils.data import DataLoader
from ..config.settings import settings
import json

reranker_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device="cpu")
embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL, device="cpu")

train_data = []


def train():
    with open("storage/feedback.jsonl") as f:
        for line in f:
            r = json.loads(line)
            article = r["text"]
            tag_text = "... build like in tagify ..."  # by slug
            label = 1.0 if r["label"] == "like" else 0.0
            train_data.append(InputExample(texts=[article, tag_text], label=label))

    dl = DataLoader(train_data, batch_size=16, shuffle=True)
    reranker_model.fit(train_dataloader=dl, epochs=1, warmup_steps=100)
    reranker_model.save(
        f"models/{settings.EMBEDDING_MODEL}-finetuned-${datetime.now().strftime('%Y%m%d%H%M%S')}"
    )


def tagify(row):
    # must match your runtime _render_tag_text
    base = f"{row['name']} — {row.get('description','')} — slug:{row['slug']}"
    if "e5" in settings.EMBEDDING_MODEL.lower():
        return "passage: " + base
    return base


def train():
    train_data = []
    with open("storage/feedback.jsonl") as f:
        for line in f:
            r = json.loads(line)
            article = r["text"]
            tag_text = tagify(r["tag"])
            label = 1.0 if r["label"] == "like" else 0.0
            train_data.append(InputExample(texts=[article, tag_text], label=label))
    dl = DataLoader(train_data, batch_size=16, shuffle=True)
    embedding_model.fit(train_dataloader=dl, epochs=1, warmup_steps=100)
    embedding_model.save(
        f"models/{settings.EMBEDDING_MODEL}-finetuned-${datetime.now().strftime('%Y%m%d%H%M%S')}"
    )
