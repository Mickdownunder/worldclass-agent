#!/usr/bin/env python3
import random
import math
from statistics import mean

random.seed(31415)
INPUT_DIM = 6
HIDDEN1 = 10
HIDDEN2 = 8
OUTPUT_DIM = 1
DATA_POINTS = 180
INNER_STEPS = 18
GENERATIONS = 30
POPULATION = 14
TOP_K = 5

# create dataset
x_data = [[random.uniform(-1.5, 1.5) for _ in range(INPUT_DIM)] for _ in range(DATA_POINTS)]
y_data = [math.tanh(sum(row) * 0.4) * 0.5 + 0.5 for row in x_data]

# base parameters stored for fairness
base_params = {
    'w1': [[random.uniform(-0.15, 0.15) for _ in range(HIDDEN1)] for _ in range(INPUT_DIM)],
    'b1': [0.0] * HIDDEN1,
    'w2': [[random.uniform(-0.15, 0.15) for _ in range(HIDDEN2)] for _ in range(HIDDEN1)],
    'b2': [0.0] * HIDDEN2,
    'w3': [[random.uniform(-0.25, 0.25) for _ in range(OUTPUT_DIM)] for _ in range(HIDDEN2)],
    'b3': [0.0] * OUTPUT_DIM
}

def relu(v):
    return [max(0.0, x) for x in v]

def relu_grad(v):
    return [1.0 if x > 0.0 else 0.0 for x in v]

def forward(x, params):
    hidden1 = [sum(x[i] * params['w1'][i][j] for i in range(INPUT_DIM)) + params['b1'][j] for j in range(HIDDEN1)]
    act1 = relu(hidden1)
    hidden2 = [sum(act1[i] * params['w2'][i][j] for i in range(HIDDEN1)) + params['b2'][j] for j in range(HIDDEN2)]
    act2 = relu(hidden2)
    out = [sum(act2[i] * params['w3'][i][j] for i in range(HIDDEN2)) + params['b3'][j] for j in range(OUTPUT_DIM)]
    return act1, act2, out

def mse(pred, target):
    diff = pred[0] - target
    return diff * diff

def compute_gradients(x, y, params):
    act1, act2, out = forward(x, params)
    diff = out[0] - y
    grad_w3 = [[act2[i] * 2 * diff for _ in range(OUTPUT_DIM)] for i in range(HIDDEN2)]
    grad_b3 = [2 * diff]
    grad_hidden2 = [2 * diff * params['w3'][i][0] for i in range(HIDDEN2)]
    grad_hidden2 = [grad_hidden2[i] * relu_grad([act2[i]])[0] for i in range(HIDDEN2)]
    grad_w2 = [[act1[i] * grad_hidden2[j] for j in range(HIDDEN2)] for i in range(HIDDEN1)]
    grad_b2 = grad_hidden2
    grad_hidden1 = [sum(grad_hidden2[j] * params['w2'][i][j] for j in range(HIDDEN2)) for i in range(HIDDEN1)]
    grad_hidden1 = [grad_hidden1[i] * relu_grad([act1[i]])[0] for i in range(HIDDEN1)]
    grad_w1 = [[x[d] * grad_hidden1[j] for j in range(HIDDEN1)] for d in range(INPUT_DIM)]
    grad_b1 = grad_hidden1
    return {'w1': grad_w1, 'b1': grad_b1, 'w2': grad_w2, 'b2': grad_b2, 'w3': grad_w3, 'b3': grad_b3}

def apply_gradients(params, grads, lrs):
    def mix(mat, grad, lr):
        return [[mat[i][j] - lr * grad[i][j] for j in range(len(mat[0]))] for i in range(len(mat))]
    def mix_bias(vec, grad, lr):
        return [vec[i] - lr * grad[i] for i in range(len(vec))]
    new_params = {
        'w1': mix(params['w1'], grads['w1'], lrs['w1']),
        'b1': mix_bias(params['b1'], grads['b1'], lrs['b1']),
        'w2': mix(params['w2'], grads['w2'], lrs['w2']),
        'b2': mix_bias(params['b2'], grads['b2'], lrs['b2']),
        'w3': mix(params['w3'], grads['w3'], lrs['w3']),
        'b3': mix_bias(params['b3'], grads['b3'], lrs['b3'])
    }
    return new_params

def evaluate(lrs):
    local = {k: [list(row) if isinstance(row, list) else row for row in base_params[k]] for k in base_params}
    total = 0.0
    for step in range(INNER_STEPS):
        idx = step % DATA_POINTS
        x = x_data[idx]
        y = y_data[idx]
        grads = compute_gradients(x, y, local)
        local = apply_gradients(local, grads, lrs)
        total += mse(forward(x, local)[2], y)
    return total / INNER_STEPS

population = []
for _ in range(POPULATION):
    population.append({
        'w1': random.uniform(0.02, 0.3),
        'b1': random.uniform(0.01, 0.25),
        'w2': random.uniform(0.01, 0.2),
        'b2': random.uniform(0.01, 0.3),
        'w3': random.uniform(0.01, 0.15),
        'b3': random.uniform(0.01, 0.35)
    })

best_record = []
print("=== Stronger Sandbox ES Experiment ===")
for gen in range(1, GENERATIONS + 1):
    evaluated = []
    for candidate in population:
        loss = evaluate(candidate)
        evaluated.append((loss, candidate))
    evaluated.sort(key=lambda x: x[0])
    top = evaluated[:TOP_K]
    best_loss, best_candidate = top[0]
    best_record.append((gen, best_loss, best_candidate))
    lr_str = ', '.join(f"{k}:{best_candidate[k]:.4f}" for k in best_candidate)
    print(f"Gen {gen:02d}: loss={best_loss:.5f}, lrs=({lr_str})")
    center = {k: mean(cand[k] for _, cand in top) for k in best_candidate}
    new_pop = []
    for _ in range(POPULATION):
        candidate = {k: max(1e-4, center[k] + random.gauss(0, 0.03)) for k in center}
        new_pop.append(candidate)
    population = new_pop

print("=== Experiment finished ===")
print(f"Final loss {best_record[-1][1]:.5f}, best lrs {best_record[-1][2]}")
