"""
Regression tests for strict experiment outcome gate parsing.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.research_experiment import derive_experiment_gate


def test_gate_detects_explicit_failure_marker():
    stdout = """
--- Success Criteria Check ---
FAILURE: The discovered policy did NOT meet all robustness and performance criteria.
  Performance Met (> 5.0% improvement): False
  Robustness (all replications > 5.0%): False
  Robustness (std dev acceptable): False (Std Dev: 0.2302)
"""
    gate = derive_experiment_gate(stdout, execution_success=True)
    assert gate["objective_met"] is False
    assert gate["failure_marker_present"] is True
    assert gate["performance_gate_passed"] is False
    assert gate["replication_gate_passed"] is False
    assert gate["stability_gate_passed"] is False


def test_gate_detects_explicit_success_marker():
    stdout = """
--- Success Criteria Check ---
SUCCESS: The discovered policy is robust and outperforms baselines!
  Performance Met (> 5.0% improvement): True
  Robustness (all replications > 5.0%): True
  Robustness (std dev acceptable): True (Std Dev: 0.0102)
"""
    gate = derive_experiment_gate(stdout, execution_success=True)
    assert gate["objective_met"] is True
    assert gate["success_marker_present"] is True
    assert gate["failure_marker_present"] is False
    assert gate["performance_gate_passed"] is True
    assert gate["replication_gate_passed"] is True
    assert gate["stability_gate_passed"] is True


def test_gate_requires_execution_success():
    stdout = "SUCCESS: The discovered policy is robust and outperforms baselines!"
    gate = derive_experiment_gate(stdout, execution_success=False)
    assert gate["objective_met"] is False
    assert "sandbox_execution_failed" in gate["reasons"]


def test_gate_accepts_hypothesis_proven_marker():
    stdout = """
--- Proof/Disproof of Hypothesis ---
Hypothesis PROVEN: The evolved conditional OptimizerPolicy demonstrated improved final loss AND more stable gradients compared to the fixed policy.
"""
    gate = derive_experiment_gate(stdout, execution_success=True)
    assert gate["objective_met"] is True
    assert gate["hypothesis_proven_marker_present"] is True


def test_gate_rejects_partial_or_not_proven_hypothesis():
    stdout_partial = "Hypothesis PARTIALLY PROVEN: improved one metric only."
    gate_partial = derive_experiment_gate(stdout_partial, execution_success=True)
    assert gate_partial["objective_met"] is False
    assert "hypothesis_only_partially_proven" in gate_partial["reasons"]

    stdout_not = "Hypothesis NOT PROVEN: no clear outperformance."
    gate_not = derive_experiment_gate(stdout_not, execution_success=True)
    assert gate_not["objective_met"] is False
    assert "hypothesis_not_proven" in gate_not["reasons"]


def test_gate_accepts_supported_conclusion_marker():
    stdout = """
--- Evaluation of Hypothesis ---
**CONCLUSION: The hypothesis is SUPPORTED.**
"""
    gate = derive_experiment_gate(stdout, execution_success=True)
    assert gate["objective_met"] is True
    assert gate["conclusion_supported_marker_present"] is True
    assert gate["conclusion_not_supported_marker_present"] is False


def test_gate_accepts_all_passed_criteria_without_explicit_success_marker():
    stdout = """
--- Hypothesis Validation ---
PASS: Criterion 1 (Non-negative losses) - All observed validation losses are >= 0.
PASS: Criterion 2 (Consistent performance gains) - Policy outperforms baseline.
PASS: Criterion 3 (Effective Optimization) - Policy is near true target.
"""
    gate = derive_experiment_gate(stdout, execution_success=True)
    assert gate["objective_met"] is True
    assert gate["criterion_pass_count"] == 3
    assert gate["criterion_fail_count"] == 0

