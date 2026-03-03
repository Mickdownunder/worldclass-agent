#!/usr/bin/env python3
import random
import math
from statistics import mean

random.seed(123456)
INPUT_DIM = 5
HIDDEN1 = 10
HIDDEN2 = 6
OUTPUT_DIM = 1
DATA_POINTS = 220
INNER_STEPS = 20
GENERATIONS = 22
POPULATION = 10
TOP_K = 4

x_data = [[random.uniform(-2, 2) for _ in range(INPUT_DIM)] for _ in range(DATA_POINTS)]
y_data = [math.tanh(sum(row) * 0.3) * 0.5 + 0.5 for row in x_data]

base_params = {
    'w1': [[random.uniform(-0.2, 0.2) for _ in range(HIDDEN1)] for _ in range(INPUT_DIM)],
    'b1': [0.0] * HIDDEN1,
    'w2': [[random.uniform(-0.2, 0.2) for _ in range(HIDDEN2)] for _ in range(HIDDEN1)],
    'b2': [0.0] * HIDDEN2,
    'w3': [[random.uniform(-0.25, 0.25) for _ in range(OUTPUT_DIM)] for _ in range(HIDDEN2)],
    'b3': [0.0] * OUTPUT_DIM,
    'att': [random.uniform(-0.1, 0.1) for _ in range(HIDDEN2)]
}

PLAYBACK = []

def relu(v):
    return [max(0.0, x) for x in v]

def relu_grad(v):
    return [1.0 if x > 0.0 else 0.0 for x in v]

def forward(x, params):
    h1 = [sum(x[i] * params['w1'][i][j] for i in range(INPUT_DIM)) + params['b1'][j] for j in range(HIDDEN1)]
    a1 = relu(h1)
    h2 = [sum(a1[i] * params['w2'][i][j] for i in range(HIDDEN1)) + params['b2'][j] for j in range(HIDDEN2)]
    a2 = relu(h2)
    att_score = sum(a2) / HIDDEN2
    att_output = [att_score * params['att'][j] for j in range(HIDDEN2)]
    full_activation = [a2[j] + att_output[j] for j in range(HIDDEN2)]
    out = [sum(full_activation[i] * params['w3'][i][j] for i in range(HIDDEN2)) + params['b3'][j] for j in range(OUTPUT_DIM)]
    return a1, a2, full_activation, att_score, out

def mse(pred, target):
    diff = pred[0] - target
    return diff * diff

def compute_gradients(x, y, params):
    a1, a2, full_act, att_score, out = forward(x, params)
    diff = out[0] - y
    d_out = 2 * diff
    grad_w3 = [[full_act[i] * d_out for _ in range(OUTPUT_DIM)] for i in range(HIDDEN2)]
    grad_b3 = [d_out]
    grad_full_act = [d_out * params['w3'][i][0] for i in range(HIDDEN2)]
    grad_att = [d_out * att_score for _ in range(HIDDEN2)]
    # contribution from att output to a2
    grad_a2_from_att = [sum(params['att'][j] * d_out for j in range(HIDDEN2)) / HIDDEN2 for _ in range(HIDDEN2)]
    grad_a2 = [grad_full_act[i] + grad_a2_from_att[i] for i in range(HIDDEN2)]
    grad_h2 = [grad_a2[i] * relu_grad([a2[i]])[0] for i in range(HIDDEN2)]
    grad_w2 = [[a1[i] * grad_h2[j] for j in range(HIDDEN2)] for i in range(HIDDEN1)]
    grad_b2 = grad_h2
    grad_h1 = [sum(grad_h2[j] * params['w2'][i][j] for j in range(HIDDEN2)) for i in range(HIDDEN1)]
    grad_h1 = [grad_h1[i] * relu_grad([a1[i]])[0] for i in range(HIDDEN1)]
    grad_w1 = [[x[d] * grad_h1[j] for j in range(HIDDEN1)] for d in range(INPUT_DIM)]
    grad_b1 = grad_h1
    return {
        'w1': grad_w1,
        'b1': grad_b1,
        'w2': grad_w2,
        'b2': grad_b2,
        'w3': grad_w3,
        'b3': grad_b3,
        'att': grad_att
    }

def norm(values):
    return sum(abs(v) for v in values) / max(1, len(values))

def apply_gradients(params, grads, lrs):
    def mix(mat, grad, lr):
        return [[mat[i][j] - lr * grad[i][j] for j in range(len(mat[0]))] for i in range(len(mat))]
    def mix_bias(vec, grad, lr):
        return [vec[i] - lr * grad[i] for i in range(len(vec))]
    return {
        'w1': mix(params['w1'], grads['w1'], lrs['w1']),
        'b1': mix_bias(params['b1'], grads['b1'], lrs['b1']),
        'w2': mix(params['w2'], grads['w2'], lrs['w2']),
        'b2': mix_bias(params['b2'], grads['b2'], lrs['b2']),
        'w3': mix(params['w3'], grads['w3'], lrs['w3']),
        'b3': mix_bias(params['b3'], grads['b3'], lrs['b3']),
        'att': mix_bias(params['att'], grads['att'], lrs['att'])
    }

def adjust_lr(base, grad_magn, sparse, g_thresh, g_scale, s_thresh, s_scale):
    lr = base
    if grad_magn > g_thresh:
        lr *= 1 + g_scale
    if sparse > s_thresh:
        lr *= 1 + s_scale
    return lr

def evaluate(candidate):
    local = {k: [list(row) if isinstance(row, list) else row for row in base_params[k]] for k in base_params}
    total = 0.0
    for step in range(INNER_STEPS):
        idx = step % DATA_POINTS
        x = x_data[idx]
        y = y_data[idx]
        grads = compute_gradients(x, y, local)
        grad_magnitudes = {
            'w1': norm([sum(abs(val) for val in row) for row in grads['w1']]),
            'w2': norm([sum(abs(val) for val in row) for row in grads['w2']]),
            'w3': norm([sum(abs(val) for val in row) for row in grads['w3']])
        }
        sparsities = {
            'b1': sum(1 for g in grads['b1'] if abs(g) < 1e-6) / len(grads['b1']),
            'b2': sum(1 for g in grads['b2'] if abs(g) < 1e-6) / len(grads['b2']),
            'b3': sum(1 for g in grads['b3'] if abs(g) < 1e-6) / len(grads['b3'])
        }
        lrs = {
            'w1': adjust_lr(candidate['w1'], grad_magnitudes['w1'], sparsities['b1'], candidate['g_thresh'], candidate['g_scale'], candidate['s_thresh'], candidate['s_scale']),
            'b1': adjust_lr(candidate['b1'], grad_magnitudes['w1'], sparsities['b1'], candidate['g_thresh'], candidate['g_scale'], candidate['s_thresh'], candidate['s_scale']),
            'w2': adjust_lr(candidate['w2'], grad_magnitudes['w2'], sparsities['b2'], candidate['g_thresh'], candidate['g_scale'], candidate['s_thresh'], candidate['s_scale']),
            'b2': adjust_lr(candidate['b2'], grad_magnitudes['w2'], sparsities['b2'], candidate['g_thresh'], candidate['g_scale'], candidate['s_thresh'], candidate['s_scale']),
            'w3': adjust_lr(candidate['w3'], grad_magnitudes['w3'], sparsities['b3'], candidate['g_thresh'], candidate['g_scale'], candidate['s_thresh'], candidate['s_scale']),
            'b3': adjust_lr(candidate['b3'], grad_magnitudes['w3'], sparsities['b3'], candidate['g_thresh'], candidate['g_scale'], candidate['s_thresh'], candidate['s_scale']),
            'att': adjust_lr(candidate['att'], grad_magnitudes['w3'], sparsities['b3'], candidate['g_thresh'], candidate['g_scale'], candidate['s_thresh'], candidate['s_scale'])
        }
        local = apply_gradients(local, grads, lrs)
        total += mse(forward(x, local)[4], y)
    return total / INNER_STEPS

population = []
for _ in range(POPULATION):
    population.append({
        'w1': random.uniform(0.01, 0.25),
        'b1': random.uniform(0.01, 0.25),
        'w2': random.uniform(0.01, 0.2),
        'b2': random.uniform(0.01, 0.25),
        'w3': random.uniform(0.01, 0.15),
        'b3': random.uniform(0.01, 0.3),
        'att': random.uniform(0.01, 0.2),
        'g_thresh': random.uniform(0.6, 1.3),
        'g_scale': random.uniform(0.2, 0.7),
        's_thresh': random.uniform(0.2, 0.8),
        's_scale': random.uniform(0.2, 0.7)
    })

print("+++ Attention Context ES Experiment +++")
best = None
for gen in range(1, GENERATIONS + 1):
    evaluated = [(evaluate(cand), cand) for cand in population]
    evaluated.sort(key=lambda x: x[0])
    top = evaluated[:TOP_K]
    loss, champion = top[0]
    config_str = ', '.join(f"{k}:{champion[k]:.3f}" for k in champion)
    print(f"Gen {gen:02d}: loss {loss:.5f}, {config_str}")
    best = (loss, champion)
    center = {k: mean(item[1][k] for item in top) for k in champion}
    population = [{k: max(1e-4, center[k] + random.gauss(0, 0.03)) for k in center} for _ in range(POPULATION)]

print("+++ Done +++")
print(f"Best loss {best[0]:.5f} with config {best[1]}")
