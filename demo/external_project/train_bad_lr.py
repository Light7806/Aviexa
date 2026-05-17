#!/usr/bin/env python3
"""
External training script with intentional gradient explosion.

This script demonstrates how external projects can integrate with Aviexa
by emitting telemetry JSON lines to stdout in the format:
    AVIEXA_TELEMETRY: {"event_type": "loss", ...}

The script intentionally uses a too-high learning rate (10.0) to trigger
gradient explosion, which Aviexa should detect.
"""

import json
import sys
import torch
import torch.nn as nn
import torch.optim as optim


class SimpleNet(nn.Module):
    """Simple 2-layer neural network for binary classification."""
    
    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(8, 16)
        self.fc2 = nn.Linear(16, 1)
    
    def forward(self, x):
        x = torch.relu(self.fc1(x))
        return self.fc2(x).squeeze(1)


def emit_telemetry(event_type: str, **kwargs):
    """Emit telemetry event to stdout for Aviexa to capture."""
    event = {"event_type": event_type, **kwargs}
    print(f"AVIEXA_TELEMETRY: {json.dumps(event)}", flush=True)


def main():
    print("=" * 60)
    print("  External Training Script: train_bad_lr.py")
    print("  Intentional bug: Learning rate too high (10.0)")
    print("=" * 60)
    
    # Set seed for reproducibility
    torch.manual_seed(42)
    
    # Create synthetic dataset
    N = 64
    X = torch.randn(N, 8)
    Y = torch.randint(0, 2, (N,)).float()
    
    print(f"\nDataset: {N} samples, 8 features, binary classification")
    
    # Initialize model
    model = SimpleNet()
    
    # INTENTIONAL BUG: Learning rate too high
    # This will cause gradient explosion
    optimizer = optim.SGD(model.parameters(), lr=10.0)
    criterion = nn.BCEWithLogitsLoss()
    
    print(f"Model: SimpleNet (8 -> 16 -> 1)")
    print(f"Optimizer: SGD with lr=10.0 (INTENTIONALLY TOO HIGH)")
    print(f"Loss: BCEWithLogitsLoss")
    print(f"\nStarting training for 10 steps...\n")
    
    # Training loop
    BATCH_SIZE = 16
    for step in range(1, 11):
        # Sample random batch
        idx = torch.randint(0, N, (BATCH_SIZE,))
        xb, yb = X[idx], Y[idx]
        
        # Forward pass
        optimizer.zero_grad()
        output = model(xb)
        loss = criterion(output, yb)
        
        # Emit loss telemetry
        loss_val = loss.item()
        emit_telemetry("loss", step=step, loss_value=loss_val)
        
        # Backward pass
        loss.backward()
        
        # Emit gradient telemetry for each layer
        for name, param in model.named_parameters():
            if param.grad is not None:
                grad_norm = param.grad.norm().item()
                has_nan = torch.isnan(param.grad).any().item()
                has_inf = torch.isinf(param.grad).any().item()
                
                emit_telemetry(
                    "backward",
                    step=step,
                    layer_name=name,
                    gradient_norm=grad_norm,
                    gradient_is_none=False,
                    has_nan=has_nan,
                    has_inf=has_inf,
                )
        
        # Update weights
        optimizer.step()
        
        # Print progress
        print(f"Step {step:2d}: loss={loss_val:.4f}")
    
    print(f"\n{'='*60}")
    print("  Training complete!")
    print("  Check Aviexa report for gradient explosion detection")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()

# Made with Bob
