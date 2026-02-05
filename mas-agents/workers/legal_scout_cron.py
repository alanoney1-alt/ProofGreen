"""
ProofGreen MAS - Legal Scout Cron Worker
Scheduled task to refresh regulatory knowledge from EPA and state sources.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import httpx
import json

from config.settings import settings


class LegalScoutCron:
    """
    Scheduled Legal Scout worker.
    Runs weekly to refresh Vector DB with new regulatory changes.
    """

    # Regulatory sources to monitor
    REGULATORY_SOURCES = {
        "epa_aim_act": {
            "url": "https://www.epa.gov/climate-hfcs-reduction",
            "category": "refrigerant",
            "priority": "high"
        },
        "epa_energy_star": {
            "url": "https://www.energystar.gov/products/heating_cooling",
            "category": "efficiency",
            "priority": "medium"
        },
        "doe_efficiency": {
            "url": "https://www.energy.gov/eere/buildings/appliance-and-equipment-standards-program",
            "category": "efficiency",
            "priority": "high"
        },
        "rewiring_america": {
            "url": "https://www.rewiringamerica.org/policy",
            "category": "incentives",
            "priority": "medium"
        }
    }

    # State-specific regulatory portals
    STATE_SOURCES = {
        "CA": {
            "carb": "https://ww2.arb.ca.gov/our-work/programs/refrigerant-management-program",
            "title_24": "https://www.energy.ca.gov/programs-and-topics/programs/building-energy-efficiency-standards"
        },
        "WA": {
            "commerce": "https://www.commerce.wa.gov/growing-the-economy/energy/appliance-efficiency-standards/"
        },
        "NY": {
            "nyserda": "https://www.nyserda.ny.gov/All-Programs"
        }
    }

    def __init__(
        self,
        db_connection=None,
        pinecone_api_key: Optional[str] = None,
        tavily_api_key: Optional[str] = None,
        firecrawl_api_key: Optional[str] = None
    ):
        """
        Initialize Legal Scout Cron.

        Args:
            db_connection: PostgreSQL connection
            pinecone_api_key: Pinecone API key
            tavily_api_key: Tavily search API key
            firecrawl_api_key: Firecrawl scraping API key
        """
        self.db = db_connection
        self.pinecone_key = pinecone_api_key or settings.PINECONE_API_KEY
        self.tavily_key = tavily_api_key or settings.TAVILY_API_KEY
        self.firecrawl_key = firecrawl_api_key or settings.FIRECRAWL_API_KEY

        self.pinecone_host = f"https://{settings.PINECONE_INDEX_NAME}-{settings.PINECONE_ENVIRONMENT}.svc.pinecone.io"

        self.scheduler = AsyncIOScheduler()
        self._running = False

    def start(self):
        """Start the scheduled worker."""
        # Schedule weekly run (Sunday at midnight)
        self.scheduler.add_job(
            self.scout_for_updates,
            CronTrigger(day_of_week='sun', hour=0, minute=0),
            id='legal_scout_weekly',
            replace_existing=True
        )

        # Also run daily check for critical updates
        self.scheduler.add_job(
            self.check_critical_updates,
            CronTrigger(hour=6, minute=0),  # 6 AM daily
            id='legal_scout_daily_critical',
            replace_existing=True
        )

        self.scheduler.start()
        self._running = True
        print("[LegalScoutCron] Scheduled worker started")
        print("  - Weekly full scan: Sundays at midnight")
        print("  - Daily critical check: 6 AM")

    def stop(self):
        """Stop the scheduled worker."""
        self.scheduler.shutdown()
        self._running = False
        print("[LegalScoutCron] Scheduled worker stopped")

    async def scout_for_updates(self) -> Dict:
        """
        Main scout function - runs weekly.
        Scans all regulatory sources and updates Vector DB.
        """
        print(f"[LegalScoutCron] Starting weekly regulatory scan at {datetime.utcnow()}")

        results = {
            "scan_time": datetime.utcnow().isoformat(),
            "sources_checked": 0,
            "updates_found": [],
            "errors": []
        }

        # 1. Scan federal sources
        for source_id, source_info in self.REGULATORY_SOURCES.items():
            try:
                updates = await self._scan_source(source_id, source_info)
                if updates:
                    results["updates_found"].extend(updates)
                results["sources_checked"] += 1
            except Exception as e:
                results["errors"].append({
                    "source": source_id,
                    "error": str(e)
                })

        # 2. Scan state sources
        verticals = settings.LEGAL_SCOUT_VERTICALS.split(",")
        for state, sources in self.STATE_SOURCES.items():
            for source_id, url in sources.items():
                try:
                    updates = await self._scan_source(
                        f"{state}_{source_id}",
                        {"url": url, "category": "state", "state": state}
                    )
                    if updates:
                        results["updates_found"].extend(updates)
                    results["sources_checked"] += 1
                except Exception as e:
                    results["errors"].append({
                        "source": f"{state}_{source_id}",
                        "error": str(e)
                    })

        # 3. Use Tavily to search for recent regulatory news
        if self.tavily_key:
            try:
                news_updates = await self._search_regulatory_news()
                results["updates_found"].extend(news_updates)
            except Exception as e:
                results["errors"].append({
                    "source": "tavily_news",
                    "error": str(e)
                })

        # 4. Update Vector DB with new regulations
        if results["updates_found"]:
            await self._update_vector_db(results["updates_found"])

        # 5. Log results
        await self._log_scout_run(results)

        print(f"[LegalScoutCron] Scan complete. Found {len(results['updates_found'])} updates.")
        return results

    async def check_critical_updates(self) -> Dict:
        """
        Daily check for critical regulatory updates.
        Focuses on high-priority changes that need immediate attention.
        """
        print(f"[LegalScoutCron] Checking for critical updates at {datetime.utcnow()}")

        # Search for critical keywords
        critical_keywords = [
            "EPA refrigerant ban",
            "HVAC efficiency mandate 2026",
            "IRA tax credit change",
            "refrigerant phase out deadline",
            "building code update 2026"
        ]

        updates = []

        if self.tavily_key:
            for keyword in critical_keywords:
                try:
                    search_results = await self._tavily_search(
                        keyword,
                        days_back=1  # Last 24 hours only
                    )
                    for result in search_results:
                        result["critical"] = True
                        result["keyword"] = keyword
                        updates.append(result)
                except Exception as e:
                    print(f"[LegalScoutCron] Error searching '{keyword}': {e}")

        if updates:
            print(f"[LegalScoutCron] Found {len(updates)} critical updates!")
            # Send alerts
            await self._send_critical_alerts(updates)

        return {
            "check_time": datetime.utcnow().isoformat(),
            "critical_updates": updates
        }

    async def _scan_source(
        self,
        source_id: str,
        source_info: Dict
    ) -> List[Dict]:
        """Scan a single regulatory source for updates."""
        url = source_info["url"]
        updates = []

        # Use Firecrawl for deep scraping if available
        if self.firecrawl_key:
            content = await self._firecrawl_scrape(url)
        else:
            content = await self._simple_fetch(url)

        if not content:
            return []

        # Check for updates since last scan
        last_scan = await self._get_last_scan_time(source_id)

        # Parse content for regulatory changes
        changes = self._extract_regulatory_changes(content, source_info)

        for change in changes:
            # Skip if we've already processed this
            if await self._is_already_indexed(change.get("id")):
                continue

            updates.append({
                "id": change.get("id") or f"{source_id}_{hash(change.get('title', ''))}",
                "source": source_id,
                "url": url,
                "title": change.get("title"),
                "summary": change.get("summary"),
                "category": source_info.get("category"),
                "state": source_info.get("state"),
                "effective_date": change.get("effective_date"),
                "priority": source_info.get("priority", "medium"),
                "discovered_at": datetime.utcnow().isoformat()
            })

        return updates

    async def _firecrawl_scrape(self, url: str) -> Optional[str]:
        """Use Firecrawl to scrape a URL."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.firecrawl.dev/v0/scrape",
                    headers={
                        "Authorization": f"Bearer {self.firecrawl_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "url": url,
                        "pageOptions": {
                            "onlyMainContent": True
                        }
                    },
                    timeout=60.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", {}).get("markdown", "")

        except Exception as e:
            print(f"[LegalScoutCron] Firecrawl error: {e}")

        return None

    async def _simple_fetch(self, url: str) -> Optional[str]:
        """Simple HTTP fetch fallback."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                if response.status_code == 200:
                    return response.text
        except Exception:
            pass
        return None

    async def _tavily_search(
        self,
        query: str,
        days_back: int = 7
    ) -> List[Dict]:
        """Search for regulatory news using Tavily."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.tavily.com/search",
                    headers={"Content-Type": "application/json"},
                    json={
                        "api_key": self.tavily_key,
                        "query": query,
                        "search_depth": "advanced",
                        "include_domains": [
                            "epa.gov", "energy.gov", "energystar.gov",
                            "rewiringamerica.org", "aceee.org"
                        ],
                        "max_results": 10
                    },
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    return [
                        {
                            "title": r.get("title"),
                            "url": r.get("url"),
                            "summary": r.get("content", "")[:500],
                            "source": "tavily_search"
                        }
                        for r in data.get("results", [])
                    ]

        except Exception as e:
            print(f"[LegalScoutCron] Tavily search error: {e}")

        return []

    async def _search_regulatory_news(self) -> List[Dict]:
        """Search for recent regulatory news."""
        queries = [
            "EPA HVAC regulations 2026",
            "IRA heat pump rebate update",
            "refrigerant phase out A2L",
            "SEER2 efficiency standard update",
            "home energy rebate program"
        ]

        all_updates = []
        for query in queries:
            results = await self._tavily_search(query)
            for result in results:
                result["category"] = "news"
                result["discovered_at"] = datetime.utcnow().isoformat()
                all_updates.append(result)

        return all_updates

    def _extract_regulatory_changes(
        self,
        content: str,
        source_info: Dict
    ) -> List[Dict]:
        """Extract regulatory changes from content."""
        # In production, use Claude to extract structured data
        # For now, simple keyword detection
        changes = []

        keywords = [
            "effective date", "compliance deadline", "new requirement",
            "phase out", "minimum efficiency", "gwp limit",
            "tax credit", "rebate program", "updated standard"
        ]

        lines = content.split('\n')
        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(kw in line_lower for kw in keywords):
                # Found potential change
                context = '\n'.join(lines[max(0, i-2):i+3])
                changes.append({
                    "title": line[:100] if len(line) > 100 else line,
                    "summary": context[:500],
                    "source_category": source_info.get("category")
                })

        return changes

    async def _update_vector_db(self, updates: List[Dict]):
        """Update Pinecone vector database with new regulations."""
        if not self.pinecone_key:
            return

        try:
            # Generate embeddings (simplified - use actual embedding model in production)
            vectors = []
            for update in updates:
                text = f"{update.get('title', '')} {update.get('summary', '')}"
                # Simple hash-based embedding for demo
                embedding = self._simple_embedding(text)

                vectors.append({
                    "id": update.get("id", str(hash(text))),
                    "values": embedding,
                    "metadata": {
                        "title": update.get("title"),
                        "summary": update.get("summary", "")[:1000],
                        "category": update.get("category"),
                        "state": update.get("state"),
                        "source": update.get("source"),
                        "url": update.get("url"),
                        "priority": update.get("priority"),
                        "discovered_at": update.get("discovered_at")
                    }
                })

            # Upsert to Pinecone
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.pinecone_host}/vectors/upsert",
                    headers={
                        "Api-Key": self.pinecone_key,
                        "Content-Type": "application/json"
                    },
                    json={"vectors": vectors},
                    timeout=30.0
                )

                if response.status_code == 200:
                    print(f"[LegalScoutCron] Indexed {len(vectors)} updates to Pinecone")

        except Exception as e:
            print(f"[LegalScoutCron] Vector DB update error: {e}")

    def _simple_embedding(self, text: str) -> List[float]:
        """Generate simple embedding (placeholder for actual model)."""
        import hashlib
        hash_bytes = hashlib.sha256(text.encode()).digest()
        embedding = [float(b) / 255.0 for b in hash_bytes]
        while len(embedding) < 1536:
            embedding.extend(embedding[:min(len(embedding), 1536 - len(embedding))])
        return embedding[:1536]

    async def _get_last_scan_time(self, source_id: str) -> Optional[datetime]:
        """Get last scan time for a source."""
        if self.db:
            row = await self.db.fetchrow(
                "SELECT last_scan FROM regulatory_scan_log WHERE source_id = $1",
                source_id
            )
            if row:
                return row["last_scan"]
        return None

    async def _is_already_indexed(self, regulation_id: str) -> bool:
        """Check if a regulation is already indexed."""
        if self.db:
            count = await self.db.fetchval(
                "SELECT COUNT(*) FROM indexed_regulations WHERE id = $1",
                regulation_id
            )
            return count > 0
        return False

    async def _log_scout_run(self, results: Dict):
        """Log scout run results."""
        if self.db:
            await self.db.execute("""
                INSERT INTO regulatory_scan_log (
                    scan_time, sources_checked, updates_found, errors
                ) VALUES ($1, $2, $3, $4)
            """,
                results["scan_time"],
                results["sources_checked"],
                len(results["updates_found"]),
                json.dumps(results["errors"])
            )

    async def _send_critical_alerts(self, updates: List[Dict]):
        """Send alerts for critical regulatory updates."""
        # In production, integrate with notification system
        print(f"[LegalScoutCron] CRITICAL ALERT: {len(updates)} critical regulatory updates detected!")
        for update in updates:
            print(f"  - {update.get('title', 'Unknown')}")


# Database schema for scout tracking
SCOUT_SCHEMA = """
CREATE TABLE IF NOT EXISTS regulatory_scan_log (
    id SERIAL PRIMARY KEY,
    scan_time TIMESTAMP NOT NULL,
    sources_checked INTEGER NOT NULL,
    updates_found INTEGER DEFAULT 0,
    errors JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS indexed_regulations (
    id VARCHAR(255) PRIMARY KEY,
    source VARCHAR(100) NOT NULL,
    title TEXT,
    summary TEXT,
    category VARCHAR(50),
    state VARCHAR(10),
    effective_date DATE,
    priority VARCHAR(20),
    indexed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_regulations_category ON indexed_regulations(category);
CREATE INDEX IF NOT EXISTS idx_regulations_state ON indexed_regulations(state);
CREATE INDEX IF NOT EXISTS idx_regulations_effective ON indexed_regulations(effective_date);
"""


async def create_legal_scout_cron(db_connection=None) -> LegalScoutCron:
    """Create and initialize Legal Scout Cron."""
    scout = LegalScoutCron(db_connection=db_connection)

    if db_connection:
        await db_connection.execute(SCOUT_SCHEMA)

    return scout
