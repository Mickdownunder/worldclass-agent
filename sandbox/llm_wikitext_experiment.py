#!/usr/bin/env python3
import torch
import torch.nn as nn
import torch.nn.functional as F
from datasets import load_dataset
from torch.utils.data import DataLoader, TensorDataset
import math
from pathlib import Path

DEVICE = torch.device('cpu')
SEQ_LEN = 64
BATCH_SIZE = 16
EPOCHS = 2
CANDIDATES = [
    {'threshold': 0.8, 'scale': 0.45},
    {'threshold': 1.0, 'scale': 0.35},
    {'threshold': 0.65, 'scale': 0.55}
]

class TinyTransformer(nn.Module):
    def __init__(self, vocab_size, embed_dim=64, num_heads=4, ff=128, layers=2):
        super().__init__()
        self.embed = nn.Embedding(vocab_size, embed_dim)
        self.pos = nn.Embedding(SEQ_LEN, embed_dim)
        encoder_layer = nn.TransformerEncoderLayer(embed_dim, num_heads, ff, dropout=0.1)
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


def build_tokenizer(text):
    chars = sorted(set(text))
    stoi = {ch: i for i, ch in enumerate(chars)}
    itos = {i: ch for ch, i in stoi.items()}
    return stoi, itos


def prepare_dataset(stoi):
    dataset = load_dataset('wikitext', 'wikitext-2-raw-v1', split='train[:1%]')
    text = '\n'.join(dataset['text'][:50])
    tokens = [stoi[ch] for ch in text if ch in stoi]
    sequences = []
    for i in range(0, len(tokens) - SEQ_LEN):
        chunk = tokens[i:i+SEQ_LEN]
        target = tokens[i+1:i+SEQ_LEN+1]
        sequences.append((chunk, target))
    chunks = torch.tensor([s[0] for s in sequences], dtype=torch.long)
    targets = torch.tensor([s[1] for s in sequences], dtype=torch.long)
    return TensorDataset(chunks, targets)


def train_candidate(candidate, model, dataset):
    dataloader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True)
    base_lr = 1e-3
    optimizer = torch.optim.Adam(model.parameters(), lr=base_lr)
    model.train()
    total_loss = 0.0
    total_tokens = 0
    for epoch in range(EPOCHS):
        for x, y in dataloader:
            x = x.to(DEVICE)
            y = y.to(DEVICE)
            optimizer.zero_grad()
            logits = model(x)
            loss = F.cross_entropy(logits.view(-1, logits.size(-1)), y.view(-1))
            loss.backward()
            grad_norm = math.sqrt(sum(p.grad.norm().item() ** 2 for p in model.parameters() if p.grad is not None))
            sparsity = sum((p.grad.abs() < 1e-5).float().mean().item() for p in model.parameters() if p.grad is not None) / len([p for p in model.parameters() if p.grad is not None])
            scale = 1.0 + candidate['scale'] * max(0.0, grad_norm - candidate['threshold'])
            if sparsity > candidate['threshold']:
                scale += candidate['scale'] * (sparsity - candidate['threshold'])
            for group in optimizer.param_groups:
                group['lr'] = base_lr * scale
            optimizer.step()
            total_loss += loss.item() * x.size(0)
            total_tokens += x.numel()
    return total_loss / total_tokens


def main():
    raw_dataset = load_dataset('wikitext', 'wikitext-2-raw-v1', split='train[:1%]')
    text = '\n'.join(raw_dataset['text'][:20])
    stoi, itos = build_tokenizer(text)
    dataset = prepare_dataset(stoi)
    vocab_size = len(stoi)
    best = None
    for candidate in CANDIDATES:
        model = TinyTransformer(vocab_size).to(DEVICE)
        loss = train_candidate(candidate, model, dataset)
        ppl = math.exp(loss)
        print(f"Candidate (thr={candidate['threshold']:.2f}, scale={candidate['scale']:.2f}) -> avg loss {loss:.4f}, ppl {ppl:.2f}")
        if best is None or loss < best[0]:
            best = (loss, ppl, candidate)
    print("=== LLM Proto Done ===")
    print(f"Best loss {best[0]:.4f}, ppl {best[1]:.2f}, config {best[2]}")

if __name__ == '__main__':
    main()
