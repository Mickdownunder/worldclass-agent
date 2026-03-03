#!/usr/bin/env python3
import torch
import torch.nn as nn
import torch.nn.functional as F
from datasets import load_dataset
from torch.utils.data import DataLoader, TensorDataset
import math

random_seed = 314159
torch.manual_seed(random_seed)

DEVICE = torch.device('cpu')
SEQ_LEN = 96
BATCH_SIZE = 12
EPOCHS = 3
CANDIDATES = [
    {'threshold': 0.9, 'scale': 0.35},
    {'threshold': 0.7, 'scale': 0.48},
    {'threshold': 1.1, 'scale': 0.30},
    {'threshold': 0.85, 'scale': 0.55}
]

class MiniTransformer(nn.Module):
    def __init__(self, vocab_size, embed_dim=128, nhead=4, dim_feedforward=256, layers=3):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, embed_dim)
        self.pos = nn.Embedding(SEQ_LEN, embed_dim)
        encoder_layer = nn.TransformerEncoderLayer(embed_dim, nhead, dim_feedforward, dropout=0.1)
        self.transformer = nn.TransformerEncoder(encoder_layer, layers)
        self.out = nn.Linear(embed_dim, vocab_size)

    def forward(self, x):
        b, t = x.shape
        positions = torch.arange(t, device=x.device).unsqueeze(0).expand(b, -1)
        h = self.embed(x) + self.pos(positions)
        h = h.transpose(0, 1)
        h = self.transformer(h)
        h = h.transpose(0, 1)
        return self.out(h)


def build_tokenizer(raw):
    chars = sorted({c for line in raw for c in line})
    stoi = {ch: i for i, ch in enumerate(chars)}
    return stoi


def make_sequences(stoi):
    dataset = load_dataset('wikitext', 'wikitext-2-raw-v1', split='train[:2%]')
    text = '\n'.join(dataset['text'][:60])
    tokens = [stoi[c] for c in text if c in stoi]
    sequences = []
    for i in range(len(tokens) - SEQ_LEN):
        chunk = tokens[i:i+SEQ_LEN]
        target = tokens[i+1:i+SEQ_LEN+1]
        sequences.append((chunk, target))
    inputs = torch.tensor([s[0] for s in sequences], dtype=torch.long)
    targets = torch.tensor([s[1] for s in sequences], dtype=torch.long)
    return TensorDataset(inputs, targets)


def adjust_lr(base, grad_norm, sparsity, threshold, scale):
    lr = base
    if grad_norm > threshold:
        lr *= 1 + scale
    if sparsity > threshold * 0.5:
        lr *= 1 + scale * 0.5
    return lr


def evaluate(candidate, model, dataset):
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    total = 0.0
    tokens = 0
    for epoch in range(EPOCHS):
        for x, y in loader:
            x = x.to(DEVICE)
            y = y.to(DEVICE)
            optimizer.zero_grad()
            logits = model(x)
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), y.view(-1))
            loss.backward()
            grad_norm = math.sqrt(sum(p.grad.norm().item() ** 2 for p in model.parameters() if p.grad is not None))
            sparsity = sum((p.grad.abs() < 1e-4).float().mean().item() for p in model.parameters() if p.grad is not None)
            sparsity /= max(1, len([p for p in model.parameters() if p.grad is not None]))
            lr = adjust_lr(1e-3, grad_norm, sparsity, candidate['threshold'], candidate['scale'])
            for group in optimizer.param_groups:
                group['lr'] = lr
            optimizer.step()
            total += loss.item() * x.size(0)
            tokens += x.numel()
    return total / tokens


def main():
    dataset = load_dataset('wikitext', 'wikitext-2-raw-v1', split='train[:1%]')
    raw_text = '\n'.join(dataset['text'][:30])
    stoi = build_tokenizer(raw_text)
    data = make_sequences(stoi)
    vocab_size = len(stoi)
    best = None
    for candidate in CANDIDATES:
        model = MiniTransformer(vocab_size).to(DEVICE)
        loss = evaluate(candidate, model, data)
        ppl = math.exp(loss)
        print(f"Candidate thr={candidate['threshold']:.2f}, scale={candidate['scale']:.2f} -> loss={loss:.4f}, ppl={ppl:.2f}")
        if best is None or loss < best[0]:
            best = (loss, ppl, candidate)
    print("=== Large LLM Proto Done ===")
    print(f"Best loss {best[0]:.4f}, ppl {best[1]:.2f}, config {best[2]}")

if __name__ == '__main__':
    main()
