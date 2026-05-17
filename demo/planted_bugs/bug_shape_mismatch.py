"""
demo/planted_bugs/bug_shape_mismatch.py
Planted bug: Linear layer input dimension mismatch (256 vs actual 128).

THE BUG:  self.fc = nn.Linear(256, 10)  — backbone outputs 128
THE FIX:  self.fc = nn.Linear(128, 10)
"""

import torch
import torch.nn as nn

torch.manual_seed(2)


class MismatchedNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.backbone = nn.Linear(16, 128)    # outputs 128 features

        # ── THE BUG: expects 256 inputs but backbone gives 128 ──────────────
        self.fc = nn.Linear(256, 10)          # BUG: should be nn.Linear(128, 10)

    def forward(self, x):
        features = torch.relu(self.backbone(x))
        return self.fc(features)              # RuntimeError: mat1 dim 1 must match mat2 dim 0


model = MismatchedNet()
X = torch.randn(8, 16)

print("bug_shape_mismatch.py: demonstrating Linear dimension mismatch")
print(f"  backbone output shape: {model.backbone(X).shape}")
print(f"  fc expects input dim : 256  (BUG — should be 128)")

try:
    out = model(X)
    print(f"  output shape: {out.shape}")
except RuntimeError as e:
    print(f"\n[EXPECTED ERROR] {e}")
    print("\nFix: change  self.fc = nn.Linear(256, 10)  to  self.fc = nn.Linear(128, 10)")
