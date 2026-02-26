"""Unit tests for tools/schema_validate.py."""
import json
import pytest
from pathlib import Path

pytest.importorskip("jsonschema")

from tools.schema_validate import main as schema_validate_main


def test_schema_validate_valid_doc(tmp_path):
    """Valid doc against schema returns 0."""
    import sys
    schema_path = tmp_path / "schema.json"
    doc_path = tmp_path / "doc.json"
    schema_path.write_text(json.dumps({"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}))
    doc_path.write_text(json.dumps({"name": "test"}))
    old_argv = sys.argv
    sys.argv = ["schema_validate.py", str(schema_path), str(doc_path)]
    try:
        code = schema_validate_main()
        assert code == 0
    finally:
        sys.argv = old_argv


def test_schema_validate_invalid_doc(tmp_path):
    """Invalid doc (missing required) returns 1."""
    import sys
    schema_path = tmp_path / "schema.json"
    doc_path = tmp_path / "doc.json"
    schema_path.write_text(json.dumps({"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}))
    doc_path.write_text(json.dumps({}))
    old_argv = sys.argv
    sys.argv = ["schema_validate.py", str(schema_path), str(doc_path)]
    try:
        code = schema_validate_main()
        assert code == 1
    finally:
        sys.argv = old_argv
