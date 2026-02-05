"""
ProofGreen MAS - API Package
FastAPI route modules.
"""

from .workflow_routes import router as workflow_router

__all__ = [
    "workflow_router",
]
