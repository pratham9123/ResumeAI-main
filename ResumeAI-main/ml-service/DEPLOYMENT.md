# ResumeAI RAG deployment

The FAISS index is generated from the committed curated JSON knowledge base during
deployment startup. The generated binary index and aligned metadata are deliberately
excluded from Git by `knowledge_base/index/.gitignore`.

Startup order:

1. Install the exact versions in `requirements.txt`.
2. Run `python -m knowledge_base.prepare_runtime`.
3. Start Gunicorn only if preparation succeeds.
4. Confirm `/health` reports `rag.ready: true` when RAG is enabled.

For the current small corpus this is preferable to committing a platform-sensitive
FAISS binary or operating object storage. Object storage becomes appropriate when
index generation is too slow for deployment, the corpus is managed separately, or
multiple services must consume the same signed immutable artifact.

The `RAG_INDEX_PATH` directory must be writable during deployment. Unless artifacts
are downloaded by a separate release job, `RAG_METADATA_PATH` must point to
`RAG_INDEX_PATH/chunks.json` so the preparation command and runtime use the same
vector-aligned metadata.
