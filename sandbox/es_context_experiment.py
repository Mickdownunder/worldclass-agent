#!/usr/bin/env python3
import random
import math
from statistics import mean

random.seed(271828)
INPUT_DIM = 5
HIDDEN1 = 12
HIDDEN2 = 6
OUTPUT_DIM = 1
DATA_POINTS = 200
INNER_STEPS = 15
GENERATIONS = 28
POPULATION = 10
TOP_K = 4

# synthetic dataset
x_data = [[random.uniform(-2, 2) for _ in range(INPUT_DIM)] for _ in range(DATA_POINTS)]
y_data = [math.tanh(sum(row) * 0.35) * 0.5 + 0.5 for row in x_data]

base_params = {
    'w1': [[random.uniform(-0.2, 0.2) for _ in range(HIDDEN1)] for _ in range(INPUT_DIM)],
    'b1': [0.0] * HIDDEN1,
    'w2': [[random.uniform(-0.2, 0.2) for _ in range(HIDDEN2)] for _ in range(HIDDEN1)],
    'b2': [0.0] * HIDDEN2,
    'w3': [[random.uniform(-0.25, 0.25) for _ in range(OUTPUT_DIM)] for _ in range(HIDDEN2)],
    'b3': [0.0] * OUTPUT_DIM
}

# activations
def relu(v):
    return [max(0.0, x) for x in v]

def relu_grad(v):
    return [1.0 if x > 0 else 0.0 for x in v]

# propagation
def forward(x, params):
    h1 = [sum(x[i] * params['w1'][i][j] for i in range(INPUT_DIM)) + params['b1'][j] for j in range(HIDDEN1)]
    a1 = relu(h1)
    h2 = [sum(a1[i] * params['w2'][i][j] for i in range(HIDDEN1)) + params['b2'][j] for j in range(HIDDEN2)]
    a2 = relu(h2)
    out = [sum(a2[i] * params['w3'][i][j] for i in range(HIDDEN2)) + params['b3'][j] for j in range(OUTPUT_DIM)]
    return a1, a2, out

def mse(pred, target):
    diff = pred[0] - target
    return diff * diff

def gradients(x, y, params):
    a1, a2, out = forward(x, params)
    diff = out[0] - y
    grad_w3 = [[a2[i] * 2 * diff for _ in range(OUTPUT_DIM)] for i in range(HIDDEN2)]
    grad_b3 = [2 * diff]
    grad_h2 = [2 * diff * params['w3'][i][0] for i in range(HIDDEN2)]
    grad_h2 = [grad_h2[i] * relu_grad([a2[i]])[0] for i in range(HIDDEN2)]
    grad_w2 = [[a1[i] * grad_h2[j] for j in range(HIDDEN2)] for i in range(HIDDEN1)]
    grad_b2 = grad_h2
    grad_h1 = [sum(grad_h2[j] * params['w2'][i][j] for j in range(HIDDEN2)) for i in range(HIDDEN1)]
    grad_h1 = [grad_h1[i] * relu_grad([a1[i]])[0] for i in range(HIDDEN1)]
    grad_w1 = [[x[d] * grad_h1[j] for j in range(HIDDEN1)] for d in range(INPUT_DIM)]
    grad_b1 = grad_h1
    return {'w1': grad_w1, 'b1': grad_b1, 'w2': grad_w2, 'b2': grad_b2, 'w3': grad_w3, 'b3': grad_b3}

def apply_gradients(params, grads, lrs):
    def mix(matrix, grad, lr):
        return [[matrix[i][j] - lr * grad[i][j] for j in range(len(matrix[0]))] for i in range(len(matrix))]
    def mix_bias(vec, grad, lr):
        return [vec[i] - lr * grad[i] for i in range(len(vec))]
    return {
        'w1': mix(params['w1'], grads['w1'], lrs['w1']),
        'b1': mix_bias(params['b1'], grads['b1'], lrs['b1']),
        'w2': mix(params['w2'], grads['w2'], lrs['w2']),
        'b2': mix_bias(params['b2'], grads['b2'], lrs['b2']),
        'w3': mix(params['w3'], grads['w3'], lrs['w3']),
        'b3': mix_bias(params['b3'], grads['b3'], lrs['b3'])
    }

def adjust_lr(base, context, threshold, scale):
    magnitude = sum(abs(v) for v in context) / len(context)
    if magnitude > threshold:
        return base * (1.0 + scale)
    return base

def evaluate(candidate):
    local = {k: [list(row) if isinstance(row, list) else row for row in base_params[k]] for k in base_params}
    total = 0.0
    for step in range(INNER_STEPS):
        idx = step % DATA_POINTS
        x = x_data[idx]
        y = y_data[idx]
        grads = gradients(x, y, local)
        lrs = {
            'w1': adjust_lr(candidate['w1'], grads['w1'][0], candidate['t1'], candidate['s1']),
            'b1': adjust_lr(candidate['b1'], grads['b1'], candidate['t1'], candidate['s1']),
            'w2': adjust_lr(candidate['w2'], grads['w2'][0], candidate['t2'], candidate['s2']),
            'b2': adjust_lr(candidate['b2'], grads['b2'], candidate['t2'], candidate['s2']),
            'w3': adjust_lr(candidate['w3'], grads['w3'][0], candidate['t3'], candidate['s3']),
            'b3': adjust_lr(candidate['b3'], grads['b3'], candidate['t3'], candidate['s3'])
        }
        local = apply_gradients(local, grads, lrs)
        total += mse(forward(x, local)[2], y)
    return total / INNER_STEPS

population = []
for _ in range(POPULATION):
    population.append({
        'w1': random.uniform(0.01, 0.25),
        'b1': random.uniform(0.01, 0.25),
        'w2': random.uniform(0.01, 0.2),
        'b2': random.uniform(0.01, 0.3),
        'w3': random.uniform(0.01, 0.15),
        'b3': random.uniform(0.01, 0.35),
        't1': random.uniform(0.5, 1.2),
        's1': random.uniform(0.2, 0.8),
        't2': random.uniform(0.5, 1.2),
        's2': random.uniform(0.2, 0.8),
        't3': random.uniform(0.5, 1.2),
        's3': random.uniform(0.2, 0.8)
    })

print("### Context-aware ES Experiment ###")
best = None
for gen in range(1, GENERATIONS + 1):
    evaluated = [(evaluate(cand), cand) for cand in population]
    evaluated.sort(key=lambda x: x[0])
    top = evaluated[:TOP_K]
    loss, champ = top[0]
    lr_details = ', '.join(f"{k}:{champ[k]:.3f}" for k in champ)
    print(f"Gen {gen:02d}: loss {loss:.5f}, config=({lr_details})")
    best = (loss, champ)
    center = {k: mean(item[1][k] for item in top) for k in champ}
    population = [{k: max(1e-4, center[k] + random.gauss(0, 0.04)) for k in center} for _ in range(POPULATION)]

print("### Experiment done ###")
print(f"Best loss {best[0]:.5f} with config {best[1]}")
