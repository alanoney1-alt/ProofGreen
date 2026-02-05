"""
Equipment Vision Parser - Claude Vision Integration
Uses Claude 3.5/4 Vision to extract equipment specifications from photos.
Automates compliance verification for HVAC, plumbing, and electrical equipment.
"""

import base64
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import httpx

logger = logging.getLogger(__name__)


@dataclass
class EquipmentData:
    """Extracted equipment specifications."""
    # Identification
    manufacturer: Optional[str] = None
    model_number: Optional[str] = None
    serial_number: Optional[str] = None

    # HVAC specific
    seer_rating: Optional[float] = None
    seer2_rating: Optional[float] = None
    hspf_rating: Optional[float] = None
    hspf2_rating: Optional[float] = None
    eer_rating: Optional[float] = None
    refrigerant_type: Optional[str] = None
    refrigerant_charge_oz: Optional[float] = None
    btu_capacity: Optional[int] = None
    tonnage: Optional[float] = None

    # Electrical specific
    voltage: Optional[int] = None
    amperage: Optional[float] = None
    phase: Optional[int] = None
    wattage: Optional[int] = None

    # Plumbing specific
    gpm: Optional[float] = None
    gpf: Optional[float] = None
    uef: Optional[float] = None
    first_hour_rating: Optional[float] = None
    tank_capacity_gallons: Optional[float] = None

    # General
    equipment_type: Optional[str] = None
    install_date: Optional[str] = None
    certification_marks: List[str] = field(default_factory=list)
    energy_star_certified: bool = False
    ahri_reference_number: Optional[str] = None

    # Confidence and metadata
    extraction_confidence: float = 0.0
    raw_text_detected: str = ""
    image_quality: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "manufacturer": self.manufacturer,
            "model_number": self.model_number,
            "serial_number": self.serial_number,
            "seer_rating": self.seer_rating,
            "seer2_rating": self.seer2_rating,
            "hspf_rating": self.hspf_rating,
            "hspf2_rating": self.hspf2_rating,
            "eer_rating": self.eer_rating,
            "refrigerant_type": self.refrigerant_type,
            "refrigerant_charge_oz": self.refrigerant_charge_oz,
            "btu_capacity": self.btu_capacity,
            "tonnage": self.tonnage,
            "voltage": self.voltage,
            "amperage": self.amperage,
            "phase": self.phase,
            "wattage": self.wattage,
            "gpm": self.gpm,
            "gpf": self.gpf,
            "uef": self.uef,
            "first_hour_rating": self.first_hour_rating,
            "tank_capacity_gallons": self.tank_capacity_gallons,
            "equipment_type": self.equipment_type,
            "install_date": self.install_date,
            "certification_marks": self.certification_marks,
            "energy_star_certified": self.energy_star_certified,
            "ahri_reference_number": self.ahri_reference_number,
            "extraction_confidence": self.extraction_confidence,
            "image_quality": self.image_quality
        }


@dataclass
class ComplianceCheck:
    """Equipment compliance check result."""
    equipment_data: EquipmentData
    is_compliant: bool
    compliance_score: float  # 0-100
    issues: List[Dict[str, str]]
    warnings: List[Dict[str, str]]
    recommendations: List[str]
    regulations_checked: List[str]


class EquipmentVisionParser:
    """
    Uses Claude Vision to extract equipment specifications from photos.

    Capabilities:
    - Read equipment nameplates and data tags
    - Extract SEER/SEER2, refrigerant type, model numbers
    - Verify Energy Star and AHRI certifications
    - Check compliance with 2026 regulations
    """

    def __init__(
        self,
        anthropic_api_key: str,
        model: str = "claude-sonnet-4-20250514"
    ):
        self.api_key = anthropic_api_key
        self.model = model
        self._client = httpx.AsyncClient(timeout=120.0)

        # 2026 compliance thresholds
        self.compliance_thresholds = {
            "hvac": {
                "seer2_split_min": 14.3,  # Split systems
                "seer2_packaged_min": 13.4,  # Packaged units
                "seer2_south_split_min": 15.2,  # Southern states
                "hspf2_min": 7.5,
                "gwp_max": 700,  # EPA AIM Act
                "approved_refrigerants": ["R-454B", "R-32", "R-290", "R-744"],
                "banned_refrigerants": ["R-410A", "R-22", "R-407C"]  # After certain dates
            },
            "plumbing": {
                "showerhead_gpm_max": 1.8,
                "lavatory_faucet_gpm_max": 1.2,
                "kitchen_faucet_gpm_max": 1.8,
                "toilet_gpf_max": 1.28,
                "urinal_gpf_max": 0.5,
                "water_heater_uef_min": {
                    "tankless": 0.87,
                    "tank_electric": 0.93,
                    "tank_gas": 0.64,
                    "heat_pump": 2.0
                }
            },
            "electrical": {
                "ev_circuit_voltage": 240,
                "ev_circuit_amperage_min": 40
            }
        }

        # Refrigerant GWP values (Global Warming Potential)
        self.refrigerant_gwp = {
            "R-22": 1810,
            "R-410A": 2088,
            "R-407C": 1774,
            "R-454B": 466,
            "R-32": 675,
            "R-290": 3,
            "R-744": 1,
            "R-1234yf": 4,
            "R-1234ze": 7
        }

    async def parse_equipment_photo(
        self,
        image_path: str,
        equipment_type: Optional[str] = None
    ) -> EquipmentData:
        """
        Parse equipment specifications from a photo using Claude Vision.

        Args:
            image_path: Path to the equipment photo
            equipment_type: Optional hint about equipment type (hvac, plumbing, electrical)

        Returns:
            EquipmentData with extracted specifications
        """
        # Load and encode image
        image_data, media_type = self._load_image(image_path)

        # Build extraction prompt
        prompt = self._build_extraction_prompt(equipment_type)

        try:
            response = await self._client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "max_tokens": 2000,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_data
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }]
                }
            )
            response.raise_for_status()
            data = response.json()

            # Parse the response
            text = data["content"][0]["text"]
            equipment = self._parse_extraction_response(text)
            equipment.image_quality = self._assess_image_quality(data)

            logger.info(f"Equipment parsed: {equipment.manufacturer} {equipment.model_number}")
            return equipment

        except Exception as e:
            logger.error(f"Equipment photo parsing error: {e}")
            return EquipmentData(
                extraction_confidence=0.0,
                raw_text_detected=f"Error: {str(e)}"
            )

    async def parse_multiple_photos(
        self,
        image_paths: List[str],
        equipment_type: Optional[str] = None
    ) -> EquipmentData:
        """
        Parse equipment from multiple photos and combine results.
        Useful when capturing different angles/labels of the same equipment.
        """
        all_data = []

        for path in image_paths:
            data = await self.parse_equipment_photo(path, equipment_type)
            if data.extraction_confidence > 0.3:
                all_data.append(data)

        if not all_data:
            return EquipmentData(extraction_confidence=0.0)

        # Merge data from all photos
        return self._merge_equipment_data(all_data)

    def check_compliance(
        self,
        equipment: EquipmentData,
        state: str = "CA",
        vertical: Optional[str] = None
    ) -> ComplianceCheck:
        """
        Check equipment compliance against 2026 regulations.
        """
        issues = []
        warnings = []
        recommendations = []
        regulations_checked = []
        compliance_score = 100.0

        # Determine equipment type if not specified
        vert = vertical or self._infer_vertical(equipment)

        if vert == "hvac":
            self._check_hvac_compliance(
                equipment, state, issues, warnings,
                recommendations, regulations_checked
            )
        elif vert == "plumbing":
            self._check_plumbing_compliance(
                equipment, issues, warnings,
                recommendations, regulations_checked
            )
        elif vert == "electrical":
            self._check_electrical_compliance(
                equipment, issues, warnings,
                recommendations, regulations_checked
            )

        # Calculate compliance score
        compliance_score -= len(issues) * 20
        compliance_score -= len(warnings) * 5
        compliance_score = max(0, compliance_score)

        return ComplianceCheck(
            equipment_data=equipment,
            is_compliant=len(issues) == 0,
            compliance_score=compliance_score,
            issues=issues,
            warnings=warnings,
            recommendations=recommendations,
            regulations_checked=regulations_checked
        )

    def _check_hvac_compliance(
        self,
        equipment: EquipmentData,
        state: str,
        issues: List,
        warnings: List,
        recommendations: List,
        regulations: List
    ):
        """Check HVAC equipment compliance."""
        thresholds = self.compliance_thresholds["hvac"]

        # SEER2 check
        if equipment.seer2_rating:
            regulations.append("DOE SEER2 2023")
            min_seer2 = thresholds["seer2_split_min"]

            # Southern states have higher requirements
            if state in ["FL", "TX", "AZ", "NV", "CA", "LA", "MS", "AL", "GA"]:
                min_seer2 = thresholds["seer2_south_split_min"]
                regulations.append(f"{state} SEER2 Regional Standard")

            if equipment.seer2_rating < min_seer2:
                issues.append({
                    "code": "SEER2_BELOW_MIN",
                    "description": f"SEER2 rating {equipment.seer2_rating} below minimum {min_seer2}",
                    "regulation": "DOE SEER2 2023"
                })

        elif equipment.seer_rating:
            # Old SEER rating - may need conversion
            warnings.append({
                "code": "SEER_NOT_SEER2",
                "description": "Equipment shows SEER not SEER2 - verify compliance with current standards",
                "regulation": "DOE SEER2 2023"
            })
            recommendations.append("Verify SEER2 rating with manufacturer or AHRI directory")

        # Refrigerant check
        if equipment.refrigerant_type:
            regulations.append("EPA AIM Act 2024")
            gwp = self.refrigerant_gwp.get(equipment.refrigerant_type, 0)

            if gwp > thresholds["gwp_max"]:
                if equipment.refrigerant_type in thresholds["banned_refrigerants"]:
                    issues.append({
                        "code": "REFRIGERANT_BANNED",
                        "description": f"{equipment.refrigerant_type} (GWP {gwp}) exceeds 700 GWP limit",
                        "regulation": "EPA AIM Act - effective 2025"
                    })
                else:
                    warnings.append({
                        "code": "HIGH_GWP_REFRIGERANT",
                        "description": f"{equipment.refrigerant_type} has high GWP ({gwp})",
                        "regulation": "EPA AIM Act"
                    })
                recommendations.append(
                    f"Consider A2L refrigerant alternatives: {', '.join(thresholds['approved_refrigerants'])}"
                )

        # HSPF2 for heat pumps
        if equipment.hspf2_rating:
            regulations.append("DOE HSPF2 2023")
            if equipment.hspf2_rating < thresholds["hspf2_min"]:
                issues.append({
                    "code": "HSPF2_BELOW_MIN",
                    "description": f"HSPF2 rating {equipment.hspf2_rating} below minimum {thresholds['hspf2_min']}",
                    "regulation": "DOE HSPF2 2023"
                })

        # Energy Star check
        if not equipment.energy_star_certified:
            recommendations.append("Consider Energy Star certified equipment for rebate eligibility")

    def _check_plumbing_compliance(
        self,
        equipment: EquipmentData,
        issues: List,
        warnings: List,
        recommendations: List,
        regulations: List
    ):
        """Check plumbing equipment compliance."""
        thresholds = self.compliance_thresholds["plumbing"]

        # Flow rate checks
        if equipment.gpm:
            regulations.append("EPA WaterSense")

            # Determine fixture type from equipment type
            if "shower" in (equipment.equipment_type or "").lower():
                if equipment.gpm > thresholds["showerhead_gpm_max"]:
                    issues.append({
                        "code": "GPM_EXCEEDS_MAX",
                        "description": f"Showerhead {equipment.gpm} GPM exceeds {thresholds['showerhead_gpm_max']} GPM max",
                        "regulation": "EPA WaterSense"
                    })
            elif "faucet" in (equipment.equipment_type or "").lower():
                max_gpm = thresholds["lavatory_faucet_gpm_max"]
                if "kitchen" in (equipment.equipment_type or "").lower():
                    max_gpm = thresholds["kitchen_faucet_gpm_max"]
                if equipment.gpm > max_gpm:
                    issues.append({
                        "code": "GPM_EXCEEDS_MAX",
                        "description": f"Faucet {equipment.gpm} GPM exceeds {max_gpm} GPM max",
                        "regulation": "EPA WaterSense"
                    })

        # Water heater efficiency
        if equipment.uef:
            regulations.append("DOE Water Heater Efficiency 2024")
            # Would need to determine heater type for proper threshold

        # GPF for toilets
        if equipment.gpf:
            regulations.append("EPA WaterSense")
            if equipment.gpf > thresholds["toilet_gpf_max"]:
                issues.append({
                    "code": "GPF_EXCEEDS_MAX",
                    "description": f"Toilet {equipment.gpf} GPF exceeds {thresholds['toilet_gpf_max']} GPF max",
                    "regulation": "EPA WaterSense"
                })

    def _check_electrical_compliance(
        self,
        equipment: EquipmentData,
        issues: List,
        warnings: List,
        recommendations: List,
        regulations: List
    ):
        """Check electrical equipment compliance."""
        # EV charging circuit requirements
        if equipment.equipment_type and "ev" in equipment.equipment_type.lower():
            regulations.append("NEC 2023 EV Ready")
            thresholds = self.compliance_thresholds["electrical"]

            if equipment.voltage and equipment.voltage < thresholds["ev_circuit_voltage"]:
                issues.append({
                    "code": "EV_VOLTAGE_LOW",
                    "description": f"EV circuit voltage {equipment.voltage}V below required {thresholds['ev_circuit_voltage']}V",
                    "regulation": "NEC 2023"
                })

            if equipment.amperage and equipment.amperage < thresholds["ev_circuit_amperage_min"]:
                warnings.append({
                    "code": "EV_AMPERAGE_LOW",
                    "description": f"EV circuit {equipment.amperage}A may limit charging speed",
                    "regulation": "NEC 2023"
                })

    def _load_image(self, image_path: str) -> Tuple[str, str]:
        """Load and base64 encode an image."""
        path = Path(image_path)

        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Determine media type
        suffix = path.suffix.lower()
        media_types = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp"
        }
        media_type = media_types.get(suffix, "image/jpeg")

        # Load and encode
        with open(path, "rb") as f:
            data = base64.b64encode(f.read()).decode("utf-8")

        return data, media_type

    def _build_extraction_prompt(self, equipment_type: Optional[str]) -> str:
        """Build the extraction prompt for Claude Vision."""
        type_hint = f"This appears to be {equipment_type} equipment. " if equipment_type else ""

        return f"""Analyze this equipment photo and extract all visible specifications from the nameplate/data tag.
{type_hint}
Extract the following information (leave blank if not visible):

IDENTIFICATION:
- Manufacturer/Brand name
- Model Number
- Serial Number

HVAC SPECIFICATIONS (if applicable):
- SEER Rating
- SEER2 Rating
- HSPF Rating
- HSPF2 Rating
- EER Rating
- Refrigerant Type (e.g., R-410A, R-454B, R-32)
- Refrigerant Charge (oz)
- BTU Capacity
- Tonnage

ELECTRICAL SPECIFICATIONS:
- Voltage (V)
- Amperage (A)
- Phase
- Wattage (W)

PLUMBING SPECIFICATIONS (if applicable):
- GPM (Gallons Per Minute)
- GPF (Gallons Per Flush)
- UEF (Uniform Energy Factor)
- First Hour Rating
- Tank Capacity (gallons)

CERTIFICATIONS:
- Energy Star certified? (yes/no)
- AHRI Reference Number
- Other certification marks visible

Respond in JSON format:
{{
    "manufacturer": "",
    "model_number": "",
    "serial_number": "",
    "seer_rating": null,
    "seer2_rating": null,
    "hspf_rating": null,
    "hspf2_rating": null,
    "eer_rating": null,
    "refrigerant_type": "",
    "refrigerant_charge_oz": null,
    "btu_capacity": null,
    "tonnage": null,
    "voltage": null,
    "amperage": null,
    "phase": null,
    "wattage": null,
    "gpm": null,
    "gpf": null,
    "uef": null,
    "first_hour_rating": null,
    "tank_capacity_gallons": null,
    "equipment_type": "",
    "energy_star_certified": false,
    "ahri_reference_number": "",
    "certification_marks": [],
    "raw_text_detected": "",
    "extraction_confidence": 0.0
}}

Set extraction_confidence between 0.0 and 1.0 based on image clarity and data visibility."""

    def _parse_extraction_response(self, text: str) -> EquipmentData:
        """Parse Claude's response into EquipmentData."""
        try:
            # Find JSON in response
            json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())

                return EquipmentData(
                    manufacturer=data.get("manufacturer"),
                    model_number=data.get("model_number"),
                    serial_number=data.get("serial_number"),
                    seer_rating=data.get("seer_rating"),
                    seer2_rating=data.get("seer2_rating"),
                    hspf_rating=data.get("hspf_rating"),
                    hspf2_rating=data.get("hspf2_rating"),
                    eer_rating=data.get("eer_rating"),
                    refrigerant_type=data.get("refrigerant_type"),
                    refrigerant_charge_oz=data.get("refrigerant_charge_oz"),
                    btu_capacity=data.get("btu_capacity"),
                    tonnage=data.get("tonnage"),
                    voltage=data.get("voltage"),
                    amperage=data.get("amperage"),
                    phase=data.get("phase"),
                    wattage=data.get("wattage"),
                    gpm=data.get("gpm"),
                    gpf=data.get("gpf"),
                    uef=data.get("uef"),
                    first_hour_rating=data.get("first_hour_rating"),
                    tank_capacity_gallons=data.get("tank_capacity_gallons"),
                    equipment_type=data.get("equipment_type"),
                    certification_marks=data.get("certification_marks", []),
                    energy_star_certified=data.get("energy_star_certified", False),
                    ahri_reference_number=data.get("ahri_reference_number"),
                    extraction_confidence=data.get("extraction_confidence", 0.5),
                    raw_text_detected=data.get("raw_text_detected", "")
                )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse extraction response: {e}")

        return EquipmentData(
            extraction_confidence=0.0,
            raw_text_detected=text[:500]
        )

    def _assess_image_quality(self, response_data: Dict) -> str:
        """Assess image quality from response metadata."""
        # This could be enhanced with actual image analysis
        return "good"

    def _merge_equipment_data(self, data_list: List[EquipmentData]) -> EquipmentData:
        """Merge equipment data from multiple photos."""
        merged = EquipmentData()

        for data in data_list:
            # Take non-None values with highest confidence
            for field_name in [
                "manufacturer", "model_number", "serial_number",
                "seer_rating", "seer2_rating", "hspf_rating", "hspf2_rating",
                "refrigerant_type", "btu_capacity", "tonnage",
                "voltage", "amperage", "gpm", "uef"
            ]:
                current = getattr(merged, field_name)
                new = getattr(data, field_name)
                if new and (not current or data.extraction_confidence > merged.extraction_confidence):
                    setattr(merged, field_name, new)

        # Merge certification marks
        all_marks = set()
        for data in data_list:
            all_marks.update(data.certification_marks)
        merged.certification_marks = list(all_marks)

        # Energy Star - if any photo shows it
        merged.energy_star_certified = any(d.energy_star_certified for d in data_list)

        # Average confidence
        merged.extraction_confidence = sum(d.extraction_confidence for d in data_list) / len(data_list)

        return merged

    def _infer_vertical(self, equipment: EquipmentData) -> str:
        """Infer vertical from equipment data."""
        if equipment.seer_rating or equipment.seer2_rating or equipment.refrigerant_type:
            return "hvac"
        if equipment.gpm or equipment.gpf or equipment.uef:
            return "plumbing"
        if equipment.voltage or equipment.amperage:
            return "electrical"
        return "unknown"

    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()


# Convenience function
async def parse_equipment_photo(
    image_path: str,
    anthropic_api_key: str,
    equipment_type: Optional[str] = None
) -> EquipmentData:
    """Parse equipment photo and return extracted data."""
    parser = EquipmentVisionParser(anthropic_api_key)
    try:
        return await parser.parse_equipment_photo(image_path, equipment_type)
    finally:
        await parser.close()
