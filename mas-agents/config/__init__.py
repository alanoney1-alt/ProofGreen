"""
ProofGreen Configuration Module
Settings and regulatory knowledge
"""

from .settings import settings, get_climate_region, get_seer2_minimum

__all__ = [
    "settings",
    "get_climate_region",
    "get_seer2_minimum"
]
