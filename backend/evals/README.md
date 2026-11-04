# Retrieval evaluation

Run `python backend/evaluate_retrieval.py backend/evals/golden_local.jsonl` from the root.
This uses one query embedding per distinct question (cached) and local retrieval,
with no conversational generation or speech. Configure the labelled cases for your
own documents before promoting an embedding migration. Historical JSON results and
RAG_AUDIT.md describe the former Ollama implementation and are not current benchmarks.
