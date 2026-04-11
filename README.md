# 🛡️ Core-Pulse
**Zero-Knowledge Cognitive Architecture & Intervention Pipeline**

[![C++20](https://img.shields.io/badge/C++-20-blue.svg)](https://isocpp.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Agentic_AI-orange.svg)](https://python.langchain.com/)
[![eBPF](https://img.shields.io/badge/eBPF-Kernel_Tracepoints-black.svg)](https://ebpf.io/)
[![Ollama](https://img.shields.io/badge/Ollama-Local_Inference-white.svg)](https://ollama.ai/)
[![ZeroMQ](https://img.shields.io/badge/ZeroMQ-IPC_Stream-red.svg)](https://zeromq.org/)

Core-Pulse is a distributed, zero-knowledge cognitive architecture. It bridges bare-metal Linux kernel tracepoints, local LLaMA-3 psychological profiling, and real-time Hyprland window manager interventions to isolate and neutralize developer burnout at the hardware level.

---

## 🧠 System Architecture

Unlike traditional monolithic productivity trackers, Core-Pulse decouples kernel ingestion, cryptographic storage, AI inference, and UI enforcement across a hyper-fast ZeroMQ IPC bridge:

1. **Bare-Metal Sentinel Core (C++20 & eBPF):** Bypasses high-level OS abstractions to track raw syscall entropy and context-switching metrics, establishing a baseline for hardware-level system thrashing.
2. **Cryptographic Vault (Python & AES-256-GCM):** Secures all kernel telemetry and OCR intercepts in a zero-knowledge SQLite vault, decrypted strictly in volatile memory for AI analysis.
3. **Neural Core & LangGraph Brain (Python & LLaMA-3):** A multi-agent graph running locally via Ollama. It dynamically calculates a "Burnout Probability" by fusing hardware entropy with semantic sentiment analysis of intercepted on-screen text.
4. **Governor TUI & Hyprland Enforcer (C++20 & FTXUI):** Dual enforcement. A terminal dashboard visualizes real-time cognitive metrics via an ASCII matrix, while the daemon physically throttles network traffic (via `tc`) and dims the Hyprland environment when critical burnout thresholds are breached.

---

## ⚙️ Prerequisites

To run this pipeline natively, your machine requires:
* **C++ Build Tools:** `g++`, `cmake`, `make`
* **Libraries:** `libzmq3-dev` (ZeroMQ), `libssl-dev` (OpenSSL)
* **Python:** 3.12+ with `pip`
* **Environment:** Linux running the Hyprland Wayland compositor.
* *(Required)* **Ollama** installed with the `dolphin-llama3:latest` model pulled locally.

---

## 🚀 Manual Launch Sequence

To run the architecture natively, you must spin up the components individually in separate terminal sessions to establish the data flow and IPC bridges.

### Step 1: Install Python Dependencies
```bash
cd layer2_neural/src
pip install langchain-ollama langgraph pydantic pyzmq
```

Step 2: Boot the Hardware Sentinel (Terminal 1)
```bash
cd layer0_sentinel/build
cmake .. && make
sudo ./sentinel_daemon
```

Step 3: Launch the Cryptographic Vault (Terminal 2)
```bash
cd layer1_vault/src
python main.py
```

Step 3: Launch the Cryptographic Vault (Terminal 2)
```bash
cd layer1_vault/src
python main.py
```

Step 4: Boot the Hyprland Context Bridge (Terminal 3)
```bash
cd layer3_governor/scripts
python layer1_context.py
```

Step 5: Fire the Neural Core (Terminal 4)
```bash
cd layer2_neural/src
python core_loop.py
```

Step 6: Launch the Matrix Governor TUI (Terminal 5)
```bash
cd layer3_governor/build
cmake .. && make
./tui_matrix
```
