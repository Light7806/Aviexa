"""
demo/planted_bugs/bug_vanishing_gradient.py
Planted bug: deep sigmoid network — all activations saturate, gradients vanish.

THE BUG:  uses sigmoid activation in a deep stack (8 layers)
THE FIX:  replace sigmoid with ReLU, or use BatchNorm + careful init
"""

import torch
import torch.nn as nn

torch.manual_seed(1)
N = 128
X = torch.randn(N, 16)
Y = torch.randint(0, 2, (N,)).float()


class VanishingNet(nn.Module):
    """8-layer sigmoid stack — classic vanishing gradient setup."""
    def __init__(self):
        super().__init__()
        layers = []
        dims = [16, 64, 64, 64, 64, 64, 64, 32, 1]
        for i in range(len(dims) - 1):
            layers.append(nn.Linear(dims[i], dims[i + 1]))
            if i < len(dims) - 2:
                layers.append(nn.Sigmoid())   # BUG: should be ReLU
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x).squeeze(1)


model     = VanishingNet()
optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
criterion = nn.BCEWithLogitsLoss()
BATCH     = 32

print("bug_vanishing_gradient.py: 8-layer sigmoid stack (vanishing gradients expected)")
for step in range(10):
    idx  = torch.randint(0, N, (BATCH,))
    xb, yb = X[idx], Y[idx]
    optimizer.zero_grad()
    loss = criterion(model(xb), yb)
    loss.backward()

    grads = [p.grad.abs().mean().item() for p in model.parameters() if p.grad is not None]
    min_g = min(grads)
    max_g = max(grads)
    print(f"  Step {step+1:2d}  loss={loss.item():.4f}  grad min={min_g:.2e}  max={max_g:.2e}")
    optimizer.step()

print("\nExpected: near-zero gradients in early layers → vanishing gradient anomaly.")
print("Fix: replace Sigmoid with ReLU and add BatchNorm.")
