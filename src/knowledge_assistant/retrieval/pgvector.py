"""pgvector-backed Retriever.

See retrieval/protocols.py for the Retriever Protocol this implements.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from knowledge_assistant.domain import RetrievedChunk
from knowledge_assistant.retrieval.protocols import Retriever
from knowledge_assistant.storage.models import DocumentChunkModel, DocumentModel


class PgVectorRetriever(Retriever):
    """Vector similarity search over document_chunks via pgvector's cosine distance operator
    (matches the HNSW index's vector_cosine_ops from Step 3)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search(
        self,
        query_embedding: list[float],
        top_k: int,
        similarity_threshold: float | None = None,
    ) -> list[RetrievedChunk]:
        # pgvector's cosine_distance is `1 - cosine_similarity` (range [0, 2]; 0 = identical
        # direction). RetrievedChunk.score is similarity, not distance, so score = 1 - distance -
        # easy to invert by mistake, hence spelling it out here rather than just in ORDER BY.
        distance = DocumentChunkModel.embedding.cosine_distance(query_embedding)

        query = (
            select(DocumentChunkModel, DocumentModel.name, distance.label("distance"))
            .join(DocumentModel, DocumentChunkModel.document_id == DocumentModel.id)
            .order_by(distance)
            .limit(top_k)
        )
        if similarity_threshold is not None:
            # Applied as a SQL WHERE clause, not a post-query filter: it's the same distance
            # expression already computed for ORDER BY, so pushing it into WHERE lets Postgres
            # use the HNSW index and discard below-threshold rows before the LIMIT, instead of
            # fetching top_k rows and then throwing some away.
            # score >= threshold  <=>  1 - distance >= threshold  <=>  distance <= 1 - threshold
            query = query.where(distance <= 1 - similarity_threshold)

        result = await self._session.execute(query)

        return [
            RetrievedChunk(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_name=document_name,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                score=1 - distance_value,
                metadata=chunk.metadata_,
            )
            for chunk, document_name, distance_value in result.all()
        ]
