from datetime import datetime
from sentence_transformers import CrossEncoder, InputExample
from torch.utils.data import DataLoader
from ...config.settings import settings
import json

model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device="cpu")
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
    model.fit(train_dataloader=dl, epochs=1, warmup_steps=100)
    model.save(f"models/{settings.EMBEDDING_MODEL}-finetuned-${datetime.now().strftime('%Y%m%d%H%M%S')}")
