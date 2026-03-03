#!/usr/bin/env python3
import math
import time
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW
from torch.utils.data import DataLoader, TensorDataset
from lion_pytorch import Lion
from datasets import load_dataset

DEVICE = torch.device('cpu')
SEQ_LEN = 64
BATCH_SIZE = 16
EPOCHS = 1
LAYERS = 12
EMBED_DIM = 128
BASE_LR = 1e-3
WEIGHT_DECAY = 1e-4
TOKEN_LIMIT = 2048

torch.manual_seed(12345)

class MiniTransformer(nn.Module):
    def __init__(self, vocab_size):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, EMBED_DIM)
        self.pos = nn.Embedding(SEQ_LEN, EMBED_DIM)
        layer = nn.TransformerEncoderLayer(EMBED_DIM, 4, 256, dropout=0.1)
        self.transformer = nn.TransformerEncoder(layer, num_layers=LAYERS)
        self.out = nn.Linear(EMBED_DIM, vocab_size)

    def forward(self, x):
        b, t = x.shape
        pos = torch.arange(t, device=x.device).unsqueeze(0).expand(b, -1)
        h = self.embed(x) + self.pos(pos)
        h = h.transpose(0, 1)
        h = self.transformer(h)
        h = h.transpose(0, 1)
        return self.out(h)


def build_dataset(limit=TOKEN_LIMIT):
    ds = load_dataset('wikitext', 'wikitext-2-raw-v1', split='train[:2%]')
    text = '\n'.join(ds['text'][:150])
    chars = sorted({c for line in text for c in line})
    stoi = {ch: i for i, ch in enumerate(chars)}
    tokens = [stoi[c] for c in text if c in stoi]
    sequences = []
    for i in range(len(tokens) - SEQ_LEN):
        chunk = tokens[i:i + SEQ_LEN]
        target = tokens[i + 1:i + SEQ_LEN + 1]
        sequences.append((chunk, target))
    inputs = torch.tensor([s[0] for s in sequences], dtype=torch.long)
    targets = torch.tensor([s[1] for s in sequences], dtype=torch.long)
    if inputs.size(0) > limit:
        inputs = inputs[:limit]
        targets = targets[:limit]
    return TensorDataset(inputs, targets), len(stoi)


def evaluate(model, dataset):
    model.eval()
    loader = DataLoader(dataset, batch_size=BATCH_SIZE)
    total = 0.0
    tokens = 0
    with torch.no_grad():
        for x, y in loader:
            x = x.to(DEVICE)
            y = y.to(DEVICE)
            logits = model(x)
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), y.view(-1))
            total += loss.item() * x.numel()
            tokens += x.numel()
    return total / max(1, tokens)


def compute_grad_norm(model):
    return math.sqrt(sum(p.grad.norm().item() ** 2 for p in model.parameters() if p.grad is not None))


def compute_update_norm(pre, post):
    accum = 0.0
    for p_pre, p_post in zip(pre, post):
        diff = (p_post - p_pre).detach()
        accum += diff.norm().item() ** 2
    return math.sqrt(accum)


def tokens_to_flops(tokens):
    return tokens * SEQ_LEN * EMBED_DIM * 2 * LAYERS


def run_seed(opt_name):
    dataset, vocab_size = build_dataset()
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
    model = MiniTransformer(vocab_size).to(DEVICE)

    if opt_name == 'AdamW':
        optimizer = AdamW(model.parameters(), lr=BASE_LR, weight_decay=WEIGHT_DECAY)
        policy_type = 'none'
    elif opt_name == 'Lion':
        optimizer = Lion(model.parameters(), lr=BASE_LR, weight_decay=WEIGHT_DECAY)
        policy_type = 'none'
    elif opt_name == 'ES':
        optimizer = AdamW(model.parameters(), lr=BASE_LR, weight_decay=WEIGHT_DECAY)
        policy_type = 'es'
    else:  # reflective
        layer_groups = []
        for idx, layer in enumerate(model.transformer.layers):
            layer_groups.append({'params': layer.parameters(), 'layer_id': f'layer_{idx}'})
        layer_groups.append({'params': model.embed.parameters(), 'layer_id': 'embed'})
        layer_groups.append({'params': model.out.parameters(), 'layer_id': 'out'})
        optimizer = AdamW(layer_groups, lr=BASE_LR, weight_decay=WEIGHT_DECAY)
        policy_type = 'reflective'

    tokens_seen = 0
    grad_norms = []
    update_norms = []
    divergences = 0
    policy_outputs = {}
    policy_inputs = []

    layer_multipliers = {group.get('layer_id', f'group_{i}'): 1.0 for i, group in enumerate(optimizer.param_groups)}
    threshold = 1.1
    scale = 0.4

    start_time = time.time()
    for epoch in range(EPOCHS):
        model.train()
        for x, y in loader:
            x = x.to(DEVICE)
            y = y.to(DEVICE)
            optimizer.zero_grad()
            logits = model(x)
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), y.view(-1))
            loss.backward()
            grad_norm = compute_grad_norm(model)
            grad_norms.append(grad_norm)
            pre_params = [p.detach().clone() for p in model.parameters() if p.requires_grad]
            if policy_type in ('es', 'reflective'):
                step_info = {'grad_norm': grad_norm}
            optimizer.step()
            post_params = [p.detach() for p in model.parameters() if p.requires_grad]
            update_norm = compute_update_norm(pre_params, post_params)
            update_norms.append(update_norm)
            if torch.isnan(loss) or torch.isinf(loss):
                divergences += 1
            tokens_seen += x.numel()
            if policy_type == 'es':
                if grad_norm > threshold:
                    for group in optimizer.param_groups:
                        group['lr'] = group['lr'] * (1 + scale)
                else:
                    for group in optimizer.param_groups:
                        group['lr'] = max(1e-6, group['lr'] * 0.99)
            elif policy_type == 'reflective':
                layer_grads = []
                for group in optimizer.param_groups:
                    group_norm = 0.0
                    count = 0
                    for p in group['params']:
                        if p.grad is not None:
                            group_norm += p.grad.norm().item() ** 2
                            count += 1
                    if count:
                        group_norm = math.sqrt(group_norm)
                    layer_grads.append(group_norm)
                policy_inputs.append(layer_grads)
                for idx, group in enumerate(optimizer.param_groups):
                    lid = group.get('layer_id', f'group_{idx}')
                    grad_value = layer_grads[idx]
                    if grad_value > threshold:
                        layer_multipliers[lid] *= 1 + scale
                    else:
                        layer_multipliers[lid] *= 0.98
                    group['lr'] = BASE_LR * layer_multipliers[lid]
                policy_outputs = layer_multipliers.copy()
    wall_time = time.time() - start_time
    val_loss = evaluate(model, dataset)
    val_ppl = math.exp(val_loss)
    metrics = {
        'optimizer': opt_name,
        'val_loss': val_loss,
        'val_ppl': val_ppl,
        'tokens': tokens_seen,
        'wall_time': wall_time,
        'flops_proxy': tokens_to_flops(tokens_seen),
        'avg_grad_norm': sum(grad_norms) / max(1, len(grad_norms)),
        'avg_update_norm': sum(update_norms) / max(1, len(update_norms)),
        'divergences': divergences,
        'policy_outputs': policy_outputs,
        'policy_inputs': policy_inputs,
        'policy_type': policy_type,
    }
    return metrics


def main():
    print('*** Block 1 / Seed 1: baseline comparison ***')
    results = []
    for name in ['AdamW', 'Lion', 'ES', 'reflective']:
        metrics = run_seed(name)
        results.append(metrics)
        print(metrics)

if __name__ == '__main__':
    main()
