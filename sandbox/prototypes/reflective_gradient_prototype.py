#!/usr/bin/env python3
import json
import random
import datetime
from pathlib import Path

BASE_LR = 0.01
STEPS = 20
LAYERS = ["embedding", "encoder", "decoder"]
OUTPUT_DIR = Path(__file__).resolve().parent

history = {layer: {"grad": 0.0, "lr": BASE_LR} for layer in LAYERS}
trajectory = []
codebook = {}

for step in range(1, STEPS + 1):
    step_record = {"step": step, "context": {}}
    for layer in LAYERS:
        grad = random.uniform(0.1, 1.0)
        last_grad = history[layer]["grad"]
        last_lr = history[layer]["lr"]
        delta = abs(grad - last_grad)
        adapt = 1 + (0.06 if delta < 0.15 else -0.02)
        lr = max(0.002, min(0.05, last_lr * adapt))
        history[layer] = {"grad": grad, "lr": lr}
        step_record["context"][layer] = {"grad": round(grad, 4), "lr": round(lr, 5), "delta": round(delta, 4)}
        codebook.setdefault(layer, []).append({"step": step, "grad": grad, "lr": lr})
    trajectory.append(step_record)

summary = {
    "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    "base_lr": BASE_LR,
    "steps": STEPS,
    "layers": LAYERS,
    "final_lr": {layer: history[layer]["lr"] for layer in LAYERS},
    "avg_lr": {layer: round(sum(entry["lr"] for entry in codebook[layer]) / len(codebook[layer]), 5) for layer in LAYERS},
    "codebook_samples": {layer: codebook[layer][-3:] for layer in LAYERS}
}

summary_path = OUTPUT_DIR / "reflective_gradient_prototype_summary.json"
with summary_path.open("w") as fout:
    json.dump({"trajectory": trajectory, "summary": summary}, fout, indent=2)

print("[sandbox] Reflective gradient prototype completed.")
print(f"Summary written to {summary_path}")
