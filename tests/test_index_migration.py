import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import pytest
import config
import train_engine
from services.embedding_service import OpenAIEmbeddings
from services.retrieval import active_store, retrieve_from_store, contextual_question

@pytest.fixture
def storage(tmp_path,monkeypatch):
    raw=tmp_path/"raw";raw.mkdir()
    db=tmp_path/"vectors"
    monkeypatch.setattr(config,"VECTOR_DB_DIR",str(db))
    monkeypatch.setattr(config,"EMBED_CACHE_FILE",str(db/"embeddings.sqlite"))
    monkeypatch.setattr(config,"OPENAI_EMBED_DIMENSIONS",3)
    monkeypatch.setattr(config,"OCR_ENABLED",False)
    monkeypatch.setattr(config,"INGESTION_WORKERS",1)
    def vectors(**kw):
        return NS(data=[NS(index=i,embedding=[1.,2.,3.]) for i in range(len(kw["input"]))],usage=None)
    create=Mock(side_effect=vectors)
    with patch("services.embedding_service.client",return_value=NS(embeddings=NS(create=create))):
        yield raw,db,create

def test_real_chroma_ingestion_incremental_and_retrieval(storage):
    raw,db,create=storage
    source=raw/"excavator_2026.txt"
    source.write_text("A bucket wheel excavator removes material continuously using a rotating wheel fitted with buckets. The excavator operates in surface mines.")
    train_engine.train(raw)
    first=create.call_count
    assert first>=1
    train_engine.train(raw)
    assert create.call_count==first
    store=active_store()
    docs=retrieve_from_store(store,"What is a bucket wheel excavator?",5)
    assert docs and "excavator_2026" in docs[0].metadata["source"]
    after=create.call_count
    retrieve_from_store(store,"What is a bucket wheel excavator?",5)
    assert create.call_count==after
    source.write_text(source.read_text()+" Maintenance is performed with the machine isolated.")
    train_engine.train(raw)
    assert create.call_count>after
    assert active_store()._collection.count()>0

def test_legacy_index_rejected_without_embedding(storage):
    raw,db,create=storage
    db.mkdir()
    (db/"ingestion_manifest.json").write_text(json.dumps({"active_collection":"legacy", "settings":{"embedding_provider":"ollama"}}))
    with pytest.raises(RuntimeError,match="migration"):
        active_store()
    assert create.call_count==0

def test_candidate_does_not_overwrite_active(storage):
    raw,db,create=storage
    (raw/"manual.txt").write_text("The mine excavator uses a rotating wheel and buckets to excavate material continuously and safely.")
    train_engine.train(raw)
    before=train_engine.load_manifest(db)
    with patch.object(config,"OPENAI_EMBED_MODEL","another-model"):
        train_engine.train(raw)
        after=train_engine.load_manifest(db)
        assert after["active_collection"]==before["active_collection"]
        assert after["candidate"]["active_collection"]!=before["active_collection"]
        with pytest.raises(RuntimeError,match="migration"):
            active_store()
    assert active_store()._collection.count()>0

def test_contextual_followup():
    assert contextual_question("How does it work?",[{"role":"user","content":"What is a bucket wheel excavator?"}]).startswith("What is a bucket")
