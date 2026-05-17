"""
demo/planted_bugs/bug_gradient_explosion.py
Planted bug: learning rate = 100.0 (should be 0.001) + no gradient clipping.
Produces gradient norm spikes that Aviexa detects as GRADIENT_EXPLOSION.

THE BUG (line 18):  lr=100.0
THE FIX:            lr=0.001 + clip_grad_norm_(model.parameters(), max_norm=1.0)
"""

import torch
import torch.nn as nn

torch.manual_seed(0)
N = 128
X = torch.randn(N, 16)
Y = torch.randint(0, 2, (N,)).float()


class BuggyNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(16, 64)
        self.fc2 = nn.Linear(64, 1)

    def forward(self, x):
        return self.fc2(torch.relu(self.fc1(x))).squeeze(1)


model = BuggyNet()

# ── THE BUG: learning rate is 100,000× too high ──────────────────────────────
optimizer = torch.optim.SGD(model.parameters(), lr=100.0)  # BUG: should be 0.001
# ── MISSING: torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

criterion = nn.BCEWithLogitsLoss()
BATCH = 32

print("bug_gradient_explosion.py: intentionally broken training (lr=100.0, no clipping)")
for step in range(10):
    idx  = torch.randint(0, N, (BATCH,))
    xb, yb = X[idx], Y[idx]
    optimizer.zero_grad()
    loss = criterion(model(xb), yb)
    loss.backward()

    gnorm = sum(p.grad.norm().item() ** 2 for p in model.parameters() if p.grad is not None) ** 0.5
    print(f"  Step {step+1:2d}  loss={loss.item():.4f}  grad_norm={gnorm:.2f}")

    optimizer.step()

print("\nExpected: gradient explosion detected by Aviexa around step 1-3.")
print("Fix: reduce lr to 0.001 and add clip_grad_norm_(model.parameters(), max_norm=1.0)")
