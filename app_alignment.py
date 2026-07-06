"""Position Alignment validation app (static, -2..+2 at the adoption meeting)."""
from core.specs import STATIC_SPECS
from core.static_app import run_static_app

run_static_app(STATIC_SPECS["position_alignment"])
