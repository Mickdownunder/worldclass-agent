import json
import subprocess
from pathlib import Path


SCRIPT = "/root/operator/workflows/research-init.sh"


def test_research_init_persists_parent_hypothesis_and_inherits_domain(tmp_path):
    operator_root = tmp_path / "operator"
    parent_id = "proj-parent"
    parent_dir = operator_root / "research" / parent_id
    parent_dir.mkdir(parents=True)
    (parent_dir / "project.json").write_text(
        json.dumps(
            {
                "id": parent_id,
                "question": "Parent",
                "domain": "biotech",
                "config": {"research_mode": "discovery"},
            }
        ),
        encoding="utf-8",
    )

    job_dir = tmp_path / "job"
    job_dir.mkdir()
    request = json.dumps(
        {
            "question": "Child question?",
            "research_mode": "discovery",
            "parent_project_id": parent_id,
            "hypothesis_to_test": "Child hypothesis",
            "mission_id": "mis-123",
            "control_plane_owner": "june",
            "source_command": "mission-executor-prebind",
        }
    )

    completed = subprocess.run(
        ["bash", SCRIPT, request],
        cwd=str(job_dir),
        env={"OPERATOR_ROOT": str(operator_root)},
        capture_output=True,
        text=True,
        check=True,
    )

    project_id = completed.stdout.strip().splitlines()[-1].strip()
    project_path = operator_root / "research" / project_id / "project.json"
    project = json.loads(project_path.read_text(encoding="utf-8"))

    assert project["question"] == "Child question?"
    assert project["parent_project_id"] == parent_id
    assert project["hypothesis_to_test"] == "Child hypothesis"
    assert project["mission_id"] == "mis-123"
    assert project["control_plane_owner"] == "june"
    assert project["source_command"] == "mission-executor-prebind"
    assert project["domain"] == "biotech"
    assert project["config"]["research_mode"] == "discovery"
