"""
Technician Scorecard - ESG Performance Evaluation System
Calculates green performance scores based on 2026 SMART ESG KPIs
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ScoreTier(str, Enum):
    """Scorecard tiers."""
    PLATINUM = "platinum"  # 4.5-5.0
    GOLD = "gold"         # 3.5-4.4
    SILVER = "silver"     # 2.5-3.4
    BRONZE = "bronze"     # 1.5-2.4
    NEEDS_IMPROVEMENT = "needs_improvement"  # Below 1.5


@dataclass
class JobScore:
    """Score for a single job."""
    job_id: str
    compliance_score: float  # 0-5
    execution_score: float   # 0-5
    impact_score: float      # 0-5
    total_score: float       # 0-5
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TechnicianScore:
    """Aggregate score for a technician."""
    technician_id: str
    name: str
    total_jobs: int
    average_score: float
    tier: ScoreTier
    compliance_avg: float
    execution_avg: float
    impact_avg: float
    carbon_saved_total_kg: float
    rebates_captured_total: float
    job_scores: List[JobScore] = field(default_factory=list)
    badges: List[str] = field(default_factory=list)
    trend: str = "stable"  # improving, stable, declining


class GreenScorecard:
    """
    Technician ESG scorecard based on 2026 SMART KPIs.

    Scoring Categories:
    - Compliance (40%): A2L refrigerant use, SEER2 standards, certification validity
    - Execution (30%): Documentation speed, certificate generation, workflow completion
    - Impact (30%): GHG emissions avoided, water saved, rebates captured

    Score Range: 1-5 stars
    """

    def __init__(self, technician_id: str, technician_name: str = ""):
        self.technician_id = technician_id
        self.technician_name = technician_name
        self.job_scores: List[JobScore] = []

        # Scoring weights
        self.weights = {
            "compliance": 0.40,
            "execution": 0.30,
            "impact": 0.30
        }

        # Compliance thresholds (2026 standards)
        self.compliance_thresholds = {
            "seer2_minimum": 15.0,
            "seer2_excellent": 18.0,
            "gwp_maximum": 700,
            "gwp_excellent": 500,
            "waste_diversion_minimum": 0.50,
            "waste_diversion_excellent": 0.75
        }

        # Impact benchmarks
        self.impact_benchmarks = {
            "co2_saved_per_job_good": 50,  # kg
            "co2_saved_per_job_excellent": 150,  # kg
            "rebate_captured_good": 500,  # $
            "rebate_captured_excellent": 2000  # $
        }

    def evaluate_job(self, job_data: Dict[str, Any]) -> JobScore:
        """
        Evaluate a job and calculate scores.

        Args:
            job_data: Dictionary containing:
                - job_id: Job identifier
                - is_a2l: Boolean, is A2L refrigerant used
                - seer2: Float, SEER2 rating
                - refrigerant_gwp: Float, GWP of refrigerant
                - waste_diversion_rate: Float, 0-1
                - cert_generated_on_site: Boolean
                - documentation_complete: Boolean
                - time_to_documentation_hours: Float
                - co2_saved_kg: Float
                - rebates_captured: Float
                - water_saved_gallons: Float
        """
        # 1. Compliance Score
        compliance_score = self._calculate_compliance_score(job_data)

        # 2. Execution Score
        execution_score = self._calculate_execution_score(job_data)

        # 3. Impact Score
        impact_score = self._calculate_impact_score(job_data)

        # Weighted total
        total_score = (
            compliance_score * self.weights["compliance"] +
            execution_score * self.weights["execution"] +
            impact_score * self.weights["impact"]
        )

        job_score = JobScore(
            job_id=job_data.get("job_id", "unknown"),
            compliance_score=compliance_score,
            execution_score=execution_score,
            impact_score=impact_score,
            total_score=total_score,
            details={
                "compliance_breakdown": self._get_compliance_breakdown(job_data),
                "execution_breakdown": self._get_execution_breakdown(job_data),
                "impact_breakdown": self._get_impact_breakdown(job_data)
            }
        )

        self.job_scores.append(job_score)
        return job_score

    def _calculate_compliance_score(self, job_data: Dict[str, Any]) -> float:
        """Calculate compliance score (0-5)."""
        score = 0.0
        max_points = 5.0

        # A2L Refrigerant compliance (2 points)
        if job_data.get("is_a2l", False):
            score += 2.0
        elif job_data.get("refrigerant_gwp", 1000) <= self.compliance_thresholds["gwp_maximum"]:
            score += 1.5

        # SEER2 efficiency (2 points)
        seer2 = job_data.get("seer2", 0)
        if seer2 >= self.compliance_thresholds["seer2_excellent"]:
            score += 2.0
        elif seer2 >= self.compliance_thresholds["seer2_minimum"]:
            score += 1.0
        elif seer2 > 0:
            score += 0.5

        # Waste diversion (1 point)
        diversion = job_data.get("waste_diversion_rate", 0)
        if diversion >= self.compliance_thresholds["waste_diversion_excellent"]:
            score += 1.0
        elif diversion >= self.compliance_thresholds["waste_diversion_minimum"]:
            score += 0.5

        return min(score, max_points)

    def _calculate_execution_score(self, job_data: Dict[str, Any]) -> float:
        """Calculate execution score (0-5)."""
        score = 0.0

        # On-site certificate generation (2 points)
        if job_data.get("cert_generated_on_site", False):
            score += 2.0

        # Documentation completeness (2 points)
        if job_data.get("documentation_complete", False):
            score += 2.0
        elif job_data.get("documentation_partial", False):
            score += 1.0

        # Speed of documentation (1 point)
        hours = job_data.get("time_to_documentation_hours", 24)
        if hours <= 1:
            score += 1.0
        elif hours <= 4:
            score += 0.5

        return min(score, 5.0)

    def _calculate_impact_score(self, job_data: Dict[str, Any]) -> float:
        """Calculate environmental/financial impact score (0-5)."""
        score = 0.0

        # CO2 saved (2 points)
        co2_saved = job_data.get("co2_saved_kg", 0)
        if co2_saved >= self.impact_benchmarks["co2_saved_per_job_excellent"]:
            score += 2.0
        elif co2_saved >= self.impact_benchmarks["co2_saved_per_job_good"]:
            score += 1.0
        elif co2_saved > 0:
            score += 0.5

        # Rebates captured (2 points)
        rebates = job_data.get("rebates_captured", 0)
        if rebates >= self.impact_benchmarks["rebate_captured_excellent"]:
            score += 2.0
        elif rebates >= self.impact_benchmarks["rebate_captured_good"]:
            score += 1.0
        elif rebates > 0:
            score += 0.5

        # Additional impact factors (1 point)
        if job_data.get("water_saved_gallons", 0) > 100:
            score += 0.5
        if job_data.get("customer_educated", False):
            score += 0.5

        return min(score, 5.0)

    def _get_compliance_breakdown(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed compliance breakdown."""
        return {
            "refrigerant": {
                "is_a2l": job_data.get("is_a2l", False),
                "gwp": job_data.get("refrigerant_gwp", "N/A"),
                "status": "Compliant" if job_data.get("is_a2l", False) else "Needs Upgrade"
            },
            "efficiency": {
                "seer2": job_data.get("seer2", "N/A"),
                "meets_2026_standard": job_data.get("seer2", 0) >= 15.0
            },
            "waste": {
                "diversion_rate": job_data.get("waste_diversion_rate", 0),
                "meets_standard": job_data.get("waste_diversion_rate", 0) >= 0.50
            }
        }

    def _get_execution_breakdown(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed execution breakdown."""
        return {
            "certificate": {
                "generated_on_site": job_data.get("cert_generated_on_site", False),
                "time_to_generate": f"{job_data.get('time_to_documentation_hours', 'N/A')} hours"
            },
            "documentation": {
                "complete": job_data.get("documentation_complete", False),
                "photos_uploaded": job_data.get("photos_uploaded", 0)
            }
        }

    def _get_impact_breakdown(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed impact breakdown."""
        return {
            "carbon": {
                "co2_saved_kg": job_data.get("co2_saved_kg", 0),
                "equivalent_trees": int(job_data.get("co2_saved_kg", 0) / 21)  # ~21kg per tree/year
            },
            "financial": {
                "rebates_captured": job_data.get("rebates_captured", 0),
                "customer_savings": job_data.get("customer_savings", 0)
            },
            "water": {
                "gallons_saved": job_data.get("water_saved_gallons", 0)
            }
        }

    def get_final_score(self) -> TechnicianScore:
        """Calculate final technician score from all jobs."""
        if not self.job_scores:
            return TechnicianScore(
                technician_id=self.technician_id,
                name=self.technician_name,
                total_jobs=0,
                average_score=0,
                tier=ScoreTier.NEEDS_IMPROVEMENT,
                compliance_avg=0,
                execution_avg=0,
                impact_avg=0,
                carbon_saved_total_kg=0,
                rebates_captured_total=0,
                badges=[]
            )

        # Calculate averages
        compliance_avg = sum(js.compliance_score for js in self.job_scores) / len(self.job_scores)
        execution_avg = sum(js.execution_score for js in self.job_scores) / len(self.job_scores)
        impact_avg = sum(js.impact_score for js in self.job_scores) / len(self.job_scores)
        average_score = sum(js.total_score for js in self.job_scores) / len(self.job_scores)

        # Calculate totals from job details
        carbon_total = sum(
            js.details.get("impact_breakdown", {}).get("carbon", {}).get("co2_saved_kg", 0)
            for js in self.job_scores
        )
        rebates_total = sum(
            js.details.get("impact_breakdown", {}).get("financial", {}).get("rebates_captured", 0)
            for js in self.job_scores
        )

        # Determine tier
        tier = self._get_tier(average_score)

        # Determine badges
        badges = self._calculate_badges(compliance_avg, execution_avg, impact_avg, carbon_total)

        # Determine trend (compare recent vs older jobs)
        trend = self._calculate_trend()

        return TechnicianScore(
            technician_id=self.technician_id,
            name=self.technician_name,
            total_jobs=len(self.job_scores),
            average_score=round(average_score, 2),
            tier=tier,
            compliance_avg=round(compliance_avg, 2),
            execution_avg=round(execution_avg, 2),
            impact_avg=round(impact_avg, 2),
            carbon_saved_total_kg=round(carbon_total, 1),
            rebates_captured_total=round(rebates_total, 2),
            job_scores=self.job_scores,
            badges=badges,
            trend=trend
        )

    def _get_tier(self, score: float) -> ScoreTier:
        """Determine tier from score."""
        if score >= 4.5:
            return ScoreTier.PLATINUM
        elif score >= 3.5:
            return ScoreTier.GOLD
        elif score >= 2.5:
            return ScoreTier.SILVER
        elif score >= 1.5:
            return ScoreTier.BRONZE
        return ScoreTier.NEEDS_IMPROVEMENT

    def _calculate_badges(
        self,
        compliance_avg: float,
        execution_avg: float,
        impact_avg: float,
        carbon_total: float
    ) -> List[str]:
        """Calculate earned badges."""
        badges = []

        # Compliance badges
        if compliance_avg >= 4.5:
            badges.append("Compliance Champion")
        elif compliance_avg >= 4.0:
            badges.append("Compliance Expert")

        # Execution badges
        if execution_avg >= 4.5:
            badges.append("Documentation Master")
        elif execution_avg >= 4.0:
            badges.append("Efficient Executor")

        # Impact badges
        if impact_avg >= 4.5:
            badges.append("Environmental Hero")
        elif impact_avg >= 4.0:
            badges.append("Green Performer")

        # Carbon badges
        if carbon_total >= 1000:
            badges.append("1 Ton CO2 Saver")
        if carbon_total >= 5000:
            badges.append("5 Ton CO2 Saver")

        # Overall badges
        if len(self.job_scores) >= 100:
            badges.append("Century Club")
        elif len(self.job_scores) >= 50:
            badges.append("Half Century")

        return badges

    def _calculate_trend(self) -> str:
        """Calculate score trend."""
        if len(self.job_scores) < 5:
            return "stable"

        # Compare last 5 jobs to previous 5
        recent = self.job_scores[-5:]
        previous = self.job_scores[-10:-5] if len(self.job_scores) >= 10 else self.job_scores[:-5]

        if not previous:
            return "stable"

        recent_avg = sum(js.total_score for js in recent) / len(recent)
        previous_avg = sum(js.total_score for js in previous) / len(previous)

        diff = recent_avg - previous_avg
        if diff > 0.3:
            return "improving"
        elif diff < -0.3:
            return "declining"
        return "stable"


class TeamScorecard:
    """Aggregate scorecard for a team of technicians."""

    def __init__(self, team_name: str = ""):
        self.team_name = team_name
        self.technician_scorecards: Dict[str, GreenScorecard] = {}

    def add_technician(self, technician_id: str, name: str = "") -> GreenScorecard:
        """Add a technician to the team."""
        scorecard = GreenScorecard(technician_id, name)
        self.technician_scorecards[technician_id] = scorecard
        return scorecard

    def get_team_summary(self) -> Dict[str, Any]:
        """Get aggregated team performance summary."""
        if not self.technician_scorecards:
            return {"status": "no_data", "message": "No technicians in team"}

        tech_scores = [
            sc.get_final_score()
            for sc in self.technician_scorecards.values()
        ]

        total_jobs = sum(ts.total_jobs for ts in tech_scores)
        total_carbon = sum(ts.carbon_saved_total_kg for ts in tech_scores)
        total_rebates = sum(ts.rebates_captured_total for ts in tech_scores)

        avg_scores = [ts.average_score for ts in tech_scores if ts.total_jobs > 0]
        team_avg = sum(avg_scores) / len(avg_scores) if avg_scores else 0

        # Tier distribution
        tier_counts = {}
        for ts in tech_scores:
            tier = ts.tier.value
            tier_counts[tier] = tier_counts.get(tier, 0) + 1

        # Top performers
        top_performers = sorted(
            tech_scores,
            key=lambda x: x.average_score,
            reverse=True
        )[:3]

        return {
            "team_name": self.team_name,
            "technician_count": len(self.technician_scorecards),
            "total_jobs_completed": total_jobs,
            "team_average_score": round(team_avg, 2),
            "team_tier": GreenScorecard("temp")._get_tier(team_avg).value,
            "total_carbon_saved_kg": round(total_carbon, 1),
            "total_rebates_captured": round(total_rebates, 2),
            "tier_distribution": tier_counts,
            "top_performers": [
                {
                    "id": tp.technician_id,
                    "name": tp.name,
                    "score": tp.average_score,
                    "tier": tp.tier.value
                }
                for tp in top_performers
            ]
        }


# Convenience function
def evaluate_technician_job(
    technician_id: str,
    job_data: Dict[str, Any],
    existing_scorecard: Optional[GreenScorecard] = None
) -> JobScore:
    """Quick evaluation of a single job."""
    scorecard = existing_scorecard or GreenScorecard(technician_id)
    return scorecard.evaluate_job(job_data)
