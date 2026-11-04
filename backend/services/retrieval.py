"""Local retrieval with exactly one query vector and explicit profile validation."""
import json
import re
from pathlib import Path
import chromadb
from langchain_chroma import Chroma
import config
from services.embedding_service import OpenAIEmbeddings, embedding_profile
from services.versioning import select_documents
from services.lexical_service import lexical_search
from services.evidence_gate import assess_evidence, EvidenceStatus

def active_store():
    path = Path(config.VECTOR_DB_DIR) / "ingestion_manifest.json"
    if not path.exists():
        raise RuntimeError("The knowledge index has not been built.")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    profile = embedding_profile()
    settings = manifest.get("settings", {})
    if settings.get("embedding_provider") != "openai" or settings.get("embedding_profile", {}).get("fingerprint") != profile.fingerprint:
        raise RuntimeError("The knowledge index needs OpenAI migration and promotion.")
    collection_name = manifest["active_collection"]
    client = chromadb.PersistentClient(path=config.VECTOR_DB_DIR)
    collection = client.get_collection(collection_name)
    meta = collection.metadata or {}
    if meta.get("embedding_profile") != profile.fingerprint or meta.get("embedding_dimensions") != profile.dimensions:
        raise RuntimeError("Incompatible knowledge index.")
    return Chroma(client=client, collection_name=collection_name, embedding_function=OpenAIEmbeddings(profile))

def contextual_question(question, history):
    # Deterministic continuity affects local lexical ranking only, never extra embeddings.
    if history and re.search(r"\b(it|its|that|those|they|them|more|elaborate)\b", question, re.I):
        previous = next((m["content"] for m in reversed(history) if m["role"] == "user"), "")
        return previous + " " + question
    return question


def retrieve_from_store(store, question, top_k, history=None):
    vector = store._embedding_function.embed_query(question)
    semantic = store.similarity_search_by_vector(vector, k=config.RETRIEVAL_FETCH_K)
    contextual = contextual_question(question, history)
    lexical = lexical_search(Path(config.VECTOR_DB_DIR), store._collection.name,
                             contextual, config.RETRIEVAL_FETCH_K) if config.HYBRID_SEARCH_ENABLED else []
    ranked, scores = {}, {}
    for results in (semantic, lexical):
        for rank, doc in enumerate(results):
            key = (doc.metadata.get("source"), doc.metadata.get("page"), doc.page_content)
            ranked[key] = doc
            scores[key] = scores.get(key, 0) + 1/(config.HYBRID_RRF_K+rank+1)
    docs = [ranked[key] for key in sorted(scores, key=scores.get, reverse=True)]
    return select_documents(docs, contextual, top_k)


def retrieve(question, history=None):
    store = active_store()
    docs = retrieve_from_store(store, question, config.QA_TOP_K, history)
    decision = assess_evidence(contextual_question(question, history), docs)
    usable = list(decision.documents) if decision.status in {EvidenceStatus.ANSWERABLE, EvidenceStatus.PARTIAL_EVIDENCE} else []
    context = "\n\n".join(
        f"Source: {d.metadata.get('source', '')}; page: {d.metadata.get('page', '')}; "
        f"version: {d.metadata.get('version', '')}\n{d.page_content}" for d in usable)
    return context[:config.CONTEXT_MAX_CHARS]
