"""
simulate_training.py
Feeds dummy data to the Aviexa dashboard so you can see it in action.
"""
import requests
import time
import random

API_BASE = "http://localhost:8765"

def simulate():
    # 1. Get the latest session ID from the API
    print("Connecting to Aviexa API...")
    sessions = requests.get(f"{API_BASE}/sessions").json()
    if not sessions:
        print("Error: No active session found. Did you run the command in VS Code?")
        return
    
    session_id = sessions[-1]['session_id']
    print(f"Feeding data to session: {session_id}")

    # 2. Simulate 20 steps of training
    for step in range(1, 21):
        loss = 2.5 / (step + 1) + random.uniform(-0.1, 0.1)
        payload = {
            "event_type": "loss",
            "session_id": session_id,
            "step": step,
            "loss_value": loss,
            "cpu_allocated_mb": 450.0 + random.uniform(-5, 5),
            "cuda_allocated_mb": 1200.0 if step > 5 else 0.0
        }
        
        requests.post(f"{API_BASE}/session/{session_id}/telemetry", json=payload)
        print(f"Step {step}: Loss = {loss:.4f}")
        time.sleep(0.5) # Matches the extension's polling rate

    # 3. Simulate an ANOMALY (Gradient Explosion)
    print("\n--- TRIGGERING ANOMALY ---")
    anomaly_payload = {
        "event_type": "backward",
        "session_id": session_id,
        "step": 21,
        "layer_name": "fc2.weight",
        "gradient_norm": 999.0 # This triggers the detector!
    }
    requests.post(f"{API_BASE}/session/{session_id}/telemetry", json=anomaly_payload)
    print("Sent Gradient Explosion event. Check your VS Code window!")

if __name__ == "__main__":
    simulate()
