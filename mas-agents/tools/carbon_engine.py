"""
Carbon Engine - EPA/WattTime/GHG Protocol Integration
Calculates carbon emissions for home service jobs using authoritative data sources
"""

import asyncio
import httpx
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import logging
import json
from functools import lru_cache

logger = logging.getLogger(__name__)


class EmissionScope(str, Enum):
    """GHG Protocol emission scopes."""
    SCOPE_1 = "scope_1"  # Direct emissions (fuel combustion, refrigerant leaks)
    SCOPE_2 = "scope_2"  # Indirect emissions (purchased electricity)
    SCOPE_3 = "scope_3"  # Value chain emissions (materials, transport, waste)


@dataclass
class EmissionFactor:
    """Emission factor with source metadata."""
    value: float
    unit: str
    source: str
    year: int
    category: str
    notes: str = ""


@dataclass
class CarbonCalculation:
    """Result of a carbon calculation."""
    total_kg_co2e: float
    scope: EmissionScope
    breakdown: Dict[str, float] = field(default_factory=dict)
    methodology: str = ""
    data_quality_score: float = 0.0  # 0-1, higher is better
    sources: List[str] = field(default_factory=list)


@dataclass
class GridCarbonIntensity:
    """Real-time grid carbon intensity."""
    moer: float  # Marginal Operating Emissions Rate (lbs CO2/MWh)
    percent: float  # Percentile of cleanness (0-100, higher is cleaner)
    region: str
    timestamp: datetime
    forecast_24h: Optional[List[Dict]] = None


class CarbonEngine:
    """
    Carbon calculation engine using EPA emission factors,
    WattTime API for real-time grid data, and GHG Protocol methodology.
    """

    def __init__(
        self,
        watttime_username: Optional[str] = None,
        watttime_password: Optional[str] = None
    ):
        self.watttime_username = watttime_username
        self.watttime_password = watttime_password
        self._watttime_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None
        self._client = httpx.AsyncClient(timeout=30.0)

        # Initialize EPA emission factors
        self._init_emission_factors()

    def _init_emission_factors(self):
        """Initialize EPA and IPCC emission factors."""

        # EPA GHG Emission Factors Hub 2024
        # https://www.epa.gov/climateleadership/ghg-emission-factors-hub
        self.fuel_factors: Dict[str, EmissionFactor] = {
            # Stationary Combustion
            "natural_gas_therm": EmissionFactor(
                value=5.3,
                unit="kg_co2e/therm",
                source="EPA GHG Hub Table 1",
                year=2024,
                category="fuel_combustion",
                notes="Includes CH4 and N2O"
            ),
            "natural_gas_ccf": EmissionFactor(
                value=5.44,
                unit="kg_co2e/ccf",
                source="EPA GHG Hub Table 1",
                year=2024,
                category="fuel_combustion"
            ),
            "propane_gallon": EmissionFactor(
                value=5.72,
                unit="kg_co2e/gallon",
                source="EPA GHG Hub Table 1",
                year=2024,
                category="fuel_combustion"
            ),
            "fuel_oil_gallon": EmissionFactor(
                value=10.16,
                unit="kg_co2e/gallon",
                source="EPA GHG Hub Table 1",
                year=2024,
                category="fuel_combustion"
            ),
            "diesel_gallon": EmissionFactor(
                value=10.21,
                unit="kg_co2e/gallon",
                source="EPA GHG Hub Table 2",
                year=2024,
                category="mobile_combustion"
            ),
            "gasoline_gallon": EmissionFactor(
                value=8.89,
                unit="kg_co2e/gallon",
                source="EPA GHG Hub Table 2",
                year=2024,
                category="mobile_combustion"
            ),
            # Electric grid average (fallback)
            "electricity_kwh_us_avg": EmissionFactor(
                value=0.386,
                unit="kg_co2e/kWh",
                source="EPA eGRID 2022",
                year=2024,
                category="purchased_electricity"
            ),
        }

        # Refrigerant GWP values (IPCC AR6)
        self.refrigerant_gwp: Dict[str, EmissionFactor] = {
            "R-410A": EmissionFactor(
                value=2088,
                unit="kg_co2e/kg",
                source="IPCC AR6",
                year=2024,
                category="refrigerant"
            ),
            "R-22": EmissionFactor(
                value=1810,
                unit="kg_co2e/kg",
                source="IPCC AR6",
                year=2024,
                category="refrigerant"
            ),
            "R-32": EmissionFactor(
                value=675,
                unit="kg_co2e/kg",
                source="IPCC AR6",
                year=2024,
                category="refrigerant"
            ),
            "R-454B": EmissionFactor(
                value=466,
                unit="kg_co2e/kg",
                source="IPCC AR6",
                year=2024,
                category="refrigerant"
            ),
            "R-290": EmissionFactor(
                value=3,
                unit="kg_co2e/kg",
                source="IPCC AR6",
                year=2024,
                category="refrigerant",
                notes="Propane - natural refrigerant"
            ),
            "R-744": EmissionFactor(
                value=1,
                unit="kg_co2e/kg",
                source="IPCC AR6",
                year=2024,
                category="refrigerant",
                notes="CO2 - natural refrigerant"
            ),
        }

        # EPA eGRID regional factors (2022 data)
        # https://www.epa.gov/egrid
        self.egrid_factors: Dict[str, EmissionFactor] = {
            "CAMX": EmissionFactor(0.225, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "CA/Mexico"),
            "ERCT": EmissionFactor(0.393, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "TX ERCOT"),
            "FRCC": EmissionFactor(0.379, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "FL"),
            "MROE": EmissionFactor(0.501, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "WI/MN"),
            "MROW": EmissionFactor(0.472, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "ND/SD/NE"),
            "NEWE": EmissionFactor(0.213, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "New England"),
            "NWPP": EmissionFactor(0.287, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "NW Power Pool"),
            "NYCW": EmissionFactor(0.238, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "NYC/Westchester"),
            "NYLI": EmissionFactor(0.357, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "Long Island"),
            "NYUP": EmissionFactor(0.115, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "Upstate NY"),
            "RFCE": EmissionFactor(0.296, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "Mid-Atlantic"),
            "RFCM": EmissionFactor(0.518, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "MI"),
            "RFCW": EmissionFactor(0.475, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "OH/IN/WV"),
            "RMPA": EmissionFactor(0.544, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "Rocky Mountain"),
            "SPNO": EmissionFactor(0.465, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "OK/KS"),
            "SPSO": EmissionFactor(0.453, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "AR/LA"),
            "SRMV": EmissionFactor(0.321, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "MS/LA"),
            "SRMW": EmissionFactor(0.645, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "MO/IL"),
            "SRSO": EmissionFactor(0.410, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "AL/GA"),
            "SRTV": EmissionFactor(0.382, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "TN/KY"),
            "SRVC": EmissionFactor(0.316, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "VA/NC/SC"),
            "AZNM": EmissionFactor(0.404, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "AZ/NM"),
            "HIOA": EmissionFactor(0.631, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "Oahu"),
            "AKGD": EmissionFactor(0.421, "kg_co2e/kWh", "EPA eGRID 2022", 2024, "grid", "AK Grid"),
        }

        # State to eGRID subregion mapping
        self.state_to_egrid: Dict[str, str] = {
            "CA": "CAMX", "TX": "ERCT", "FL": "FRCC", "NY": "NYCW",
            "PA": "RFCE", "IL": "SRMW", "OH": "RFCW", "GA": "SRSO",
            "NC": "SRVC", "MI": "RFCM", "NJ": "RFCE", "VA": "SRVC",
            "WA": "NWPP", "AZ": "AZNM", "MA": "NEWE", "TN": "SRTV",
            "IN": "RFCW", "MO": "SRMW", "MD": "RFCE", "WI": "MROE",
            "CO": "RMPA", "MN": "MROE", "SC": "SRVC", "AL": "SRSO",
            "LA": "SRMV", "KY": "SRTV", "OR": "NWPP", "OK": "SPNO",
            "CT": "NEWE", "UT": "NWPP", "IA": "MROW", "NV": "NWPP",
            "AR": "SPSO", "MS": "SRMV", "KS": "SPNO", "NM": "AZNM",
            "NE": "MROW", "WV": "RFCW", "ID": "NWPP", "HI": "HIOA",
            "NH": "NEWE", "ME": "NEWE", "MT": "NWPP", "RI": "NEWE",
            "DE": "RFCE", "SD": "MROW", "ND": "MROW", "AK": "AKGD",
            "VT": "NEWE", "WY": "RMPA",
        }

        # EPA WARM model factors for waste
        # https://www.epa.gov/warm
        self.waste_factors: Dict[str, EmissionFactor] = {
            "landfill_mixed_msw": EmissionFactor(
                value=0.52,
                unit="mtco2e/short_ton",
                source="EPA WARM v16",
                year=2024,
                category="waste"
            ),
            "recycling_mixed_metals": EmissionFactor(
                value=-3.72,
                unit="mtco2e/short_ton",
                source="EPA WARM v16",
                year=2024,
                category="waste",
                notes="Negative = avoided emissions"
            ),
            "recycling_copper": EmissionFactor(
                value=-4.43,
                unit="mtco2e/short_ton",
                source="EPA WARM v16",
                year=2024,
                category="waste"
            ),
            "recycling_aluminum": EmissionFactor(
                value=-9.11,
                unit="mtco2e/short_ton",
                source="EPA WARM v16",
                year=2024,
                category="waste"
            ),
            "composting_yard_waste": EmissionFactor(
                value=-0.08,
                unit="mtco2e/short_ton",
                source="EPA WARM v16",
                year=2024,
                category="waste"
            ),
        }

        # Equipment lifecycle emissions (embodied carbon)
        self.equipment_embodied: Dict[str, EmissionFactor] = {
            "hvac_unit_standard": EmissionFactor(
                value=850,
                unit="kg_co2e",
                source="Industry LCA Average",
                year=2024,
                category="embodied",
                notes="Manufacturing + transport"
            ),
            "heat_pump_air_source": EmissionFactor(
                value=750,
                unit="kg_co2e",
                source="Industry LCA Average",
                year=2024,
                category="embodied"
            ),
            "water_heater_gas": EmissionFactor(
                value=180,
                unit="kg_co2e",
                source="Industry LCA Average",
                year=2024,
                category="embodied"
            ),
            "water_heater_heat_pump": EmissionFactor(
                value=320,
                unit="kg_co2e",
                source="Industry LCA Average",
                year=2024,
                category="embodied"
            ),
            "ev_charger_level2": EmissionFactor(
                value=95,
                unit="kg_co2e",
                source="Industry LCA Average",
                year=2024,
                category="embodied"
            ),
            "solar_panel_per_kw": EmissionFactor(
                value=400,
                unit="kg_co2e/kW",
                source="NREL Harmonized LCA",
                year=2024,
                category="embodied"
            ),
        }

    # WattTime API Integration
    async def _get_watttime_token(self) -> Optional[str]:
        """Authenticate with WattTime API."""
        if not self.watttime_username or not self.watttime_password:
            return None

        if self._watttime_token and self._token_expiry:
            if datetime.now(timezone.utc) < self._token_expiry:
                return self._watttime_token

        try:
            response = await self._client.get(
                "https://api.watttime.org/login",
                auth=(self.watttime_username, self.watttime_password)
            )
            response.raise_for_status()
            data = response.json()
            self._watttime_token = data.get("token")
            # Token expires in 30 minutes
            self._token_expiry = datetime.now(timezone.utc).replace(microsecond=0)
            return self._watttime_token
        except Exception as e:
            logger.error(f"WattTime authentication failed: {e}")
            return None

    async def get_realtime_grid_carbon(
        self,
        latitude: float,
        longitude: float
    ) -> Optional[GridCarbonIntensity]:
        """Get real-time marginal carbon intensity from WattTime."""
        token = await self._get_watttime_token()
        if not token:
            return None

        try:
            # Get region first
            response = await self._client.get(
                "https://api.watttime.org/v3/region-from-loc",
                params={"latitude": latitude, "longitude": longitude},
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            region_data = response.json()
            region = region_data.get("region")

            # Get real-time index
            response = await self._client.get(
                "https://api.watttime.org/v3/signal-index",
                params={"region": region},
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            index_data = response.json()

            return GridCarbonIntensity(
                moer=index_data.get("moer", 0),
                percent=index_data.get("percent", 50),
                region=region,
                timestamp=datetime.now(timezone.utc)
            )

        except Exception as e:
            logger.error(f"WattTime API error: {e}")
            return None

    async def get_grid_forecast(
        self,
        latitude: float,
        longitude: float,
        hours: int = 24
    ) -> Optional[List[Dict]]:
        """Get grid carbon intensity forecast."""
        token = await self._get_watttime_token()
        if not token:
            return None

        try:
            response = await self._client.get(
                "https://api.watttime.org/v3/forecast",
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "horizon_hours": hours
                },
                headers={"Authorization": f"Bearer {token}"}
            )
            response.raise_for_status()
            return response.json().get("data", [])

        except Exception as e:
            logger.error(f"WattTime forecast error: {e}")
            return None

    # Carbon Calculation Methods
    def calculate_fuel_emissions(
        self,
        fuel_type: str,
        quantity: float,
        unit: str = "therm"
    ) -> CarbonCalculation:
        """Calculate Scope 1 emissions from fuel combustion."""
        factor_key = f"{fuel_type}_{unit}"

        if factor_key not in self.fuel_factors:
            # Try to find a matching factor
            for key in self.fuel_factors:
                if fuel_type in key:
                    factor_key = key
                    break

        factor = self.fuel_factors.get(factor_key)
        if not factor:
            return CarbonCalculation(
                total_kg_co2e=0,
                scope=EmissionScope.SCOPE_1,
                methodology="Unknown fuel type",
                data_quality_score=0.0
            )

        emissions = quantity * factor.value

        return CarbonCalculation(
            total_kg_co2e=emissions,
            scope=EmissionScope.SCOPE_1,
            breakdown={fuel_type: emissions},
            methodology=f"Direct combustion: {quantity} {unit} x {factor.value} {factor.unit}",
            data_quality_score=0.9,
            sources=[f"{factor.source} ({factor.year})"]
        )

    def calculate_refrigerant_emissions(
        self,
        refrigerant_type: str,
        quantity_kg: float,
        leak_rate: float = 0.02  # Default 2% annual leak rate
    ) -> CarbonCalculation:
        """Calculate Scope 1 emissions from refrigerant leakage."""
        refrigerant_upper = refrigerant_type.upper().replace("-", "-")

        factor = self.refrigerant_gwp.get(refrigerant_upper)
        if not factor:
            return CarbonCalculation(
                total_kg_co2e=0,
                scope=EmissionScope.SCOPE_1,
                methodology="Unknown refrigerant type",
                data_quality_score=0.0
            )

        # Annual leak emissions
        leaked_kg = quantity_kg * leak_rate
        emissions = leaked_kg * factor.value

        return CarbonCalculation(
            total_kg_co2e=emissions,
            scope=EmissionScope.SCOPE_1,
            breakdown={
                f"{refrigerant_type}_leak": emissions,
                "charge_kg": quantity_kg,
                "leak_rate": leak_rate,
                "gwp": factor.value
            },
            methodology=f"Refrigerant leak: {leaked_kg:.3f} kg x GWP {factor.value}",
            data_quality_score=0.85,
            sources=[f"{factor.source} ({factor.year})"]
        )

    def calculate_electricity_emissions(
        self,
        kwh: float,
        state: str,
        use_realtime: bool = False,
        realtime_moer: Optional[float] = None
    ) -> CarbonCalculation:
        """Calculate Scope 2 emissions from electricity consumption."""

        if use_realtime and realtime_moer:
            # Use real-time marginal emissions (WattTime MOER)
            # MOER is in lbs CO2/MWh, convert to kg CO2/kWh
            kg_per_kwh = realtime_moer * 0.453592 / 1000
            emissions = kwh * kg_per_kwh
            source = "WattTime MOER (real-time marginal)"
            quality = 0.95
        else:
            # Use EPA eGRID regional average
            egrid_region = self.state_to_egrid.get(state.upper(), "US_AVG")
            factor = self.egrid_factors.get(egrid_region)

            if not factor:
                factor = self.fuel_factors["electricity_kwh_us_avg"]
                egrid_region = "US Average"

            emissions = kwh * factor.value
            source = f"EPA eGRID {egrid_region} ({factor.year})"
            quality = 0.8

        return CarbonCalculation(
            total_kg_co2e=emissions,
            scope=EmissionScope.SCOPE_2,
            breakdown={"electricity_kwh": kwh, "emission_rate": emissions / kwh if kwh else 0},
            methodology=f"Purchased electricity: {kwh} kWh",
            data_quality_score=quality,
            sources=[source]
        )

    def calculate_avoided_emissions(
        self,
        old_equipment: Dict[str, Any],
        new_equipment: Dict[str, Any],
        state: str,
        annual_usage_hours: float = 2000
    ) -> Dict[str, Any]:
        """Calculate avoided emissions from equipment upgrade."""

        old_fuel = old_equipment.get("fuel_type", "natural_gas")
        new_fuel = new_equipment.get("fuel_type", "electric")
        old_efficiency = old_equipment.get("efficiency", 0.80)
        new_efficiency = new_equipment.get("efficiency", 0.95)
        capacity_btu = old_equipment.get("capacity_btu", 60000)

        # Calculate annual energy consumption
        annual_btu = capacity_btu * annual_usage_hours

        # Old equipment emissions
        if old_fuel == "natural_gas":
            old_therms = annual_btu / 100000 / old_efficiency
            old_calc = self.calculate_fuel_emissions("natural_gas", old_therms, "therm")
        elif old_fuel == "propane":
            old_gallons = annual_btu / 91500 / old_efficiency
            old_calc = self.calculate_fuel_emissions("propane", old_gallons, "gallon")
        elif old_fuel == "fuel_oil":
            old_gallons = annual_btu / 138500 / old_efficiency
            old_calc = self.calculate_fuel_emissions("fuel_oil", old_gallons, "gallon")
        else:
            old_kwh = annual_btu / 3412 / old_efficiency
            old_calc = self.calculate_electricity_emissions(old_kwh, state)

        # New equipment emissions
        if new_fuel == "electric":
            # Heat pumps have COP (Coefficient of Performance)
            cop = new_equipment.get("cop", 3.0)  # Typical heat pump COP
            new_kwh = annual_btu / 3412 / cop
            new_calc = self.calculate_electricity_emissions(new_kwh, state)
        else:
            new_therms = annual_btu / 100000 / new_efficiency
            new_calc = self.calculate_fuel_emissions(new_fuel, new_therms, "therm")

        avoided = old_calc.total_kg_co2e - new_calc.total_kg_co2e
        percent_reduction = (avoided / old_calc.total_kg_co2e * 100) if old_calc.total_kg_co2e > 0 else 0

        return {
            "old_annual_emissions_kg": old_calc.total_kg_co2e,
            "new_annual_emissions_kg": new_calc.total_kg_co2e,
            "avoided_emissions_kg": avoided,
            "percent_reduction": percent_reduction,
            "lifetime_avoided_kg": avoided * new_equipment.get("expected_life_years", 15),
            "methodology": "GHG Protocol comparative analysis",
            "sources": old_calc.sources + new_calc.sources
        }

    def calculate_waste_emissions(
        self,
        waste_items: List[Dict[str, Any]]
    ) -> CarbonCalculation:
        """Calculate Scope 3 emissions from waste disposal/recycling."""

        total_emissions = 0.0
        breakdown = {}
        sources = set()

        for item in waste_items:
            material = item.get("material", "mixed_msw")
            weight_lbs = item.get("weight_lbs", 0)
            disposal = item.get("disposal_method", "landfill")

            # Convert to short tons
            weight_tons = weight_lbs / 2000

            factor_key = f"{disposal}_{material}"
            factor = self.waste_factors.get(factor_key)

            if not factor:
                # Fall back to mixed MSW landfill
                factor = self.waste_factors.get("landfill_mixed_msw")

            if factor:
                # WARM uses metric tons CO2e, convert to kg
                emissions = weight_tons * factor.value * 1000
                total_emissions += emissions
                breakdown[f"{material}_{disposal}"] = emissions
                sources.add(factor.source)

        return CarbonCalculation(
            total_kg_co2e=total_emissions,
            scope=EmissionScope.SCOPE_3,
            breakdown=breakdown,
            methodology="EPA WARM model methodology",
            data_quality_score=0.75,
            sources=list(sources)
        )

    def calculate_vehicle_emissions(
        self,
        distance_miles: float,
        vehicle_type: str = "gasoline",
        mpg: float = 25.0
    ) -> CarbonCalculation:
        """Calculate Scope 1/3 emissions from vehicle travel."""

        if vehicle_type == "electric":
            # EV: ~0.3 kWh/mile average
            kwh = distance_miles * 0.3
            # Use US average grid factor
            factor = self.fuel_factors["electricity_kwh_us_avg"]
            emissions = kwh * factor.value
            scope = EmissionScope.SCOPE_2
            method = f"EV travel: {distance_miles} miles x 0.3 kWh/mile"
        elif vehicle_type == "diesel":
            gallons = distance_miles / mpg
            factor = self.fuel_factors["diesel_gallon"]
            emissions = gallons * factor.value
            scope = EmissionScope.SCOPE_1
            method = f"Diesel travel: {distance_miles} miles / {mpg} mpg"
        else:  # gasoline
            gallons = distance_miles / mpg
            factor = self.fuel_factors["gasoline_gallon"]
            emissions = gallons * factor.value
            scope = EmissionScope.SCOPE_1
            method = f"Gasoline travel: {distance_miles} miles / {mpg} mpg"

        return CarbonCalculation(
            total_kg_co2e=emissions,
            scope=scope,
            breakdown={"distance_miles": distance_miles, "vehicle_type": vehicle_type},
            methodology=method,
            data_quality_score=0.85,
            sources=[f"{factor.source} ({factor.year})"]
        )

    def calculate_job_carbon_footprint(
        self,
        job_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate complete carbon footprint for a service job.
        Returns breakdown by scope with total and per-scope emissions.
        """

        results = {
            "scope_1": [],
            "scope_2": [],
            "scope_3": [],
            "totals": {"scope_1": 0, "scope_2": 0, "scope_3": 0, "total": 0},
            "avoided_emissions": None,
            "sources": set(),
            "methodology": "GHG Protocol Corporate Standard"
        }

        state = job_data.get("state", "CA")

        # Scope 1: Direct emissions
        # Vehicle travel to job site
        if job_data.get("travel_distance_miles"):
            travel_calc = self.calculate_vehicle_emissions(
                job_data["travel_distance_miles"],
                job_data.get("vehicle_type", "gasoline"),
                job_data.get("vehicle_mpg", 20.0)
            )
            results["scope_1"].append({
                "category": "vehicle_travel",
                "emissions_kg": travel_calc.total_kg_co2e,
                "details": travel_calc.breakdown
            })
            results["totals"]["scope_1"] += travel_calc.total_kg_co2e
            results["sources"].update(travel_calc.sources)

        # Refrigerant handling
        if job_data.get("refrigerant"):
            ref_data = job_data["refrigerant"]
            ref_calc = self.calculate_refrigerant_emissions(
                ref_data.get("type", "R-410A"),
                ref_data.get("charge_kg", 0),
                ref_data.get("leak_rate", 0.02)
            )
            results["scope_1"].append({
                "category": "refrigerant",
                "emissions_kg": ref_calc.total_kg_co2e,
                "details": ref_calc.breakdown
            })
            results["totals"]["scope_1"] += ref_calc.total_kg_co2e
            results["sources"].update(ref_calc.sources)

        # Fuel combustion on-site
        if job_data.get("fuel_used"):
            for fuel in job_data["fuel_used"]:
                fuel_calc = self.calculate_fuel_emissions(
                    fuel.get("type", "natural_gas"),
                    fuel.get("quantity", 0),
                    fuel.get("unit", "therm")
                )
                results["scope_1"].append({
                    "category": f"fuel_{fuel.get('type')}",
                    "emissions_kg": fuel_calc.total_kg_co2e,
                    "details": fuel_calc.breakdown
                })
                results["totals"]["scope_1"] += fuel_calc.total_kg_co2e
                results["sources"].update(fuel_calc.sources)

        # Scope 2: Electricity for tools/equipment
        if job_data.get("electricity_kwh"):
            elec_calc = self.calculate_electricity_emissions(
                job_data["electricity_kwh"],
                state
            )
            results["scope_2"].append({
                "category": "tool_electricity",
                "emissions_kg": elec_calc.total_kg_co2e,
                "details": elec_calc.breakdown
            })
            results["totals"]["scope_2"] += elec_calc.total_kg_co2e
            results["sources"].update(elec_calc.sources)

        # Scope 3: Waste and materials
        if job_data.get("waste"):
            waste_calc = self.calculate_waste_emissions(job_data["waste"])
            results["scope_3"].append({
                "category": "waste_disposal",
                "emissions_kg": waste_calc.total_kg_co2e,
                "details": waste_calc.breakdown
            })
            results["totals"]["scope_3"] += waste_calc.total_kg_co2e
            results["sources"].update(waste_calc.sources)

        # Equipment embodied carbon
        if job_data.get("equipment_installed"):
            for equip in job_data["equipment_installed"]:
                equip_type = equip.get("type", "hvac_unit_standard")
                factor = self.equipment_embodied.get(equip_type)
                if factor:
                    quantity = equip.get("quantity", 1)
                    emissions = factor.value * quantity
                    results["scope_3"].append({
                        "category": f"embodied_{equip_type}",
                        "emissions_kg": emissions,
                        "details": {"type": equip_type, "quantity": quantity}
                    })
                    results["totals"]["scope_3"] += emissions
                    results["sources"].add(factor.source)

        # Calculate avoided emissions if upgrade
        if job_data.get("old_equipment") and job_data.get("new_equipment"):
            results["avoided_emissions"] = self.calculate_avoided_emissions(
                job_data["old_equipment"],
                job_data["new_equipment"],
                state,
                job_data.get("annual_usage_hours", 2000)
            )

        # Calculate total
        results["totals"]["total"] = (
            results["totals"]["scope_1"] +
            results["totals"]["scope_2"] +
            results["totals"]["scope_3"]
        )

        # Convert sources set to list
        results["sources"] = list(results["sources"])

        return results

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()


# Utility functions
def get_state_grid_factor(state: str) -> Tuple[float, str]:
    """Get grid emission factor for a state."""
    engine = CarbonEngine()
    egrid_region = engine.state_to_egrid.get(state.upper(), "US_AVG")
    factor = engine.egrid_factors.get(egrid_region)

    if factor:
        return factor.value, egrid_region
    return 0.386, "US Average"


def estimate_annual_savings(
    equipment_type: str,
    old_efficiency: float,
    new_efficiency: float,
    state: str,
    annual_load_btu: float
) -> Dict[str, float]:
    """Estimate annual carbon and cost savings from upgrade."""
    engine = CarbonEngine()

    grid_factor, region = get_state_grid_factor(state)

    # Assuming electric heat pump upgrade
    old_kwh = annual_load_btu / 3412 / old_efficiency
    new_kwh = annual_load_btu / 3412 / new_efficiency

    old_emissions = old_kwh * grid_factor
    new_emissions = new_kwh * grid_factor

    # Average electricity rate
    avg_rate = 0.12  # $/kWh national average

    return {
        "old_kwh": old_kwh,
        "new_kwh": new_kwh,
        "kwh_saved": old_kwh - new_kwh,
        "old_emissions_kg": old_emissions,
        "new_emissions_kg": new_emissions,
        "emissions_saved_kg": old_emissions - new_emissions,
        "annual_cost_savings": (old_kwh - new_kwh) * avg_rate,
        "grid_region": region
    }
