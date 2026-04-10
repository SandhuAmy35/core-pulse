# CORE-PULSE

CORE-PULSE is a multi-layer hackathon prototype for privacy-aware employee productivity and burnout analytics. This repository now follows the team's integration-first strategy:

1. Clone and scaffold the shared repo.
2. Stand up the communication pipe before deep domain logic.
3. Let each layer swap the mock implementation for the real one without breaking contracts.

## Active integration path

- `layer0_sentinel/mock_publisher.py` publishes realistic mock telemetry over ZeroMQ.
- `layer2_neural/src/zmq_broadcaster.py` consumes the ZeroMQ stream, computes dashboard-ready aggregates, and exposes them over WebSockets.
- `layer4_surface/synergy-dashboard` renders the live stream in a polished Next.js dashboard.

## Shared contracts

- ZeroMQ topic contract: [shared_contracts/zmq_topics.json](shared_contracts/zmq_topics.json)
- Payload schemas: [shared_contracts/payload_schemas.json](shared_contracts/payload_schemas.json)

## Layer 1 space-weather source

The intended real-time cosmic entropy source for the later `layer1_vault` implementation is:

- Primary X-ray flux feed: `https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json`
- NASA flare enrichment feed: `https://kauai.ccmc.gsfc.nasa.gov/DONKI/WS/get/FLR?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD`

The SWPC feed gives the actual GOES X-ray flux values. The NASA DONKI endpoint supplies flare metadata for entropy enrichment and auditability.

## Quick start

### 1. Install the Python bridge dependencies

```powershell
python -m pip install -r layer2_neural/requirements.txt
```

### 2. Start the mock Layer 0 publisher

```powershell
python layer0_sentinel/mock_publisher.py --interval 0.8
```

### 3. Start the ZeroMQ -> WebSocket bridge

```powershell
python layer2_neural/src/core_loop.py --websocket-port 8765
```

### 4. Install and run the dashboard

```powershell
cd layer4_surface
npm install
npm run dev:dashboard
```

The dashboard will be available at `http://localhost:3000`, and it listens to the bridge at `ws://127.0.0.1:8765`.

## Why this layout works

- The communication contract is explicit before anyone writes heavy logic.
- The Linux-only C++ layers stay decoupled from the Python and Next.js workstreams.
- Layer 1 crypto, Layer 2 graph orchestration, and Layer 4 UX can all advance without breaking the integration surface.
