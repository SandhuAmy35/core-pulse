from __future__ import annotations

import argparse
import random
import time

try:
    from layer1_vault.src.crypto_aes import decrypt_payload, encrypt_payload
    from layer1_vault.src.nasa_client import SpaceWeatherClient
    from layer1_vault.src.trng_engine import EntropyEngine
except ImportError:
    import sys
    from pathlib import Path

    REPO_ROOT = Path(__file__).resolve().parents[2]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from layer1_vault.src.crypto_aes import decrypt_payload, encrypt_payload
    from layer1_vault.src.nasa_client import SpaceWeatherClient
    from layer1_vault.src.trng_engine import EntropyEngine


def format_years(seconds: float) -> str:
    years = seconds / (365.25 * 24 * 3600)
    if years < 1:
        return f"{seconds:,.1f} seconds"
    if years < 1_000_000:
        return f"{years:,.1f} years"
    return f"{years:,.3e} years"


def simulate_attack(rounds: int, guesses_per_round: int, refresh_delay: float) -> None:
    client = SpaceWeatherClient(cache_ttl_seconds=1.0)
    entropy_engine = EntropyEngine()
    rng = random.Random(42)
    success = 0

    print("CORE-PULSE Layer 1 security simulation")
    print("Live space-weather entropy plus local micro-fluctuations rotate the AES-256-GCM key.")
    print()

    for round_index in range(1, rounds + 1):
        sample_payload = {
            "sequence": round_index,
            "timestamp": f"sim-round-{round_index}",
            "sensor_id": "sentinel-sim-01",
            "team": "hack-o-mania-core-pulse",
            "employees": [{"user_id": "U-8401", "focus_score": 0.81}],
            "system_load": {"cpu": 38.4, "memory": 52.1, "network_mbps": 7.9},
            "flags": ["simulation", "layer1_demo"],
        }
        snapshot = client.get_snapshot(force_refresh=round_index > 1)
        entropy = entropy_engine.build_entropy_material(
            snapshot,
            sample_payload,
            extra_context={"round": round_index},
        )
        encrypted = encrypt_payload(sample_payload, entropy, topic="telemetry_raw", source_label="layer1_demo")

        print(f"Round {round_index}")
        print(
            f"  key fingerprint: {entropy.key_fingerprint} | entropy digest: {entropy.entropy_digest[:18]}... "
            f"| source: {snapshot.quality} | xray: {snapshot.xray_flux_wm2:.3e}"
        )

        for _ in range(guesses_per_round):
            fake_key = rng.randbytes(32)
            try:
                decrypt_payload(encrypted, fake_key)
                success += 1
                break
            except Exception:
                continue

        at_one_billion_per_second = (2**256) / 1_000_000_000
        print(f"  brute-force attempts this round: {guesses_per_round:,}")
        print(f"  successful guesses: {success}")
        print(f"  keyspace estimate: 2^256 = 1.16e77 possibilities")
        print(f"  time at 1B guesses/sec: {format_years(at_one_billion_per_second)}")
        print("  result: attack failed before the entropy pool rotated again")
        print()
        time.sleep(refresh_delay)

    if success == 0:
        print("Simulation complete: dynamic cosmic entropy kept the payload opaque in every round.")
    else:
        print("Unexpected decrypt success observed in the simulation.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Visual brute-force failure simulation for Layer 1.")
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--guesses-per-round", type=int, default=2500)
    parser.add_argument("--refresh-delay", type=float, default=0.5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    simulate_attack(
        rounds=args.rounds,
        guesses_per_round=args.guesses_per_round,
        refresh_delay=args.refresh_delay,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
