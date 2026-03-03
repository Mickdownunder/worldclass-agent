#!/usr/bin/env python3
import random
import math
from statistics import mean

random.seed(42)

INPUT_DIM = 4
HIDDEN_DIM = 8
OUTPUT_DIM = 1
DATA_POINTS = 120
INNER_STEPS = 12
GENERATIONS = 25
POPULATION = 12
TOP_K = 4

# Create synthetic dataset (sinusoidal mixture)
x_data = [[random.uniform(-1, 1) for _ in range(INPUT_DIM)] for _ in range(DATA_POINTS)]
y_data = [math.sin(sum(row)) * 0.5 + 0.5 for row in x_data]

# Initialize network parameters
params = {
    "w1": [[random.uniform(-0.2, 0.2) for _ in range(HIDDEN_DIM)] for _ in range(INPUT_DIM)],
    "b1": [0.0] * HIDDEN_DIM,
    "w2": [[random.uniform(-0.2, 0.2) for _ in range(OUTPUT_DIM)] for _ in range(HIDDEN_DIM)],
    "b2": [0.0] * OUTPUT_DIM
}

# Activation functions

def relu(v):
    return [max(0.0, x) for x in v]

def relu_grad(v):
    return [1.0 if x > 0 else 0.0 for x in v]

def forward(x, weights):
    hidden = [sum(x[i] * weights['w1'][i][j] for i in range(INPUT_DIM)) + weights['b1'][j] for j in range(HIDDEN_DIM)]
    activated = relu(hidden)
    out = [sum(activated[k] * weights['w2'][k][j] for k in range(HIDDEN_DIM)) + weights['b2'][j] for j in range(OUTPUT_DIM)]
    return activated, out

def mse_loss(pred, target):
    diff = pred[0] - target
    return diff * diff

def gradients(x, y, weights):
    activated, out = forward(x, weights)
    diff = out[0] - y
    d_out = [2 * diff]
    grad_w2 = [[activated[i] * d_out[0] for _ in range(OUTPUT_DIM)] for i in range(HIDDEN_DIM)]
    grad_b2 = [d_out[0]]
    grad_hidden = [d_out[0] * weights['w2'][i][0] for i in range(HIDDEN_DIM)]
    relu_mask = relu_grad(activated)
    grad_hidden = [grad_hidden[i] * relu_mask[i] for i in range(HIDDEN_DIM)]
    grad_w1 = [[x[d] * grad_hidden[j] for j in range(HIDDEN_DIM)] for d in range(INPUT_DIM)]
    grad_b1 = grad_hidden
    return {'w1': grad_w1, 'b1': grad_b1, 'w2': grad_w2, 'b2': grad_b2}

def apply_grads(weights, grads, lrs):
    new_w1 = [[weights['w1'][i][j] - lrs['w1'] * grads['w1'][i][j] for j in range(HIDDEN_DIM)] for i in range(INPUT_DIM)]
    new_b1 = [weights['b1'][j] - lrs['b1'] * grads['b1'][j] for j in range(HIDDEN_DIM)]
    new_w2 = [[weights['w2'][i][j] - lrs['w2'] * grads['w2'][i][j] for j in range(OUTPUT_DIM)] for i in range(HIDDEN_DIM)]
    new_b2 = [weights['b2'][j] - lrs['b2'] * grads['b2'][j] for j in range(OUTPUT_DIM)]
    return {'w1': new_w1, 'b1': new_b1, 'w2': new_w2, 'b2': new_b2}

def evaluate_candidate(lrs):
    local_weights = {k: [list(row) if isinstance(row, list) else row for row in params[k]] for k in params}
    total_loss = 0.0
    for step in range(INNER_STEPS):
        idx = step % DATA_POINTS
        x = x_data[idx]
        y = y_data[idx]
        grads = gradients(x, y, local_weights)
        local_weights = apply_grads(local_weights, grads, lrs)
        pred = forward(x, local_weights)[1]
        total_loss += mse_loss(pred, y)
    return total_loss / INNER_STEPS, local_weights

# Population holds candidate learning-rate vectors
population = []
for _ in range(POPULATION):
    population.append({
        'w1': random.uniform(0.01, 0.2),
        'b1': random.uniform(0.01, 0.2),
        'w2': random.uniform(0.01, 0.2),
        'b2': random.uniform(0.01, 0.2)
    })

best_history = []
print("--- Starting ES-driven Reflective Gradient Experiment ---")
for gen in range(1, GENERATIONS + 1):
    evaluated = []
    for cand in population:
        loss, _ = evaluate_candidate(cand)
        evaluated.append((loss, cand))
    evaluated.sort(key=lambda x: x[0])
    top = evaluated[:TOP_K]
    best_loss = top[0][0]
    best_lrs = top[0][1]
    best_history.append((gen, best_loss, best_lrs))
    print(f"Generation {gen:02d}: best loss {best_loss:.4f}, lrs {best_lrs}")
    new_center = {k: mean(cand[k] for _, cand in top) for k in top[0][1]}
    new_pop = []
    for _ in range(POPULATION):
        candidate = {k: max(1e-4, new_center[k] + random.gauss(0, 0.02)) for k in new_center}
        new_pop.append(candidate)
    population = new_pop

print("--- Experiment complete ---")
print(f"Best observed loss: {best_history[-1][1]:.4f} at generation {best_history[-1][0]}")
print(f"Best learning rates: {best_history[-1][2]}")
