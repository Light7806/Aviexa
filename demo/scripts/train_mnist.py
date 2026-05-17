"""
demo/scripts/train_mnist.py
Healthy baseline training on SYNTHETIC tensors (no download needed).
Produces stable loss + gradients — Aviexa should show all green.
"""

import torch
import torch.nn as nn

# ── Synthetic "MNIST-like" dataset ────────────────────────────────────────────
torch.manual_seed(42)
N, C, H, W = 256, 1, 28, 28
X = torch.randn(N, C, H, W)
Y = torch.randint(0, 10, (N,))


class SmallCNN(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv = nn.Conv2d(1, 8, 3, padding=1)
        self.pool = nn.AdaptiveAvgPool2d(4)
        self.fc   = nn.Linear(8 * 4 * 4, 10)

    def forward(self, x):
        x = torch.relu(self.conv(x))
        x = self.pool(x)
        return self.fc(x.flatten(1))


model     = SmallCNN()
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)   # healthy LR
criterion = nn.CrossEntropyLoss()
BATCH     = 32

print("train_mnist.py: healthy baseline (synthetic MNIST-like data)")
for epoch in range(3):
    for start in range(0, N, BATCH):
        xb = X[start:start + BATCH]
        yb = Y[start:start + BATCH]
        optimizer.zero_grad()
        loss = criterion(model(xb), yb)
        loss.backward()
        optimizer.step()
    print(f"  Epoch {epoch+1}/3  loss={loss.item():.4f}")

print("Done — no anomalies expected.")
