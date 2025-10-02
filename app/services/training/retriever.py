from sentence_transformers import SentenceTransformer, InputExample
from torch.utils.data import DataLoader
import json
from datetime import datetime
from ...config.settings import settings

model = SentenceTransformer(settings.EMBEDDING_MODEL, device="cpu")

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
    model.fit(train_dataloader=dl, epochs=1, warmup_steps=100)
    model.save(f"models/{settings.EMBEDDING_MODEL}-finetuned-${datetime.now().strftime('%Y%m%d%H%M%S')}")