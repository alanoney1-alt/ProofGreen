"""
Knowledge Manager - RAG System with Pinecone for ESG Regulations
Manages vector embeddings and retrieval of regulatory knowledge
"""

import asyncio
import json
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import logging
import httpx

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeDocument:
    """A document in the knowledge base."""
    id: str
    content: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SearchResult:
    """Result from knowledge search."""
    document_id: str
    content: str
    score: float
    metadata: Dict[str, Any]


class KnowledgeManager:
    """
    RAG-based knowledge manager for ESG regulations.
    Uses Pinecone for vector storage and retrieval.
    """

    def __init__(
        self,
        pinecone_api_key: Optional[str] = None,
        pinecone_environment: str = "us-east-1",
        pinecone_index_name: str = "esg-regulations",
        anthropic_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None
    ):
        self.pinecone_api_key = pinecone_api_key
        self.pinecone_environment = pinecone_environment
        self.index_name = pinecone_index_name
        self.anthropic_api_key = anthropic_api_key
        self.openai_api_key = openai_api_key

        self._client = httpx.AsyncClient(timeout=60.0)
        self._index_host: Optional[str] = None

        # Local cache for frequently accessed documents
        self._cache: Dict[str, KnowledgeDocument] = {}

        # Knowledge categories
        self.categories = [
            "federal_regulations",
            "state_regulations",
            "epa_standards",
            "efficiency_standards",
            "tax_credits",
            "refrigerant_rules",
            "building_codes",
            "safety_certifications"
        ]

    async def initialize(self):
        """Initialize Pinecone connection and ensure index exists."""
        if not self.pinecone_api_key:
            logger.warning("Pinecone API key not configured - using local mode")
            return

        try:
            # Get index host from Pinecone
            response = await self._client.get(
                f"https://api.pinecone.io/indexes/{self.index_name}",
                headers={"Api-Key": self.pinecone_api_key}
            )

            if response.status_code == 200:
                data = response.json()
                self._index_host = data.get("host")
                logger.info(f"Connected to Pinecone index: {self.index_name}")
            elif response.status_code == 404:
                # Create index
                await self._create_index()
            else:
                logger.error(f"Pinecone error: {response.status_code}")

        except Exception as e:
            logger.error(f"Failed to initialize Pinecone: {e}")

    async def _create_index(self):
        """Create Pinecone index if it doesn't exist."""
        try:
            response = await self._client.post(
                "https://api.pinecone.io/indexes",
                headers={
                    "Api-Key": self.pinecone_api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "name": self.index_name,
                    "dimension": 1536,  # OpenAI embedding dimension
                    "metric": "cosine",
                    "spec": {
                        "serverless": {
                            "cloud": "aws",
                            "region": self.pinecone_environment
                        }
                    }
                }
            )
            response.raise_for_status()
            logger.info(f"Created Pinecone index: {self.index_name}")

            # Wait for index to be ready
            await asyncio.sleep(5)
            await self.initialize()

        except Exception as e:
            logger.error(f"Failed to create index: {e}")

    async def _get_embedding(self, text: str) -> Optional[List[float]]:
        """Get embedding vector for text using OpenAI."""
        if not self.openai_api_key:
            # Return mock embedding for testing
            return [0.0] * 1536

        try:
            response = await self._client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "text-embedding-3-small",
                    "input": text[:8000]  # Truncate to max tokens
                }
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]

        except Exception as e:
            logger.error(f"Embedding error: {e}")
            return None

    async def add_document(
        self,
        content: str,
        metadata: Dict[str, Any],
        doc_id: Optional[str] = None
    ) -> str:
        """Add a document to the knowledge base."""

        # Generate ID from content hash if not provided
        if not doc_id:
            doc_id = hashlib.sha256(content.encode()).hexdigest()[:16]

        # Get embedding
        embedding = await self._get_embedding(content)

        doc = KnowledgeDocument(
            id=doc_id,
            content=content,
            metadata=metadata,
            embedding=embedding
        )

        # Store in cache
        self._cache[doc_id] = doc

        # Store in Pinecone
        if self._index_host and embedding:
            try:
                await self._client.post(
                    f"https://{self._index_host}/vectors/upsert",
                    headers={
                        "Api-Key": self.pinecone_api_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "vectors": [{
                            "id": doc_id,
                            "values": embedding,
                            "metadata": {
                                **metadata,
                                "content": content[:1000],  # Store truncated content in metadata
                                "full_content_hash": hashlib.sha256(content.encode()).hexdigest()
                            }
                        }],
                        "namespace": metadata.get("category", "general")
                    }
                )
                logger.info(f"Added document to Pinecone: {doc_id}")

            except Exception as e:
                logger.error(f"Failed to store in Pinecone: {e}")

        return doc_id

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 5
    ) -> List[SearchResult]:
        """Search knowledge base for relevant documents."""

        # Get query embedding
        query_embedding = await self._get_embedding(query)

        if not query_embedding:
            # Fall back to keyword search in cache
            return self._local_search(query, category, top_k)

        if self._index_host:
            try:
                # Build filter
                pinecone_filter = {}
                if filters:
                    pinecone_filter = filters
                if category:
                    pinecone_filter["category"] = {"$eq": category}

                response = await self._client.post(
                    f"https://{self._index_host}/query",
                    headers={
                        "Api-Key": self.pinecone_api_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "vector": query_embedding,
                        "topK": top_k,
                        "includeMetadata": True,
                        "namespace": category or "",
                        "filter": pinecone_filter if pinecone_filter else None
                    }
                )
                response.raise_for_status()
                data = response.json()

                results = []
                for match in data.get("matches", []):
                    results.append(SearchResult(
                        document_id=match["id"],
                        content=match.get("metadata", {}).get("content", ""),
                        score=match["score"],
                        metadata=match.get("metadata", {})
                    ))

                return results

            except Exception as e:
                logger.error(f"Pinecone search error: {e}")

        return self._local_search(query, category, top_k)

    def _local_search(
        self,
        query: str,
        category: Optional[str],
        top_k: int
    ) -> List[SearchResult]:
        """Local keyword-based search fallback."""
        results = []
        query_terms = query.lower().split()

        for doc_id, doc in self._cache.items():
            if category and doc.metadata.get("category") != category:
                continue

            # Simple keyword matching
            content_lower = doc.content.lower()
            score = sum(1 for term in query_terms if term in content_lower)
            score = score / len(query_terms) if query_terms else 0

            if score > 0:
                results.append(SearchResult(
                    document_id=doc_id,
                    content=doc.content[:500],
                    score=score,
                    metadata=doc.metadata
                ))

        # Sort by score and return top k
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_k]

    async def get_regulation_context(
        self,
        vertical: str,
        state: str,
        equipment_type: Optional[str] = None
    ) -> str:
        """Get regulatory context for a specific scenario."""

        # Build query
        query_parts = [f"{vertical} regulations", f"{state} state requirements"]
        if equipment_type:
            query_parts.append(f"{equipment_type} compliance")

        query = " ".join(query_parts)

        # Search for relevant documents
        results = await self.search(
            query=query,
            filters={"vertical": vertical} if vertical else None,
            top_k=5
        )

        # Build context string
        context_parts = []
        for result in results:
            context_parts.append(f"[{result.metadata.get('regulation', 'Unknown')}]\n{result.content}")

        return "\n\n---\n\n".join(context_parts) if context_parts else "No specific regulations found."

    async def load_regulatory_knowledge(self, knowledge_path: str):
        """Load regulatory knowledge from JSON file."""
        try:
            with open(knowledge_path, "r") as f:
                knowledge = json.load(f)

            # Index nationwide standards
            nationwide = knowledge.get("nationwide_standards", {})
            for vertical, regulations in nationwide.items():
                for reg_id, reg_data in regulations.items():
                    content = f"""
                    Regulation: {reg_data.get('name', reg_id)}
                    Vertical: {vertical}
                    Requirement: {reg_data.get('requirement', '')}
                    Effective Date: {reg_data.get('effective_date', 'In effect')}
                    Details: {json.dumps(reg_data, indent=2)}
                    """

                    await self.add_document(
                        content=content.strip(),
                        metadata={
                            "category": "federal_regulations",
                            "vertical": vertical,
                            "regulation": reg_id,
                            "effective_date": reg_data.get("effective_date")
                        },
                        doc_id=f"fed_{vertical}_{reg_id}"
                    )

            # Index state overrides
            state_overrides = knowledge.get("state_overrides", {})
            for state, state_data in state_overrides.items():
                for reg_id, reg_data in state_data.items():
                    if not isinstance(reg_data, dict):
                        continue

                    content = f"""
                    State: {state}
                    Regulation: {reg_data.get('name', reg_id)}
                    Requirement: {reg_data.get('requirement', '')}
                    Effective Date: {reg_data.get('effective_date', 'In effect')}
                    Details: {json.dumps(reg_data, indent=2)}
                    """

                    await self.add_document(
                        content=content.strip(),
                        metadata={
                            "category": "state_regulations",
                            "state": state,
                            "regulation": reg_id,
                            "effective_date": reg_data.get("effective_date")
                        },
                        doc_id=f"state_{state}_{reg_id}"
                    )

            # Index tax credits
            tax_credits = knowledge.get("ira_tax_credits", {})
            for credit_id, credit_data in tax_credits.items():
                content = f"""
                Tax Credit: {credit_data.get('name', credit_id)}
                Section: {credit_id}
                Credit Rate: {credit_data.get('rate', 'N/A')}
                Maximum: ${credit_data.get('max_amount', 'No limit')}
                Eligible Equipment: {', '.join(credit_data.get('eligible_equipment', []))}
                Requirements: {json.dumps(credit_data.get('requirements', {}), indent=2)}
                """

                await self.add_document(
                    content=content.strip(),
                    metadata={
                        "category": "tax_credits",
                        "credit_type": credit_id,
                        "max_amount": credit_data.get("max_amount")
                    },
                    doc_id=f"credit_{credit_id}"
                )

            logger.info(f"Loaded regulatory knowledge: {len(self._cache)} documents")

        except Exception as e:
            logger.error(f"Failed to load knowledge: {e}")

    async def update_from_sources(self):
        """
        Scout and update knowledge from authoritative sources.
        This would be run periodically to keep knowledge current.
        """

        sources = [
            {
                "name": "EPA Regulations",
                "url": "https://www.epa.gov/regulatory-information",
                "category": "epa_standards"
            },
            {
                "name": "DOE Efficiency Standards",
                "url": "https://www.energy.gov/eere/buildings/appliance-and-equipment-standards-program",
                "category": "efficiency_standards"
            },
            {
                "name": "IRS Energy Credits",
                "url": "https://www.irs.gov/credits-deductions/energy-efficient-home-improvement-credit",
                "category": "tax_credits"
            }
        ]

        # In production, this would scrape/fetch from these sources
        # For now, log that we would update
        logger.info(f"Knowledge scout would update from {len(sources)} sources")

        return {
            "status": "completed",
            "sources_checked": len(sources),
            "documents_updated": 0,
            "last_update": datetime.now(timezone.utc).isoformat()
        }

    async def ask(
        self,
        question: str,
        context_filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Answer a question using RAG.
        Retrieves relevant documents and generates an answer.
        """

        # Search for relevant documents
        results = await self.search(
            query=question,
            filters=context_filters,
            top_k=5
        )

        # Build context
        context = "\n\n".join([
            f"[Source: {r.metadata.get('regulation', 'Unknown')}]\n{r.content}"
            for r in results
        ])

        # If Anthropic API is available, generate answer
        if self.anthropic_api_key:
            try:
                response = await self._client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "claude-sonnet-4-20250514",
                        "max_tokens": 1024,
                        "messages": [{
                            "role": "user",
                            "content": f"""Based on the following regulatory information, answer this question:

Question: {question}

Context:
{context}

Provide a clear, accurate answer citing specific regulations where applicable."""
                        }]
                    }
                )
                response.raise_for_status()
                data = response.json()

                return {
                    "answer": data["content"][0]["text"],
                    "sources": [r.metadata for r in results],
                    "confidence": max(r.score for r in results) if results else 0
                }

            except Exception as e:
                logger.error(f"Failed to generate answer: {e}")

        # Return context without generated answer
        return {
            "answer": None,
            "context": context,
            "sources": [r.metadata for r in results],
            "confidence": max(r.score for r in results) if results else 0
        }

    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()


# Convenience functions
async def create_knowledge_manager(
    pinecone_api_key: Optional[str] = None,
    anthropic_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None
) -> KnowledgeManager:
    """Create and initialize a knowledge manager."""
    manager = KnowledgeManager(
        pinecone_api_key=pinecone_api_key,
        anthropic_api_key=anthropic_api_key,
        openai_api_key=openai_api_key
    )
    await manager.initialize()
    return manager
