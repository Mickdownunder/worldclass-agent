#!/usr/bin/env python3
import json, sys, pathlib
from jsonschema import Draft202012Validator

def main():
    if len(sys.argv) != 3:
        print("usage: schema_validate.py <schema.json> <doc.json>", file=sys.stderr)
        return 2

    schema_path = pathlib.Path(sys.argv[1])
    doc_path = pathlib.Path(sys.argv[2])

    schema = json.loads(schema_path.read_text())
    doc = json.loads(doc_path.read_text())

    v = Draft202012Validator(schema)
    errors = sorted(v.iter_errors(doc), key=lambda e: e.path)

    if errors:
        for e in errors[:50]:
            path = ".".join(map(str, e.path)) if e.path else "<root>"
            print(f"ERROR {doc_path}: {path}: {e.message}", file=sys.stderr)
        return 1

    print(f"OK {doc_path}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
