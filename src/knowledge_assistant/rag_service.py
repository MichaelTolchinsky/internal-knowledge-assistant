"""RAG service orchestrator: the query-time pipeline from docs/ARCHITECTURE.md section 3.2
(question -> embedding -> retrieval -> prompt -> LLM -> citations -> Answer).

Per docs/CODING-GUIDELINES.md section 2: this module contains no HTTP concerns, no SQL, and no
Bedrock/transformers SDK calls itself - it composes the Protocols only. Concrete
implementations are wired in by the caller (see dependencies.py), never imported here.
"""

from __future__ import annotations

from knowledge_assistant.citations.protocols import CitationExtractor
from knowledge_assistant.config import settings
from knowledge_assistant.domain import Answer
from knowledge_assistant.embeddings.protocols import EmbeddingModel
from knowledge_assistant.llm.protocols import LLMClient
from knowledge_assistant.prompts.protocols import PromptBuilder
from knowledge_assistant.retrieval.protocols import Retriever

# No config field for this yet (checked config.py/.env.example - neither has one). Hardcoded
# here as a reasonable default for a grounded, citation-aware paragraph answer; a candidate for
# a future `settings.llm_max_tokens` field if/when it needs to be tuned per the evaluation
# experiment workflow (docs/CODING-GUIDELINES.md section 6).
_DEFAULT_MAX_TOKENS = 512


class RAGService:
    """Orchestrates one question -> Answer round trip. Holds no HTTP/SQL/SDK code - every
    external boundary is a Protocol, injected by the caller (see dependencies.py)."""

    def __init__(
        self,
        embedding_model: EmbeddingModel,
        retriever: Retriever,
        prompt_builder: PromptBuilder,
        llm_client: LLMClient,
        citation_extractor: CitationExtractor,
    ) -> None:
        self._embedding_model = embedding_model
        self._retriever = retriever
        self._prompt_builder = prompt_builder
        self._llm_client = llm_client
        self._citation_extractor = citation_extractor

    async def answer_question(self, question: str) -> Answer:
        query_embedding = (await self._embedding_model.embed([question]))[0]

        # Empty results (no chunks pass similarity_threshold, or nothing retrieved at all) flow
        # through unchanged - prompt_builder's <no_context> handling (Step 7) already covers an
        # empty chunks list, no special-casing needed here.
        chunks = await self._retriever.search(
            query_embedding, settings.top_k, settings.similarity_threshold
        )

        prompt = self._prompt_builder.build(question, chunks)
        llm_response = await self._llm_client.generate(prompt, max_tokens=_DEFAULT_MAX_TOKENS)

        return self._citation_extractor.extract(llm_response.answer, chunks)
