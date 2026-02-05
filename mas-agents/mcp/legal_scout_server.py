"""
ProofGreen MCP Legal Scout Server
Model Context Protocol server for autonomous regulatory monitoring.

Monitors EPA.gov and Energy.gov for 2026 A2L refrigerant and SEER2 updates.
Auto-updates regulatory_knowledge.json when thresholds are crossed.
Flags active jobs that no longer comply with updated regulations.
"""

import asyncio
import json
import logging
import os
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import httpx

# MCP Server implementation
# In production, use: from mcp.server import Server
# For now, we implement a FastMCP-compatible server

logger = logging.getLogger(__name__)


@dataclass
class RegulatoryAlert:
    """Alert for regulatory threshold crossing."""
    id: str
    regulation_type: str  # seer2, refrigerant_gwp, etc.
    previous_value: Any
    new_value: Any
    source_url: str
    effective_date: Optional[str]
    severity: str  # info, warning, critical
    affected_jobs: List[str]
    discovered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ComplianceFlag:
    """Flag for a job that no longer complies."""
    job_id: str
    company_id: str
    regulation_id: str
    reason: str
    previous_status: str
    new_status: str
    flagged_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class MCPLegalScoutServer:
    """
    MCP Server for Legal Scout agent.

    Provides tools for:
    - Monitoring regulatory websites (EPA, Energy.gov)
    - Checking compliance thresholds
    - Auto-updating knowledge base
    - Flagging non-compliant jobs
    """

    def __init__(
        self,
        anthropic_api_key: Optional[str] = None,
        firecrawl_api_key: Optional[str] = None,
        knowledge_path: Optional[str] = None,
        db_connection: Optional[Any] = None
    ):
        self.anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        self.firecrawl_api_key = firecrawl_api_key or os.getenv("FIRECRAWL_API_KEY")
        self.knowledge_path = knowledge_path or str(
            Path(__file__).parent.parent / "config" / "regulatory_knowledge.json"
        )
        self._db = db_connection
        self._client = httpx.AsyncClient(timeout=60.0)

        # Monitoring targets
        self.monitor_urls = {
            "epa_aim_act": {
                "url": "https://www.epa.gov/climate-hfcs-reduction/aim-act",
                "keywords": ["A2L", "refrigerant", "GWP", "R-454B", "R-32", "phasedown"],
                "vertical": "hvac"
            },
            "epa_snap": {
                "url": "https://www.epa.gov/snap",
                "keywords": ["refrigerant", "substitute", "acceptable", "unacceptable"],
                "vertical": "hvac"
            },
            "doe_seer2": {
                "url": "https://www.energy.gov/eere/buildings/residential-heating-and-cooling",
                "keywords": ["SEER2", "efficiency", "minimum", "standard", "2023", "2025"],
                "vertical": "hvac"
            },
            "doe_water_heater": {
                "url": "https://www.energy.gov/eere/buildings/water-heating",
                "keywords": ["UEF", "water heater", "efficiency", "standard"],
                "vertical": "plumbing"
            },
            "energy_star": {
                "url": "https://www.energystar.gov/products/heating_cooling",
                "keywords": ["Energy Star", "specification", "2026", "criteria"],
                "vertical": "hvac"
            }
        }

        # Compliance thresholds (2026 values)
        self.thresholds = {
            "hvac": {
                "seer2_split_north": 14.3,
                "seer2_split_south": 15.2,
                "seer2_packaged_north": 13.4,
                "seer2_packaged_south": 14.3,
                "hspf2_min": 7.5,
                "gwp_max": 700,
                "a2l_required_date": "2025-01-01"
            },
            "plumbing": {
                "showerhead_gpm_max": 1.8,
                "faucet_gpm_max": 1.2,
                "toilet_gpf_max": 1.28,
                "water_heater_uef_min": 0.87
            }
        }

        # Alert history
        self._alerts: List[RegulatoryAlert] = []
        self._compliance_flags: List[ComplianceFlag] = []

    # =========================================================================
    # MCP Tool: monitor_regulatory_updates
    # =========================================================================

    async def monitor_regulatory_updates(
        self,
        sources: Optional[List[str]] = None,
        vertical: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        MCP Tool: Monitor EPA and Energy.gov for regulatory updates.

        Args:
            sources: Specific sources to monitor (default: all)
            vertical: Filter by vertical (hvac, plumbing, etc.)

        Returns:
            Dictionary with discovered updates and alerts
        """
        logger.info(f"MCP Legal Scout: Monitoring regulatory updates")

        results = {
            "monitored_at": datetime.now(timezone.utc).isoformat(),
            "sources_checked": [],
            "updates_found": [],
            "alerts_generated": [],
            "knowledge_updates": 0
        }

        # Filter sources
        target_sources = self.monitor_urls
        if sources:
            target_sources = {k: v for k, v in target_sources.items() if k in sources}
        if vertical:
            target_sources = {k: v for k, v in target_sources.items() if v.get("vertical") == vertical}

        for source_id, source_config in target_sources.items():
            try:
                # Fetch and analyze content
                content = await self._fetch_regulatory_content(source_config["url"])

                if content:
                    results["sources_checked"].append(source_id)

                    # Analyze for threshold changes
                    updates = await self._analyze_for_updates(
                        content,
                        source_config["keywords"],
                        source_config["vertical"],
                        source_config["url"]
                    )

                    if updates:
                        results["updates_found"].extend(updates)

                        # Check for threshold crossings
                        alerts = self._check_threshold_crossings(updates, source_config["vertical"])
                        results["alerts_generated"].extend(alerts)

                        # Auto-update knowledge base
                        if alerts:
                            kb_updates = await self._auto_update_knowledge_base(alerts)
                            results["knowledge_updates"] += kb_updates

            except Exception as e:
                logger.error(f"Error monitoring {source_id}: {e}")

        return results

    # =========================================================================
    # MCP Tool: check_job_compliance
    # =========================================================================

    async def check_job_compliance(
        self,
        job_id: str,
        job_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        MCP Tool: Check if a job still complies with current regulations.

        Args:
            job_id: The job identifier
            job_data: Job details including equipment, state, vertical

        Returns:
            Compliance status and any violations
        """
        logger.info(f"MCP Legal Scout: Checking compliance for job {job_id}")

        result = {
            "job_id": job_id,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "is_compliant": True,
            "violations": [],
            "warnings": [],
            "regulations_checked": []
        }

        vertical = job_data.get("vertical", "hvac")
        state = job_data.get("state", "CA")
        equipment = job_data.get("equipment", {})

        # Load current thresholds
        thresholds = self.thresholds.get(vertical, {})

        # HVAC compliance checks
        if vertical == "hvac":
            result["regulations_checked"].extend([
                "DOE SEER2 2023",
                "EPA AIM Act 2024",
                "2026 A2L Refrigerant Mandate"
            ])

            # SEER2 check
            seer2 = equipment.get("seer2_rating")
            if seer2:
                # Southern states have higher requirements
                southern_states = ["FL", "TX", "AZ", "NV", "CA", "LA", "MS", "AL", "GA", "SC", "NC"]
                min_seer2 = thresholds.get(
                    "seer2_split_south" if state in southern_states else "seer2_split_north",
                    14.3
                )

                if seer2 < min_seer2:
                    result["is_compliant"] = False
                    result["violations"].append({
                        "code": "SEER2_BELOW_MIN",
                        "regulation": "DOE SEER2 2023",
                        "current_value": seer2,
                        "required_value": min_seer2,
                        "message": f"SEER2 {seer2} below minimum {min_seer2} for {state}"
                    })

            # Refrigerant GWP check
            refrigerant = equipment.get("refrigerant_type")
            if refrigerant:
                gwp_values = {
                    "R-410A": 2088,
                    "R-22": 1810,
                    "R-454B": 466,
                    "R-32": 675
                }
                gwp = gwp_values.get(refrigerant, 0)
                max_gwp = thresholds.get("gwp_max", 700)

                if gwp > max_gwp:
                    result["is_compliant"] = False
                    result["violations"].append({
                        "code": "REFRIGERANT_GWP_EXCEEDED",
                        "regulation": "EPA AIM Act 2024",
                        "current_value": gwp,
                        "required_value": f"<= {max_gwp}",
                        "message": f"Refrigerant {refrigerant} GWP {gwp} exceeds limit {max_gwp}"
                    })

        # Plumbing compliance checks
        elif vertical == "plumbing":
            result["regulations_checked"].extend([
                "EPA WaterSense",
                "DOE Water Heater Efficiency"
            ])

            # GPM check
            gpm = equipment.get("gpm")
            fixture_type = equipment.get("fixture_type", "showerhead")
            if gpm:
                max_gpm = thresholds.get(f"{fixture_type}_gpm_max", 2.0)
                if gpm > max_gpm:
                    result["is_compliant"] = False
                    result["violations"].append({
                        "code": "GPM_EXCEEDED",
                        "regulation": "EPA WaterSense",
                        "current_value": gpm,
                        "required_value": max_gpm,
                        "message": f"Flow rate {gpm} GPM exceeds {max_gpm} GPM limit"
                    })

        # Flag job if non-compliant
        if not result["is_compliant"]:
            await self._flag_job(job_id, job_data, result["violations"])

        return result

    # =========================================================================
    # MCP Tool: flag_affected_jobs
    # =========================================================================

    async def flag_affected_jobs(
        self,
        regulation_id: str,
        new_threshold: Any,
        vertical: str
    ) -> Dict[str, Any]:
        """
        MCP Tool: Flag all active jobs affected by a regulation change.

        Args:
            regulation_id: The changed regulation
            new_threshold: The new threshold value
            vertical: The affected vertical

        Returns:
            List of flagged jobs
        """
        logger.info(f"MCP Legal Scout: Flagging jobs affected by {regulation_id}")

        result = {
            "regulation_id": regulation_id,
            "new_threshold": new_threshold,
            "jobs_checked": 0,
            "jobs_flagged": [],
            "flagged_at": datetime.now(timezone.utc).isoformat()
        }

        # In production, this would query the database for active jobs
        # For now, we demonstrate the logic

        # Simulate fetching active jobs
        active_jobs = await self._get_active_jobs(vertical)
        result["jobs_checked"] = len(active_jobs)

        for job in active_jobs:
            compliance = await self.check_job_compliance(job["id"], job)

            if not compliance["is_compliant"]:
                flag = ComplianceFlag(
                    job_id=job["id"],
                    company_id=job.get("company_id", ""),
                    regulation_id=regulation_id,
                    reason=f"Regulation change: {regulation_id}",
                    previous_status="compliant",
                    new_status="non_compliant"
                )
                self._compliance_flags.append(flag)
                result["jobs_flagged"].append({
                    "job_id": job["id"],
                    "violations": compliance["violations"],
                    "flagged_at": flag.flagged_at.isoformat()
                })

        return result

    # =========================================================================
    # MCP Tool: get_current_thresholds
    # =========================================================================

    def get_current_thresholds(self, vertical: Optional[str] = None) -> Dict[str, Any]:
        """
        MCP Tool: Get current regulatory thresholds.

        Args:
            vertical: Optional vertical filter

        Returns:
            Current thresholds by vertical
        """
        if vertical:
            return {vertical: self.thresholds.get(vertical, {})}
        return self.thresholds

    # =========================================================================
    # MCP Tool: schedule_monitoring
    # =========================================================================

    async def schedule_monitoring(
        self,
        frequency: str = "weekly",
        sources: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        MCP Tool: Schedule recurring regulatory monitoring.

        Args:
            frequency: Monitoring frequency (daily, weekly, monthly)
            sources: Specific sources to monitor

        Returns:
            Schedule confirmation
        """
        frequencies = {
            "daily": timedelta(days=1),
            "weekly": timedelta(weeks=1),
            "monthly": timedelta(days=30)
        }

        interval = frequencies.get(frequency, timedelta(weeks=1))
        next_run = datetime.now(timezone.utc) + interval

        schedule = {
            "schedule_id": hashlib.md5(f"{frequency}_{sources}".encode()).hexdigest()[:8],
            "frequency": frequency,
            "sources": sources or list(self.monitor_urls.keys()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "next_run": next_run.isoformat(),
            "status": "active"
        }

        # In production, this would register with a job scheduler (Celery, APScheduler)
        logger.info(f"Scheduled monitoring: {schedule}")

        return schedule

    # =========================================================================
    # Internal Methods
    # =========================================================================

    async def _fetch_regulatory_content(self, url: str) -> Optional[str]:
        """Fetch content from regulatory website."""

        # Try Firecrawl first for better extraction
        if self.firecrawl_api_key:
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
                        "onlyMainContent": True
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        return data.get("data", {}).get("markdown", "")
            except Exception as e:
                logger.warning(f"Firecrawl failed, falling back: {e}")

        # Fall back to direct fetch
        try:
            response = await self._client.get(url, follow_redirects=True)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")

        return None

    async def _analyze_for_updates(
        self,
        content: str,
        keywords: List[str],
        vertical: str,
        source_url: str
    ) -> List[Dict[str, Any]]:
        """Analyze content for regulatory updates using Claude."""
        if not self.anthropic_api_key or not content:
            return []

        updates = []

        try:
            # Check if content contains relevant keywords
            content_lower = content.lower()
            relevant_keywords = [kw for kw in keywords if kw.lower() in content_lower]

            if not relevant_keywords:
                return []

            # Use Claude to analyze
            prompt = f"""Analyze this regulatory content for 2026 compliance updates related to {vertical}.

Keywords found: {relevant_keywords}

Content (truncated):
{content[:6000]}

Extract any NEW or CHANGED regulations. For each one, provide:
- regulation_type: [seer2, refrigerant_gwp, a2l_mandate, efficiency, water_flow]
- current_value: The new threshold/requirement
- effective_date: When it takes effect
- summary: Brief description

Respond in JSON format:
[{{"regulation_type": "", "current_value": "", "effective_date": "", "summary": ""}}]

If no actionable updates found, respond: []"""

            response = await self._client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 1500,
                    "messages": [{"role": "user", "content": prompt}]
                }
            )

            if response.status_code == 200:
                data = response.json()
                text = data["content"][0]["text"]

                # Parse JSON
                import re
                json_match = re.search(r'\[.*\]', text, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group())
                    for item in parsed:
                        if item.get("regulation_type"):
                            updates.append({
                                **item,
                                "source_url": source_url,
                                "vertical": vertical,
                                "discovered_at": datetime.now(timezone.utc).isoformat()
                            })

        except Exception as e:
            logger.error(f"Analysis error: {e}")

        return updates

    def _check_threshold_crossings(
        self,
        updates: List[Dict[str, Any]],
        vertical: str
    ) -> List[Dict[str, Any]]:
        """Check if updates cross compliance thresholds."""
        alerts = []
        current_thresholds = self.thresholds.get(vertical, {})

        for update in updates:
            reg_type = update.get("regulation_type", "")
            new_value = update.get("current_value")

            # Map regulation types to threshold keys
            threshold_map = {
                "seer2": ["seer2_split_north", "seer2_split_south"],
                "refrigerant_gwp": ["gwp_max"],
                "efficiency": ["seer2_split_north", "hspf2_min"],
                "water_flow": ["showerhead_gpm_max", "faucet_gpm_max"]
            }

            threshold_keys = threshold_map.get(reg_type, [])

            for key in threshold_keys:
                if key in current_thresholds:
                    try:
                        old_value = current_thresholds[key]
                        # Compare values (this is simplified - would need type handling)
                        if str(new_value) != str(old_value):
                            alerts.append({
                                "id": f"alert_{hashlib.md5(f'{reg_type}_{new_value}'.encode()).hexdigest()[:8]}",
                                "regulation_type": reg_type,
                                "threshold_key": key,
                                "previous_value": old_value,
                                "new_value": new_value,
                                "severity": "critical" if reg_type in ["refrigerant_gwp", "seer2"] else "warning",
                                "source_url": update.get("source_url"),
                                "effective_date": update.get("effective_date"),
                                "summary": update.get("summary", "")
                            })
                    except Exception:
                        pass

        return alerts

    async def _auto_update_knowledge_base(self, alerts: List[Dict[str, Any]]) -> int:
        """Auto-update regulatory_knowledge.json with new thresholds."""
        updates = 0

        try:
            with open(self.knowledge_path, "r") as f:
                knowledge = json.load(f)

            # Add MCP scout updates section
            if "mcp_scout_updates" not in knowledge:
                knowledge["mcp_scout_updates"] = {}

            for alert in alerts:
                update_key = f"mcp_{alert['regulation_type']}_{alert['id']}"
                knowledge["mcp_scout_updates"][update_key] = {
                    "regulation_type": alert["regulation_type"],
                    "threshold_key": alert.get("threshold_key"),
                    "previous_value": alert["previous_value"],
                    "new_value": alert["new_value"],
                    "source_url": alert.get("source_url"),
                    "effective_date": alert.get("effective_date"),
                    "discovered_at": datetime.now(timezone.utc).isoformat(),
                    "severity": alert["severity"],
                    "auto_applied": True
                }
                updates += 1

                # Update active thresholds
                if alert.get("threshold_key"):
                    vertical = "hvac"  # Would need to track this properly
                    if vertical in self.thresholds:
                        try:
                            self.thresholds[vertical][alert["threshold_key"]] = float(alert["new_value"])
                        except (ValueError, TypeError):
                            pass

            if updates > 0:
                knowledge["metadata"] = knowledge.get("metadata", {})
                knowledge["metadata"]["last_mcp_scout_update"] = datetime.now(timezone.utc).isoformat()
                knowledge["metadata"]["mcp_scout_alerts_count"] = len(alerts)

                with open(self.knowledge_path, "w") as f:
                    json.dump(knowledge, f, indent=2)

                logger.info(f"MCP Scout: Auto-updated {updates} regulations in knowledge base")

        except Exception as e:
            logger.error(f"Failed to update knowledge base: {e}")

        return updates

    async def _flag_job(
        self,
        job_id: str,
        job_data: Dict[str, Any],
        violations: List[Dict[str, Any]]
    ):
        """Flag a job as non-compliant."""
        for violation in violations:
            flag = ComplianceFlag(
                job_id=job_id,
                company_id=job_data.get("company_id", ""),
                regulation_id=violation.get("regulation", ""),
                reason=violation.get("message", ""),
                previous_status="compliant",
                new_status="non_compliant"
            )
            self._compliance_flags.append(flag)

            # In production, this would also:
            # 1. Update job status in database
            # 2. Create notification/task in FSM
            # 3. Send alert to dashboard

            logger.warning(f"Job {job_id} flagged: {violation.get('message')}")

    async def _get_active_jobs(self, vertical: str) -> List[Dict[str, Any]]:
        """Get active jobs for a vertical (mock implementation)."""
        # In production, query from database
        return []

    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()


# =========================================================================
# MCP Server Registration (FastMCP compatible)
# =========================================================================

def create_mcp_tools(server: MCPLegalScoutServer) -> List[Dict[str, Any]]:
    """Create MCP tool definitions for the Legal Scout server."""
    return [
        {
            "name": "monitor_regulatory_updates",
            "description": "Monitor EPA and Energy.gov for 2026 regulatory updates. Checks for A2L refrigerant, SEER2, and other compliance changes.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "sources": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific sources to monitor (epa_aim_act, doe_seer2, etc.)"
                    },
                    "vertical": {
                        "type": "string",
                        "enum": ["hvac", "plumbing", "electrical", "landscaping"],
                        "description": "Filter by vertical"
                    }
                }
            }
        },
        {
            "name": "check_job_compliance",
            "description": "Check if a specific job complies with current regulations.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "Job identifier"},
                    "job_data": {
                        "type": "object",
                        "description": "Job details including equipment, state, vertical",
                        "properties": {
                            "vertical": {"type": "string"},
                            "state": {"type": "string"},
                            "equipment": {"type": "object"}
                        }
                    }
                },
                "required": ["job_id", "job_data"]
            }
        },
        {
            "name": "flag_affected_jobs",
            "description": "Flag all active jobs affected by a regulation change.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "regulation_id": {"type": "string", "description": "The changed regulation"},
                    "new_threshold": {"description": "The new threshold value"},
                    "vertical": {"type": "string", "description": "The affected vertical"}
                },
                "required": ["regulation_id", "new_threshold", "vertical"]
            }
        },
        {
            "name": "get_current_thresholds",
            "description": "Get current regulatory thresholds.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "vertical": {"type": "string", "description": "Optional vertical filter"}
                }
            }
        },
        {
            "name": "schedule_monitoring",
            "description": "Schedule recurring regulatory monitoring.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "frequency": {
                        "type": "string",
                        "enum": ["daily", "weekly", "monthly"],
                        "default": "weekly"
                    },
                    "sources": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Sources to monitor"
                    }
                }
            }
        }
    ]


# Entry point for MCP server
async def run_mcp_server():
    """Run the MCP Legal Scout server."""
    server = MCPLegalScoutServer()

    logger.info("MCP Legal Scout Server started")
    logger.info(f"Monitoring targets: {list(server.monitor_urls.keys())}")

    # In production, this would register with the MCP protocol
    # For now, run an initial scan
    results = await server.monitor_regulatory_updates()
    logger.info(f"Initial scan: {len(results.get('updates_found', []))} updates found")

    await server.close()
    return results


if __name__ == "__main__":
    asyncio.run(run_mcp_server())
