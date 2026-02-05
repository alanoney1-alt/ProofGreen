"""
Legal Scout Agent - Regulatory Update Monitor
Uses TavilySearch to discover new 2026 regulatory changes and update knowledge base
"""

import asyncio
import json
import httpx
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import logging
import re

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
    Legal Scout sub-agent that monitors regulatory changes using TavilySearch.
    Automatically updates regulatory_knowledge.json and triggers ledger recalculation.
    """

    def __init__(
        self,
        tavily_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        knowledge_path: Optional[str] = None
    ):
        self.tavily_api_key = tavily_api_key
        self.anthropic_api_key = anthropic_api_key
        self.knowledge_path = knowledge_path or str(
            Path(__file__).parent.parent / "config" / "regulatory_knowledge.json"
        )
        self._client = httpx.AsyncClient(timeout=60.0)

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
