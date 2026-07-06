"""Adoption Contribution validation app (static, 0..3 at the adoption meeting)."""
from core.specs import STATIC_SPECS
from core.static_app import run_static_app

run_static_app(STATIC_SPECS["adoption_contribution"])
