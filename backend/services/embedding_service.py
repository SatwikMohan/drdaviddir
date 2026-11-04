"""Profile-isolated, persistent content-hash cache for OpenAI vectors."""
import hashlib
import json
import math
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from langchain_core.embeddings import Embeddings
import config
from services.openai_service import client, usage, record_usage

_LOCK = threading.RLock()

@dataclass(frozen=True)
class EmbeddingProfile:
    model: str
    query_prefix: str = ""
    document_prefix: str = ""
    dimensions: int = config.OPENAI_EMBED_DIMENSIONS
    normalization: str = config.EMBED_NORMALIZATION
    version: int = 2

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(self.__dict__, sort_keys=True).encode()).hexdigest()[:16]

    def as_dict(self):
        return dict(self.__dict__, fingerprint=self.fingerprint, provider="openai")

def embedding_profile(model=None):
    return EmbeddingProfile(model or config.OPENAI_EMBED_MODEL,
        config.EMBED_QUERY_PREFIX, config.EMBED_DOCUMENT_PREFIX,
        config.OPENAI_EMBED_DIMENSIONS, config.EMBED_NORMALIZATION)

class OpenAIEmbeddings(Embeddings):
    def __init__(self, profile=None):
        self.profile = profile or embedding_profile()
        self.last_documents_ms = 0

    def _vectors(self, texts):
        keys = [hashlib.sha256((self.profile.fingerprint+"\0"+text).encode()).hexdigest() for text in texts]
        Path(config.EMBED_CACHE_FILE).parent.mkdir(parents=True, exist_ok=True)
        # Serialize cache misses in this process, including overlapping ingestion batches.
        with _LOCK, sqlite3.connect(config.EMBED_CACHE_FILE, timeout=60) as db:
            db.execute("CREATE TABLE IF NOT EXISTS vectors (key TEXT PRIMARY KEY, vector TEXT NOT NULL)")
            found = {}
            for key in set(keys):
                row = db.execute("SELECT vector FROM vectors WHERE key=?", (key,)).fetchone()
                if row:
                    vector = json.loads(row[0])
                    if len(vector) != self.profile.dimensions or not all(math.isfinite(v) for v in vector):
                        raise ValueError("Invalid cached vector")
                    found[key] = vector
            missing = list(dict.fromkeys(key for key in keys if key not in found))
            inputs = dict(zip(keys, texts))
            for offset in range(0, len(missing), config.EMBEDDING_BATCH_SIZE):
                batch = missing[offset:offset+config.EMBEDDING_BATCH_SIZE]
                with usage("embeddings", self.profile.model) as record:
                    response = client().embeddings.create(model=self.profile.model,
                        dimensions=self.profile.dimensions, input=[inputs[key] for key in batch])
                    record_usage(record, response)
                ordered = sorted(response.data, key=lambda item: item.index)
                if len(ordered) != len(batch):
                    raise ValueError("Embedding count mismatch")
                for key, item in zip(batch, ordered):
                    vector = item.embedding
                    if len(vector) != self.profile.dimensions or not all(math.isfinite(v) for v in vector):
                        raise ValueError("Embedding dimension or value mismatch")
                    norm = math.sqrt(sum(v*v for v in vector))
                    if norm == 0:
                        raise ValueError("Zero embedding")
                    if self.profile.normalization == "l2":
                        vector = [v/norm for v in vector]
                    found[key] = vector
                    db.execute("INSERT OR REPLACE INTO vectors VALUES (?, ?)", (key, json.dumps(vector)))
                db.commit()
            return [found[key] for key in keys]

    def embed_documents(self, texts):
        started = time.monotonic()
        vectors = self._vectors([self.profile.document_prefix+t for t in texts])
        self.last_documents_ms = (time.monotonic()-started)*1000
        return vectors

    def embed_query(self, text):
        return self._vectors([self.profile.query_prefix+" ".join(text.split())])[0]
