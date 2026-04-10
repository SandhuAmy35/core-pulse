# Layer 1 Vault

Layer 1 consumes `telemetry_raw` frames from Layer 0, enriches each payload with live space-weather context, derives entropy for AES-256-GCM encryption, persists only sealed records, and stores an integrity proof for later audit.

## Install

```powershell
python -m pip install -r layer1_vault/requirements.txt
```

## Run The Vault Daemon

```powershell
python layer1_vault/src/main.py --log-level INFO
```

By default the daemon:

- subscribes to `tcp://127.0.0.1:5557`
- listens for the `telemetry_raw` topic
- writes the vault database to `layer1_vault/data/vault.db`

## Inspect The Vault

```powershell
python layer1_vault/src/vault_report.py --pretty --verify-integrity
```

`--verify-integrity` recomputes the stored proof hash for recent rows and confirms that each proof still matches the ciphertext, nonce, AAD digest, telemetry summary, and linked space-weather snapshot.

## Demo The Security Story

```powershell
python layer1_vault/ui_sim/flex_demo.py --rounds 3 --guesses-per-round 2500
```

## Validate Layer 1

```powershell
python layer1_vault/tests/check_unit.py
python layer1_vault/tests/check_live_pipeline.py
python layer1_vault/tests/check_report.py
python layer1_vault/tests/check_demo.py
```
