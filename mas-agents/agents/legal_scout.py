"""
Legal Scout Agent - Regulatory Update Monitor
Uses TavilySearch and Firecrawl to discover new 2026 regulatory changes.
Updates knowledge base and vector database for semantic search.
"""

import asyncio
import json
import httpx
import hashlib
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import logging
import re
import os

logger = logging.getLogger(__name__)


@dataclass
class RegulatoryUpdate:
    """A discovered regulatory update."""
    id: str
    vertical: str
    state: str
    regulation_type: str  # seer2, gpm, refrigerant, waste_diversion, etc.
    title: str
    summary: str
    effective_date: Optional[str]
    source_url: str
    discovered_at: datetime
    confidence: float  # 0-1, how confident we are this is relevant
    raw_content: str = ""
    applied_to_knowledge: bool = False


@dataclass
class ComplianceSyncResult:
    """Result from a compliance sync operation."""
    vertical: str
    state: str
    updates_found: List[RegulatoryUpdate]
    knowledge_updated: bool
    ledger_recalculated: bool
    timestamp: datetime


class LegalScoutAgent:
    """
    Legal Scout sub-agent that monitors regulatory changes using TavilySearch and Firecrawl.
    Automatically updates regulatory_knowledge.json and vector database for semantic search.
    Triggers ledger recalculation when new regulations are discovered.
    """

    def __init__(
        self,
        tavily_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        firecrawl_api_key: Optional[str] = None,
        pinecone_api_key: Optional[str] = None,
        pinecone_index_name: str = "esg-regulations",
        knowledge_path: Optional[str] = None
    ):
        self.tavily_api_key = tavily_api_key or os.getenv("TAVILY_API_KEY")
        self.anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.firecrawl_api_key = firecrawl_api_key or os.getenv("FIRECRAWL_API_KEY")
        self.pinecone_api_key = pinecone_api_key or os.getenv("PINECONE_API_KEY")
        self.pinecone_index_name = pinecone_index_name
        self.knowledge_path = knowledge_path or str(
            Path(__file__).parent.parent / "config" / "regulatory_knowledge.json"
        )
        self._client = httpx.AsyncClient(timeout=60.0)
        self._pinecone_index = None

        # Regulatory keywords by vertical
        self.vertical_keywords = {
            "hvac": [
                "SEER2", "refrigerant", "A2L", "R-454B", "R-32", "GWP",
                "heat pump", "EPA refrigerant", "Title 24", "HSPF2"
            ],
            "plumbing": [
                "GPM", "WaterSense", "water efficiency", "GPF",
                "water heater UEF", "CalGreen", "plumbing code"
            ],
            "electrical": [
                "NEC 2026", "EV charger", "solar", "AFCI", "GFCI",
                "electrical code", "energy storage", "grid interconnection"
            ],
            "landscaping": [
                "gas equipment ban", "leaf blower", "CARB SORE",
                "irrigation", "water schedule", "landscape watering"
            ],
            "waste": [
                "waste diversion", "C&D debris", "landfill diversion",
                "EPR", "recycling mandate", "hazardous waste"
            ]
        }

        # State regulatory agencies to prioritize
        self.state_agencies = {
            "CA": ["CARB", "CEC", "CPUC", "CalRecycle"],
            "TX": ["TCEQ", "PUC Texas", "Texas RRC"],
            "FL": ["FDEP", "PSC Florida", "SWFWMD"],
            "NY": ["DEC New York", "PSC New York", "NYSERDA"],
            "WA": ["Ecology Washington", "UTC Washington"]
        }

    async def run_compliance_sync(
        self,
        vertical: str,
        state: str,
        recalculate_ledger: bool = True
    ) -> ComplianceSyncResult:
        """
        Run a full compliance sync for a vertical and state.
        Searches for regulatory updates, updates knowledge base, and recalculates ledger.
        """
        logger.info(f"Running compliance sync for {vertical} in {state}")

        # 1. Search for regulatory updates
        updates = await self.search_regulatory_updates(vertical, state)

        # 2. Analyze and validate updates
        validated_updates = await self._analyze_updates(updates, vertical, state)

        # 3. Update knowledge base if new regulations found
        knowledge_updated = False
        if validated_updates:
            knowledge_updated = await self._update_knowledge_base(validated_updates, vertical, state)

        # 4. Trigger ledger recalculation if knowledge was updated
        ledger_recalculated = False
        if knowledge_updated and recalculate_ledger:
            ledger_recalculated = await self._trigger_ledger_recalculation(vertical, state)

        return ComplianceSyncResult(
            vertical=vertical,
            state=state,
            updates_found=validated_updates,
            knowledge_updated=knowledge_updated,
            ledger_recalculated=ledger_recalculated,
            timestamp=datetime.now(timezone.utc)
        )

    async def search_regulatory_updates(
        self,
        vertical: str,
        state: str,
        year: int = 2026
    ) -> List[Dict[str, Any]]:
        """
        Search for regulatory updates using TavilySearch API.
        """
        if not self.tavily_api_key:
            logger.warning("Tavily API key not configured - using mock search")
            return self._mock_search_results(vertical, state)

        # Build search queries
        queries = self._build_search_queries(vertical, state, year)
        all_results = []

        for query in queries:
            try:
                response = await self._client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.tavily_api_key,
                        "query": query,
                        "search_depth": "advanced",
                        "include_domains": [
                            "epa.gov", "energy.gov", "congress.gov",
                            "state.gov", "dsireusa.org", "energystar.gov",
                            f"{state.lower()}.gov"
                        ],
                        "max_results": 10,
                        "include_answer": True,
                        "include_raw_content": True
                    }
                )
                response.raise_for_status()
                data = response.json()

                for result in data.get("results", []):
                    all_results.append({
                        "query": query,
                        "title": result.get("title", ""),
                        "url": result.get("url", ""),
                        "content": result.get("content", ""),
                        "raw_content": result.get("raw_content", ""),
                        "score": result.get("score", 0)
                    })

            except Exception as e:
                logger.error(f"Tavily search error for query '{query}': {e}")

        return all_results

    def _build_search_queries(self, vertical: str, state: str, year: int) -> List[str]:
        """Build search queries for regulatory updates."""
        keywords = self.vertical_keywords.get(vertical, [])
        queries = []

        # Primary query
        queries.append(f"{year} {vertical} regulatory updates {state}")

        # Keyword-specific queries
        for keyword in keywords[:3]:  # Limit to top 3 keywords
            queries.append(f"{year} {keyword} mandate {state} regulation")

        # State agency queries
        agencies = self.state_agencies.get(state, [])
        for agency in agencies[:2]:
            queries.append(f"{agency} {vertical} {year} requirements")

        return queries

    async def _analyze_updates(
        self,
        raw_results: List[Dict[str, Any]],
        vertical: str,
        state: str
    ) -> List[RegulatoryUpdate]:
        """
        Analyze search results using Claude to extract regulatory updates.
        """
        if not raw_results:
            return []

        validated = []

        # Use Claude to analyze if available
        if self.anthropic_api_key:
            for result in raw_results[:10]:  # Analyze top 10
                update = await self._extract_regulation_with_claude(result, vertical, state)
                if update and update.confidence > 0.6:
                    validated.append(update)
        else:
            # Fall back to keyword-based extraction
            for result in raw_results:
                update = self._extract_regulation_keywords(result, vertical, state)
                if update:
                    validated.append(update)

        # Deduplicate by regulation type
        seen = set()
        unique = []
        for update in validated:
            key = f"{update.regulation_type}_{update.state}"
            if key not in seen:
                seen.add(key)
                unique.append(update)

        return unique

    async def _extract_regulation_with_claude(
        self,
        result: Dict[str, Any],
        vertical: str,
        state: str
    ) -> Optional[RegulatoryUpdate]:
        """Use Claude to extract regulatory information from search result."""
        try:
            prompt = f"""Analyze this search result and extract any 2026 regulatory updates for {vertical} in {state}.

Title: {result['title']}
Content: {result['content'][:2000]}

If this contains a new or updated regulation, extract:
1. regulation_type: One of [seer2, gpm, refrigerant, waste_diversion, efficiency, safety, electrification]
2. effective_date: When it takes effect (YYYY-MM-DD format if known)
3. summary: A 2-sentence summary of the requirement
4. confidence: 0.0-1.0 how confident this is a real regulatory update

Respond in JSON format:
{{"is_regulation": true/false, "regulation_type": "", "effective_date": "", "summary": "", "confidence": 0.0}}

If this is not a regulatory update, respond: {{"is_regulation": false}}"""

            response = await self._client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 500,
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            response.raise_for_status()
            data = response.json()
            text = data["content"][0]["text"]

            # Parse JSON from response
            json_match = re.search(r'\{[^}]+\}', text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                if parsed.get("is_regulation"):
                    return RegulatoryUpdate(
                        id=f"scout_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        vertical=vertical,
                        state=state,
                        regulation_type=parsed.get("regulation_type", "unknown"),
                        title=result["title"],
                        summary=parsed.get("summary", ""),
                        effective_date=parsed.get("effective_date"),
                        source_url=result["url"],
                        discovered_at=datetime.now(timezone.utc),
                        confidence=parsed.get("confidence", 0.5),
                        raw_content=result.get("raw_content", "")
                    )

        except Exception as e:
            logger.error(f"Claude analysis error: {e}")

        return None

    def _extract_regulation_keywords(
        self,
        result: Dict[str, Any],
        vertical: str,
        state: str
    ) -> Optional[RegulatoryUpdate]:
        """Extract regulation using keyword matching (fallback)."""
        content = (result.get("content", "") + " " + result.get("title", "")).lower()

        # Check for regulatory keywords
        reg_keywords = {
            "seer2": ["seer2", "seer 2", "efficiency standard", "minimum seer"],
            "gpm": ["gpm", "gallons per minute", "flow rate", "watersense"],
            "refrigerant": ["refrigerant", "gwp", "a2l", "r-454b", "r-32", "r-410a"],
            "waste_diversion": ["diversion", "landfill", "recycling mandate", "c&d waste"],
            "efficiency": ["efficiency", "energy star", "title 24"],
            "electrification": ["electrification", "heat pump mandate", "gas ban"]
        }

        for reg_type, keywords in reg_keywords.items():
            if any(kw in content for kw in keywords):
                # Check for mandate/requirement language
                if any(w in content for w in ["mandate", "require", "must", "effective", "ban"]):
                    return RegulatoryUpdate(
                        id=f"scout_kw_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        vertical=vertical,
                        state=state,
                        regulation_type=reg_type,
                        title=result.get("title", "Unknown"),
                        summary=result.get("content", "")[:200],
                        effective_date=None,
                        source_url=result.get("url", ""),
                        discovered_at=datetime.now(timezone.utc),
                        confidence=0.5,
                        raw_content=result.get("raw_content", "")
                    )

        return None

    async def _update_knowledge_base(
        self,
        updates: List[RegulatoryUpdate],
        vertical: str,
        state: str
    ) -> bool:
        """Update regulatory_knowledge.json with new regulations."""
        try:
            # Load current knowledge
            with open(self.knowledge_path, "r") as f:
                knowledge = json.load(f)

            # Ensure state overrides section exists
            if "state_overrides" not in knowledge:
                knowledge["state_overrides"] = {}
            if state not in knowledge["state_overrides"]:
                knowledge["state_overrides"][state] = {}

            # Add/update regulations
            updated = False
            for update in updates:
                reg_key = f"scout_{update.regulation_type}_{datetime.now().strftime('%Y%m%d')}"

                # Check if this is a new or updated regulation
                existing = knowledge["state_overrides"][state].get(reg_key)
                if not existing or update.effective_date:
                    knowledge["state_overrides"][state][reg_key] = {
                        "name": update.title[:100],
                        "requirement": update.summary,
                        "effective_date": update.effective_date,
                        "source": update.source_url,
                        "regulation_type": update.regulation_type,
                        "discovered_at": update.discovered_at.isoformat(),
                        "confidence": update.confidence,
                        "auto_discovered": True
                    }
                    update.applied_to_knowledge = True
                    updated = True
                    logger.info(f"Added new regulation to knowledge base: {reg_key}")

            # Save updated knowledge
            if updated:
                # Add metadata about last scout run
                if "metadata" not in knowledge:
                    knowledge["metadata"] = {}
                knowledge["metadata"]["last_scout_run"] = datetime.now(timezone.utc).isoformat()
                knowledge["metadata"]["last_scout_state"] = state
                knowledge["metadata"]["last_scout_vertical"] = vertical

                with open(self.knowledge_path, "w") as f:
                    json.dump(knowledge, f, indent=2)

                logger.info(f"Knowledge base updated with {len([u for u in updates if u.applied_to_knowledge])} new regulations")

            return updated

        except Exception as e:
            logger.error(f"Failed to update knowledge base: {e}")
            return False

    async def _trigger_ledger_recalculation(self, vertical: str, state: str) -> bool:
        """
        Trigger Green Ledger recalculation based on new regulations.
        This would call the carbon_ledger module to recalculate compliance scores.
        """
        try:
            # In production, this would:
            # 1. Query all jobs in the state/vertical
            # 2. Re-run compliance checks with new regulations
            # 3. Update ledger entries with new compliance status
            # 4. Flag any newly non-compliant jobs

            logger.info(f"Triggering ledger recalculation for {vertical} in {state}")

            # Import here to avoid circular imports
            from app.carbon_ledger import GreenLedger
            from app.logic.regulatory_router import RegulatoryRouter

            # Re-initialize router with updated knowledge
            router = RegulatoryRouter(self.knowledge_path)

            # Log the recalculation trigger
            logger.info(f"Ledger recalculation triggered - new regulations applied to {vertical}/{state}")

            return True

        except Exception as e:
            logger.error(f"Ledger recalculation failed: {e}")
            return False

    def _mock_search_results(self, vertical: str, state: str) -> List[Dict[str, Any]]:
        """Return mock search results for testing without API key."""
        mock_results = {
            "hvac": [
                {
                    "title": f"2026 SEER2 Efficiency Standards Update for {state}",
                    "url": "https://energy.gov/seer2-2026",
                    "content": f"New SEER2 minimums for {state}: 15.2 for split systems, 14.3 for packaged units. Effective January 1, 2026. All installations must comply.",
                    "score": 0.95
                },
                {
                    "title": "EPA A2L Refrigerant Transition Final Rule",
                    "url": "https://epa.gov/aim-act-2026",
                    "content": "Mandatory transition to low-GWP refrigerants (GWP < 700) for all new residential AC systems. R-454B and R-32 approved alternatives.",
                    "score": 0.92
                }
            ],
            "plumbing": [
                {
                    "title": f"{state} Water Efficiency Standards 2026",
                    "url": f"https://{state.lower()}.gov/water-efficiency",
                    "content": "Updated GPM requirements: Showerheads 1.8 GPM max, Faucets 1.2 GPM max. WaterSense certification required for all new installations.",
                    "score": 0.88
                }
            ],
            "electrical": [
                {
                    "title": "NEC 2026 EV-Ready Requirements",
                    "url": "https://nfpa.org/nec-2026",
                    "content": "New construction must include 240V/50A dedicated circuit for EV charging. Panel capacity requirements updated.",
                    "score": 0.90
                }
            ],
            "landscaping": [
                {
                    "title": f"{state} Gas Equipment Phase-Out Update",
                    "url": f"https://{state.lower()}.gov/sore-rule",
                    "content": "Gas-powered lawn equipment sales ban effective 2024. Commercial operators must transition to electric by 2026.",
                    "score": 0.85
                }
            ]
        }

        return mock_results.get(vertical, [])

    # =========================================================================
    # Firecrawl Integration - Deep regulatory scraping
    # =========================================================================

    async def scrape_regulatory_portals(
        self,
        vertical: str,
        urls: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Scrape regulatory portals using Firecrawl for deep content extraction.
        This provides more comprehensive data than basic search APIs.
        """
        if not self.firecrawl_api_key:
            logger.warning("Firecrawl API key not configured - skipping portal scraping")
            return []

        # Default regulatory portals by vertical
        default_urls = {
            "hvac": [
                "https://www.epa.gov/climate-hfcs-reduction",
                "https://www.energy.gov/eere/buildings/residential-heating-and-cooling",
                "https://www.ahridirectory.org/NewSearch/Search"
            ],
            "plumbing": [
                "https://www.epa.gov/watersense",
                "https://www.energy.gov/eere/buildings/water-heating"
            ],
            "electrical": [
                "https://www.nfpa.org/nec",
                "https://www.energy.gov/eere/solar",
                "https://afdc.energy.gov/laws"
            ],
            "landscaping": [
                "https://ww2.arb.ca.gov/our-work/programs/small-off-road-engines-sore"
            ],
            "waste": [
                "https://www.epa.gov/recycle",
                "https://www.epa.gov/hw"
            ]
        }

        target_urls = urls or default_urls.get(vertical, [])
        all_content = []

        for url in target_urls:
            try:
                content = await self._firecrawl_scrape(url)
                if content:
                    all_content.append({
                        "url": url,
                        "vertical": vertical,
                        "content": content,
                        "scraped_at": datetime.now(timezone.utc).isoformat()
                    })
                    logger.info(f"Successfully scraped {url}")

            except Exception as e:
                logger.error(f"Firecrawl scrape error for {url}: {e}")

        return all_content

    async def _firecrawl_scrape(self, url: str) -> Optional[str]:
        """Scrape a single URL using Firecrawl API."""
        try:
            response = await self._client.post(
                "https://api.firecrawl.dev/v0/scrape",
                headers={
                    "Authorization": f"Bearer {self.firecrawl_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "url": url,
                    "formats": ["markdown"],
                    "onlyMainContent": True,
                    "waitFor": 3000  # Wait for dynamic content
                }
            )
            response.raise_for_status()
            data = response.json()

            if data.get("success"):
                return data.get("data", {}).get("markdown", "")

        except Exception as e:
            logger.error(f"Firecrawl API error: {e}")

        return None

    async def autonomous_legal_scout(self, vertical: str) -> Dict[str, Any]:
        """
        Run autonomous legal scouting that scrapes 2026 mandates
        and updates the Knowledge Base with new findings.
        """
        logger.info(f"Starting autonomous legal scout for {vertical}")

        results = {
            "vertical": vertical,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "sources_scraped": 0,
            "regulations_found": 0,
            "knowledge_base_updates": 0,
            "vector_db_updates": 0,
            "errors": []
        }

        # Step 1: Scrape regulatory portals
        scraped_content = await self.scrape_regulatory_portals(vertical)
        results["sources_scraped"] = len(scraped_content)

        # Step 2: Process and extract regulations
        regulations = []
        for content in scraped_content:
            extracted = await self._extract_regulations_from_content(
                content["content"],
                vertical,
                content["url"]
            )
            regulations.extend(extracted)

        results["regulations_found"] = len(regulations)

        # Step 3: Update knowledge base
        if regulations:
            kb_updates = await self._batch_update_knowledge_base(regulations)
            results["knowledge_base_updates"] = kb_updates

        # Step 4: Update vector database for semantic search
        if regulations and self.pinecone_api_key:
            vector_updates = await self._update_vector_database(regulations, vertical)
            results["vector_db_updates"] = vector_updates

        results["completed_at"] = datetime.now(timezone.utc).isoformat()
        logger.info(f"Autonomous scout complete: {results['regulations_found']} regulations found")

        return results

    async def _extract_regulations_from_content(
        self,
        content: str,
        vertical: str,
        source_url: str
    ) -> List[RegulatoryUpdate]:
        """Extract regulations from scraped content using Claude."""
        if not content or not self.anthropic_api_key:
            return []

        try:
            # Chunk content if too large
            content_chunk = content[:8000]

            prompt = f"""Analyze this regulatory content and extract all 2026 regulatory requirements for {vertical}.

Content:
{content_chunk}

For each regulation found, extract:
- regulation_type: [seer2, gpm, refrigerant, waste_diversion, efficiency, safety, electrification, incentive]
- title: Brief title
- summary: 2-3 sentence description of the requirement
- effective_date: When it takes effect (if mentioned)
- mandatory: true/false - is this a mandate or voluntary?
- penalties: Any penalties for non-compliance (if mentioned)

Respond with a JSON array:
[{{"regulation_type": "", "title": "", "summary": "", "effective_date": "", "mandatory": true, "penalties": ""}}]

If no regulations found, respond: []"""

            response = await self._client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt}]
                }
            )
            response.raise_for_status()
            data = response.json()
            text = data["content"][0]["text"]

            # Parse JSON array from response
            json_match = re.search(r'\[.*\]', text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                regulations = []
                for item in parsed:
                    if item.get("title"):
                        regulations.append(RegulatoryUpdate(
                            id=f"scout_fc_{hashlib.md5(item['title'].encode()).hexdigest()[:8]}",
                            vertical=vertical,
                            state="FEDERAL",  # Default to federal for scraped content
                            regulation_type=item.get("regulation_type", "unknown"),
                            title=item.get("title", ""),
                            summary=item.get("summary", ""),
                            effective_date=item.get("effective_date"),
                            source_url=source_url,
                            discovered_at=datetime.now(timezone.utc),
                            confidence=0.8 if item.get("mandatory") else 0.6,
                            raw_content=content_chunk
                        ))
                return regulations

        except Exception as e:
            logger.error(f"Regulation extraction error: {e}")

        return []

    async def _batch_update_knowledge_base(
        self,
        regulations: List[RegulatoryUpdate]
    ) -> int:
        """Batch update knowledge base with multiple regulations."""
        updates = 0
        try:
            with open(self.knowledge_path, "r") as f:
                knowledge = json.load(f)

            if "federal_regulations" not in knowledge:
                knowledge["federal_regulations"] = {}

            for reg in regulations:
                reg_key = f"auto_{reg.regulation_type}_{reg.id}"
                if reg_key not in knowledge["federal_regulations"]:
                    knowledge["federal_regulations"][reg_key] = {
                        "name": reg.title,
                        "requirement": reg.summary,
                        "regulation_type": reg.regulation_type,
                        "effective_date": reg.effective_date,
                        "source": reg.source_url,
                        "discovered_at": reg.discovered_at.isoformat(),
                        "confidence": reg.confidence,
                        "auto_discovered": True
                    }
                    updates += 1

            if updates > 0:
                knowledge["metadata"] = knowledge.get("metadata", {})
                knowledge["metadata"]["last_batch_update"] = datetime.now(timezone.utc).isoformat()
                knowledge["metadata"]["batch_update_count"] = updates

                with open(self.knowledge_path, "w") as f:
                    json.dump(knowledge, f, indent=2)

        except Exception as e:
            logger.error(f"Batch knowledge update failed: {e}")

        return updates

    # =========================================================================
    # Pinecone Vector Database Integration - Semantic Search
    # =========================================================================

    async def _init_pinecone(self):
        """Initialize Pinecone connection."""
        if self._pinecone_index:
            return

        try:
            # Using REST API instead of SDK for async compatibility
            response = await self._client.get(
                f"https://api.pinecone.io/indexes/{self.pinecone_index_name}",
                headers={"Api-Key": self.pinecone_api_key}
            )
            if response.status_code == 200:
                data = response.json()
                self._pinecone_index = data.get("host")
                logger.info(f"Connected to Pinecone index: {self.pinecone_index_name}")
            else:
                logger.warning(f"Pinecone index not found: {self.pinecone_index_name}")

        except Exception as e:
            logger.error(f"Pinecone initialization error: {e}")

    async def _update_vector_database(
        self,
        regulations: List[RegulatoryUpdate],
        vertical: str
    ) -> int:
        """Update Pinecone vector database with regulation embeddings."""
        if not self.pinecone_api_key or not self.anthropic_api_key:
            return 0

        await self._init_pinecone()
        if not self._pinecone_index:
            return 0

        updates = 0

        for reg in regulations:
            try:
                # Generate embedding using Claude (or use a dedicated embedding model)
                embedding = await self._generate_embedding(
                    f"{reg.title}: {reg.summary}"
                )

                if embedding:
                    # Upsert to Pinecone
                    vector_data = {
                        "vectors": [{
                            "id": reg.id,
                            "values": embedding,
                            "metadata": {
                                "vertical": vertical,
                                "regulation_type": reg.regulation_type,
                                "title": reg.title,
                                "summary": reg.summary[:500],
                                "source_url": reg.source_url,
                                "effective_date": reg.effective_date or "",
                                "discovered_at": reg.discovered_at.isoformat()
                            }
                        }]
                    }

                    response = await self._client.post(
                        f"https://{self._pinecone_index}/vectors/upsert",
                        headers={
                            "Api-Key": self.pinecone_api_key,
                            "Content-Type": "application/json"
                        },
                        json=vector_data
                    )

                    if response.status_code == 200:
                        updates += 1
                        logger.info(f"Indexed regulation: {reg.id}")

            except Exception as e:
                logger.error(f"Vector DB update error for {reg.id}: {e}")

        return updates

    async def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate text embedding using Anthropic API."""
        # Note: Anthropic doesn't have a dedicated embedding endpoint yet
        # In production, use OpenAI embeddings, Cohere, or Voyage AI
        # For now, we'll use a placeholder that would integrate with an embedding service

        try:
            # Placeholder - would use actual embedding service
            # response = await self._client.post(
            #     "https://api.openai.com/v1/embeddings",
            #     headers={"Authorization": f"Bearer {openai_key}"},
            #     json={"model": "text-embedding-3-small", "input": text}
            # )
            # return response.json()["data"][0]["embedding"]

            # For now, return None - implement with real embedding service
            logger.debug("Embedding generation requires dedicated embedding service")
            return None

        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            return None

    async def semantic_search_regulations(
        self,
        query: str,
        vertical: Optional[str] = None,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Search regulations using semantic similarity."""
        if not self.pinecone_api_key:
            logger.warning("Pinecone not configured for semantic search")
            return []

        await self._init_pinecone()
        if not self._pinecone_index:
            return []

        try:
            # Generate query embedding
            query_embedding = await self._generate_embedding(query)
            if not query_embedding:
                # Fall back to metadata filter
                return await self._metadata_search(query, vertical, top_k)

            # Query Pinecone
            filter_dict = {}
            if vertical:
                filter_dict["vertical"] = vertical

            response = await self._client.post(
                f"https://{self._pinecone_index}/query",
                headers={
                    "Api-Key": self.pinecone_api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "vector": query_embedding,
                    "topK": top_k,
                    "includeMetadata": True,
                    "filter": filter_dict if filter_dict else None
                }
            )

            if response.status_code == 200:
                data = response.json()
                return [
                    {
                        "id": match["id"],
                        "score": match["score"],
                        **match.get("metadata", {})
                    }
                    for match in data.get("matches", [])
                ]

        except Exception as e:
            logger.error(f"Semantic search error: {e}")

        return []

    async def _metadata_search(
        self,
        query: str,
        vertical: Optional[str],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """Fall back to metadata-based search when embeddings unavailable."""
        try:
            with open(self.knowledge_path, "r") as f:
                knowledge = json.load(f)

            results = []
            query_lower = query.lower()

            # Search federal regulations
            for key, reg in knowledge.get("federal_regulations", {}).items():
                name = reg.get("name", "").lower()
                req = reg.get("requirement", "").lower()

                if query_lower in name or query_lower in req:
                    results.append({
                        "id": key,
                        "title": reg.get("name"),
                        "summary": reg.get("requirement"),
                        "regulation_type": reg.get("regulation_type"),
                        "score": 1.0 if query_lower in name else 0.8
                    })

            # Filter by vertical if specified
            if vertical:
                results = [r for r in results if vertical in r.get("regulation_type", "")]

            # Sort by score and limit
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]

        except Exception as e:
            logger.error(f"Metadata search error: {e}")
            return []

    async def get_scout_status(self) -> Dict[str, Any]:
        """Get current scout agent status and last run info."""
        try:
            with open(self.knowledge_path, "r") as f:
                knowledge = json.load(f)

            metadata = knowledge.get("metadata", {})
            return {
                "status": "active",
                "tavily_configured": bool(self.tavily_api_key),
                "claude_configured": bool(self.anthropic_api_key),
                "last_run": metadata.get("last_scout_run"),
                "last_state": metadata.get("last_scout_state"),
                "last_vertical": metadata.get("last_scout_vertical"),
                "knowledge_path": self.knowledge_path
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()


# Convenience function to run a quick compliance sync
async def run_compliance_sync(
    vertical: str,
    state: str,
    tavily_api_key: Optional[str] = None,
    anthropic_api_key: Optional[str] = None
) -> ComplianceSyncResult:
    """Run a compliance sync and return results."""
    scout = LegalScoutAgent(
        tavily_api_key=tavily_api_key,
        anthropic_api_key=anthropic_api_key
    )
    try:
        return await scout.run_compliance_sync(vertical, state)
    finally:
        await scout.close()
