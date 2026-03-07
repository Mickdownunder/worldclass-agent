"""Synthesis pipeline: run_synthesis, contract validation, and public helpers."""
from tools.synthesis.run import main, run_synthesis
from tools.synthesis.contract import (
    SynthesisContractError,
    validate_synthesis_contract,
    extract_claim_refs_from_report,
    _build_valid_claim_ref_set,
)
from tools.synthesis.ledger import (
    normalize_to_strings,
    _build_provenance_appendix,
    _build_claim_source_registry,
)

__all__ = [
    "run_synthesis",
    "main",
    "validate_synthesis_contract",
    "SynthesisContractError",
    "normalize_to_strings",
    "extract_claim_refs_from_report",
    "_build_valid_claim_ref_set",
    "_build_provenance_appendix",
    "_build_claim_source_registry",
]
