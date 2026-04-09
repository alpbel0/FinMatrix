"""Mock ChromaDB client for Week 5 embedding storage tests.

Provides in-memory simulation of ChromaDB operations without
requiring actual ChromaDB server.

Key features:
- In-memory vector storage
- Metadata filtering support ($eq, $ne, $in, $nin, $gt, $lt, $gte, $lte)
- Query result simulation with distance calculation
- Collection management
- Error injection capabilities

Usage:
    from tests.mocks.mock_chromadb import (
        MockChromaClient,
        create_mock_chroma_client,
        create_mock_embedding,
    )

    client = create_mock_chroma_client()
    collection = client.create_collection("test_chunks")

    # Add documents
    collection.add(
        ids=["chunk1", "chunk2"],
        embeddings=[create_mock_embedding(), create_mock_embedding()],
        metadatas=[{"symbol": "THYAO"}, {"symbol": "GARAN"}],
    )

    # Query
    results = collection.query(
        query_embeddings=[create_mock_embedding()],
        n_results=5,
        where={"symbol": "THYAO"},
    )
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
import uuid

# Default embedding dimension (OpenAI text-embedding-3-small)
DEFAULT_EMBEDDING_DIMENSION = 1536


@dataclass
class MockChromaDocument:
    """Mock document stored in ChromaDB."""
    id: str
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)
    document: str | None = None  # Original text content


@dataclass
class MockQueryResult:
    """Mock result from ChromaDB query.

    Matches ChromaDB's query result structure for compatibility.
    """
    ids: list[list[str]]
    embeddings: list[list[list[float]]] | None = None
    documents: list[list[str | None]] | None = None
    metadatas: list[list[dict[str, Any]]] | None = None
    distances: list[list[float]] | None = None


class MockChromaCollection:
    """Mock ChromaDB collection for testing.

    Provides in-memory storage and basic query functionality
    without requiring a real ChromaDB server.
    """

    def __init__(
        self,
        name: str = "test_collection",
        dimension: int = DEFAULT_EMBEDDING_DIMENSION,
        metadata: dict[str, Any] | None = None,
    ):
        self.name = name
        self.dimension = dimension
        self.metadata = metadata or {}
        self._documents: dict[str, MockChromaDocument] = {}

    # --- Core Operations ---

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]] | None = None,
        documents: list[str | None] | None = None,
    ) -> None:
        """Add documents to the collection.

        Args:
            ids: List of document IDs
            embeddings: List of embedding vectors
            metadatas: Optional list of metadata dicts
            documents: Optional list of document texts

        Raises:
            ValueError: If ids and embeddings have different lengths
            ValueError: If embedding dimension doesn't match collection
        """
        if len(ids) != len(embeddings):
            raise ValueError("ids and embeddings must have same length")

        metadatas = metadatas or [{}] * len(ids)
        documents = documents or [None] * len(ids)

        for i, doc_id in enumerate(ids):
            # Validate embedding dimension
            if len(embeddings[i]) != self.dimension:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {self.dimension}, "
                    f"got {len(embeddings[i])}"
                )

            self._documents[doc_id] = MockChromaDocument(
                id=doc_id,
                embedding=embeddings[i],
                metadata=metadatas[i],
                document=documents[i],
            )

    def query(
        self,
        query_embeddings: list[list[float]],
        n_results: int = 10,
        where: dict[str, Any] | None = None,
        where_document: dict[str, Any] | None = None,
        include: list[str] | None = None,
    ) -> MockQueryResult:
        """Query the collection for similar documents.

        Args:
            query_embeddings: Query vectors
            n_results: Number of results per query
            where: Metadata filter (e.g., {"symbol": "THYAO"})
            where_document: Document content filter (not implemented)
            include: Fields to include in results

        Returns:
            MockQueryResult with matching documents
        """
        include = include or ["metadatas", "documents", "distances"]

        # Apply metadata filter
        filtered_docs = self._apply_metadata_filter(where)

        # Build results for each query embedding
        all_ids = []
        all_embeddings = []
        all_documents = []
        all_metadatas = []
        all_distances = []

        for query_emb in query_embeddings:
            # Calculate distances
            scored_docs = []
            for doc in filtered_docs:
                distance = self._calculate_distance(query_emb, doc.embedding)
                scored_docs.append((doc, distance))

            # Sort by distance (ascending - lower distance = more similar)
            scored_docs.sort(key=lambda x: x[1])

            # Take top n_results
            top_docs = scored_docs[:n_results]

            all_ids.append([doc.id for doc, _ in top_docs])
            if "embeddings" in include:
                all_embeddings.append([doc.embedding for doc, _ in top_docs])
            if "documents" in include:
                all_documents.append([doc.document for doc, _ in top_docs])
            if "metadatas" in include:
                all_metadatas.append([doc.metadata for doc, _ in top_docs])
            if "distances" in include:
                all_distances.append([dist for _, dist in top_docs])

        return MockQueryResult(
            ids=all_ids,
            embeddings=all_embeddings if all_embeddings else None,
            documents=all_documents if all_documents else None,
            metadatas=all_metadatas if all_metadatas else None,
            distances=all_distances if all_distances else None,
        )

    def get(
        self,
        ids: list[str] | None = None,
        where: dict[str, Any] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        include: list[str] | None = None,
    ) -> dict[str, Any]:
        """Retrieve documents by ID or metadata filter.

        Args:
            ids: List of document IDs to retrieve
            where: Metadata filter
            limit: Maximum number of documents to return
            offset: Number of documents to skip
            include: Fields to include in results

        Returns:
            Dict with ids, embeddings, metadatas, documents
        """
        include = include or ["metadatas", "documents"]

        # Filter by IDs if provided
        if ids:
            docs = [self._documents.get(doc_id) for doc_id in ids]
            docs = [d for d in docs if d is not None]
        else:
            docs = self._apply_metadata_filter(where)

        # Apply offset and limit
        if offset:
            docs = docs[offset:]
        if limit:
            docs = docs[:limit]

        result = {
            "ids": [doc.id for doc in docs],
        }
        if "embeddings" in include:
            result["embeddings"] = [doc.embedding for doc in docs]
        if "metadatas" in include:
            result["metadatas"] = [doc.metadata for doc in docs]
        if "documents" in include:
            result["documents"] = [doc.document for doc in docs]

        return result

    def delete(
        self,
        ids: list[str] | None = None,
        where: dict[str, Any] | None = None,
    ) -> None:
        """Delete documents by ID or metadata filter.

        Args:
            ids: List of document IDs to delete
            where: Metadata filter for documents to delete
        """
        if ids:
            for doc_id in ids:
                self._documents.pop(doc_id, None)
        elif where:
            docs_to_delete = self._apply_metadata_filter(where)
            for doc in docs_to_delete:
                self._documents.pop(doc.id, None)

    def update(
        self,
        ids: list[str],
        embeddings: list[list[float]] | None = None,
        metadatas: list[dict[str, Any]] | None = None,
        documents: list[str | None] | None = None,
    ) -> None:
        """Update existing documents.

        Args:
            ids: List of document IDs to update
            embeddings: New embedding vectors
            metadatas: New metadata dicts
            documents: New document texts
        """
        for i, doc_id in enumerate(ids):
            if doc_id in self._documents:
                doc = self._documents[doc_id]
                if embeddings:
                    doc.embedding = embeddings[i]
                if metadatas:
                    doc.metadata = metadatas[i]
                if documents:
                    doc.document = documents[i]

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict[str, Any]] | None = None,
        documents: list[str | None] | None = None,
    ) -> None:
        """Add or update documents.

        Args:
            ids: List of document IDs
            embeddings: List of embedding vectors
            metadatas: Optional list of metadata dicts
            documents: Optional list of document texts
        """
        metadatas = metadatas or [{}] * len(ids)
        documents = documents or [None] * len(ids)

        for i, doc_id in enumerate(ids):
            self._documents[doc_id] = MockChromaDocument(
                id=doc_id,
                embedding=embeddings[i],
                metadata=metadatas[i],
                document=documents[i],
            )

    def count(self) -> int:
        """Return number of documents in collection.

        Returns:
            Document count
        """
        return len(self._documents)

    def reset(self) -> None:
        """Clear all documents from collection."""
        self._documents.clear()

    def peek(self, limit: int = 10) -> dict[str, Any]:
        """Preview documents without full query.

        Args:
            limit: Maximum number of documents to preview

        Returns:
            Dict with ids, metadatas, documents
        """
        docs = list(self._documents.values())[:limit]
        return {
            "ids": [doc.id for doc in docs],
            "metadatas": [doc.metadata for doc in docs],
            "documents": [doc.document for doc in docs],
        }

    # --- Helper Methods ---

    def _apply_metadata_filter(
        self,
        where: dict[str, Any] | None,
    ) -> list[MockChromaDocument]:
        """Apply metadata filter to documents.

        Args:
            where: Filter conditions

        Returns:
            List of matching documents
        """
        if not where:
            return list(self._documents.values())

        filtered = []
        for doc in self._documents.values():
            if self._matches_filter(doc.metadata, where):
                filtered.append(doc)

        return filtered

    def _matches_filter(
        self,
        metadata: dict[str, Any],
        filter_cond: dict[str, Any],
    ) -> bool:
        """Check if metadata matches filter conditions.

        Supports operators: $eq, $ne, $in, $nin, $gt, $lt, $gte, $lte

        Args:
            metadata: Document metadata
            filter_cond: Filter conditions

        Returns:
            True if metadata matches filter
        """
        for key, condition in filter_cond.items():
            value = metadata.get(key)

            # Simple equality check
            if isinstance(condition, (str, int, float, bool)):
                if value != condition:
                    return False

            # Operator-based checks
            elif isinstance(condition, dict):
                for op, op_value in condition.items():
                    if op == "$eq" and value != op_value:
                        return False
                    elif op == "$ne" and value == op_value:
                        return False
                    elif op == "$in" and value not in op_value:
                        return False
                    elif op == "$nin" and value in op_value:
                        return False
                    elif op == "$gt" and (value is None or value <= op_value):
                        return False
                    elif op == "$lt" and (value is None or value >= op_value):
                        return False
                    elif op == "$gte" and (value is None or value < op_value):
                        return False
                    elif op == "$lte" and (value is None or value > op_value):
                        return False

        return True

    def _calculate_distance(
        self,
        vec1: list[float],
        vec2: list[float],
    ) -> float:
        """Calculate L2 (Euclidean) distance between vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Distance value (lower = more similar)
        """
        # Simple L2 distance without numpy dependency
        sum_sq = sum((a - b) ** 2 for a, b in zip(vec1, vec2))
        return sum_sq ** 0.5


class MockChromaClient:
    """Mock ChromaDB client for testing.

    Manages multiple collections and provides server-like interface.
    """

    def __init__(self, host: str = "localhost", port: int = 8001):
        self.host = host
        self.port = port
        self._collections: dict[str, MockChromaCollection] = {}

    def create_collection(
        self,
        name: str,
        dimension: int = DEFAULT_EMBEDDING_DIMENSION,
        metadata: dict[str, Any] | None = None,
    ) -> MockChromaCollection:
        """Create a new collection.

        Args:
            name: Collection name
            dimension: Embedding dimension
            metadata: Collection metadata

        Returns:
            MockChromaCollection instance

        Raises:
            ValueError: If collection already exists
        """
        if name in self._collections:
            raise ValueError(f"Collection '{name}' already exists")

        collection = MockChromaCollection(
            name=name,
            dimension=dimension,
            metadata=metadata,
        )
        self._collections[name] = collection
        return collection

    def get_collection(self, name: str) -> MockChromaCollection:
        """Get an existing collection.

        Args:
            name: Collection name

        Returns:
            MockChromaCollection instance

        Raises:
            ValueError: If collection doesn't exist
        """
        if name not in self._collections:
            raise ValueError(f"Collection '{name}' does not exist")
        return self._collections[name]

    def get_or_create_collection(
        self,
        name: str,
        dimension: int = DEFAULT_EMBEDDING_DIMENSION,
        metadata: dict[str, Any] | None = None,
    ) -> MockChromaCollection:
        """Get or create a collection.

        Args:
            name: Collection name
            dimension: Embedding dimension (for new collection)
            metadata: Collection metadata (for new collection)

        Returns:
            MockChromaCollection instance
        """
        if name in self._collections:
            return self._collections[name]
        return self.create_collection(name, dimension, metadata)

    def delete_collection(self, name: str) -> None:
        """Delete a collection.

        Args:
            name: Collection name
        """
        self._collections.pop(name, None)

    def list_collections(self) -> list[str]:
        """List all collection names.

        Returns:
            List of collection names
        """
        return list(self._collections.keys())

    def reset(self) -> None:
        """Clear all collections."""
        self._collections.clear()

    def heartbeat(self) -> int:
        """Return heartbeat timestamp (mock).

        Returns:
            Current timestamp
        """
        return int(datetime.now().timestamp())


# --- Factory Functions ---

def create_mock_embedding(
    dimension: int = DEFAULT_EMBEDDING_DIMENSION,
    seed: int | None = None,
) -> list[float]:
    """Create a mock embedding vector.

    Generates a normalized random vector for testing.
    Uses pure Python (no numpy dependency).

    Args:
        dimension: Vector dimension
        seed: Random seed for reproducibility

    Returns:
        List of floats representing embedding
    """
    import random

    if seed is not None:
        random.seed(seed)

    # Generate random values
    vec = [random.gauss(0, 1) for _ in range(dimension)]

    # Normalize (L2 norm)
    norm = sum(x ** 2 for x in vec) ** 0.5
    if norm > 0:
        vec = [x / norm for x in vec]

    return vec


def create_mock_chroma_client() -> MockChromaClient:
    """Create a mock ChromaDB client for testing.

    Returns:
        MockChromaClient instance
    """
    return MockChromaClient()


def create_mock_collection_with_documents(
    name: str = "test_chunks",
    documents: list[dict[str, Any]] | None = None,
    dimension: int = DEFAULT_EMBEDDING_DIMENSION,
) -> MockChromaCollection:
    """Create a collection pre-populated with mock documents.

    Args:
        name: Collection name
        documents: List of dicts with 'id', 'metadata', 'document' keys
        dimension: Embedding dimension

    Returns:
        MockChromaCollection with documents added
    """
    client = create_mock_chroma_client()
    collection = client.create_collection(name, dimension)

    if documents:
        ids = [doc.get("id", str(uuid.uuid4())) for doc in documents]
        embeddings = [create_mock_embedding(dimension, seed=i) for i in range(len(ids))]
        metadatas = [doc.get("metadata", {}) for doc in documents]
        doc_texts = [doc.get("document", None) for doc in documents]

        collection.add(
            ids=ids,
            embeddings=embeddings,
            metadatas=metadatas,
            documents=doc_texts,
        )

    return collection