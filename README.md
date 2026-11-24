<div align="center">

  <img src="quince-icon.svg" alt="Quince Logo" width="96" height="96" />

  # Quince

  **The quiet, private, local-first Windows agent runtime & hierarchical MCP tool workspace.**

  Real-time autonomous browser control, deep Windows system telemetry, and low-latency voice interaction powered by a token-optimized hierarchical capability engine.  
  Zero cloud lock-in. Zero prompt bloat. Real-time deterministic execution.

  <p align="center">
    <a href="#hierarchical-mcp-engine"><img src="https://img.shields.io/badge/MCP-Hierarchical%20Engine-8b5cf6?style=for-the-badge&logo=anthropic" alt="MCP Hierarchical Engine" /></a>
    <a href="#rtsi-browser-automation"><img src="https://img.shields.io/badge/Chrome%20Extension-Manifest%20V3-4285f4?style=for-the-badge&logo=googlechrome" alt="Chrome MV3 Extension" /></a>
    <a href="#architecture"><img src="https://img.shields.io/badge/Python-3.10%2B%20%7C%20AsyncIO-3776ab?style=for-the-badge&logo=python" alt="Python 3.10+ AsyncIO" /></a>
    <a href="#desktop-voice-client"><img src="https://img.shields.io/badge/Audio-Windows%20WASAPI-0078d4?style=for-the-badge&logo=windows" alt="Windows WASAPI" /></a>
    <a href="#license"><img src="https://img.shields.io/badge/License-MIT-amber.svg?style=for-the-badge" alt="License MIT" /></a>
  </p>

  <p align="center">
    <a href="#why-quince">Why Quince</a> •
    <a href="#core-capabilities">Capabilities</a> •
    <a href="#architecture">Architecture</a> •
    <a href="#hierarchical-mcp-engine">Hierarchical MCP</a> •
    <a href="#rtsi-browser-automation">RTSI Browser Bridge</a> •
    <a href="#desktop-voice-client">Voice Subsystem</a> •
    <a href="#getting-started">Getting Started</a> •
    <a href="#configuration">Configuration</a> •
    <a href="#engineering-highlights">Engineering Highlights</a>
  </p>

</div>

---

## Why Quince?

Most desktop AI assistants and tool-calling runtimes suffer from fundamental architecture flaws:
- **Prompt Window Exhaustion:** Dumping 40+ flat tool schemas into every model turn wastes thousands of context tokens, inflates latency, and increases parameter hallucination.
- **Brittle Browser Automation:** Relying on heavyweight CDP instances or detached Puppeteer sessions disconnects the agent from the user's active browsing session and fails on complex SPA state changes.
- **Lack of Safety Guardrails:** Standard agents execute irreversible actions (financial checkouts, sending emails, deleting data) autonomously without human-in-the-loop verification.
- **Audio Lag & Poor Interruption Handling:** Push-to-talk interfaces suffer from device drift, audio buffer latency, and inability to cleanly interrupt speech mid-playback.

**Quince solves these problems with systems-level engineering:**
- **Hierarchical Capability Tree:** Exposes a single, unified `navigate` primitive. The LLM navigates an organized domain tree on demand, loading schemas strictly when needed—**reducing tool prompt tokens by over 75%** while enabling multi-step compositional execution across different branches.
- **RTSI (Real-Time State Inspection) Engine:** A Manifest V3 Chrome Extension communicating over a loopback WebSocket bridge (`ws://127.0.0.1:7100`). Employs an Action-Perception loop with semantic accessibility snapshots, stable element references, and DOM mutation quiescence.
- **Zero-Trust Risk Gate:** Irreversible operations trigger an automated `await_user` suspension, prompting the user for verbal or physical confirmation before execution.
- **Hardware-Level WASAPI Audio:** Low-latency 16 kHz PCM microphone capture and 24 kHz streaming playback with an instant barge-in interrupt gesture (`Ctrl+Q`), race-condition turn tokens, and an active audio device watchdog.

---

## Core Capabilities

### 1. Hierarchical MCP Engine
> Dynamic capability navigation replacing monolithic flat tool catalogs.

- **On-Demand Schema Injection:** The agent receives category menus first (`system`, `files`, `web`, `productivity`, `knowledge`, `memory`, `browser`, `chat`) and only loads specific tool schemas upon entering a domain.
- **Compositional Multi-Hop Tool Chains:** The model navigates into a branch, executes a capability, preserves the result in working context, calls `reset` to traverse to a different branch, and executes subsequent actions within a single session.
- **Multi-Transport Support:** Runs over Streamable HTTP (`127.0.0.5:10010/mcp`), Server-Sent Events (SSE), or standard `stdio`.

### 2. RTSI Chrome Browser Automation
> Fast, DOM-native web control without heavyweight headless browser overhead.

- **Stable Element References:** Generates concise accessibility snapshots with stable element IDs (`e1`, `e2`), bypassing fragile CSS selectors and coordinate-based clicking.
- **Action-Perception State Machine:** Strict transitions across `ENTRY` -> `DECIDE` -> `ACTION` -> `COMPARE` -> `JUDGE` -> `TERMINATE` with DOM mutation diffing.
- **Context Observation Recycling:** Automatically purges intermediate page snapshots using `replaces: "observation"`, preventing token explosion during long browser sessions.
- **Safety HUD & Emergency Stop:** Closed-shadow-root visual indicators outline active automation, accompanied by a physical emergency stop shortcut (`Alt+Shift+Q`).

### 3. Windows Desktop Voice Client
> Seamless push-to-talk desktop interaction with zero-latency interruption.

- **Unified Push-to-Talk & Barge-In:** Holding `Ctrl+Q` records speech. Pressing the hotkey while the assistant is speaking instantly aborts playback and begins capturing the new prompt in one motion.
- **WASAPI Device Pinning & Watchdog:** Selects audio devices by exact name and host API (Windows WASAPI) rather than OS default indices, backed by a background watchdog that recovers from device disconnections.
- **Resilient Transport:** Maintains a bidirectional WebSocket connection to the Basket LLM runtime with heartbeat health checks, exponential backoff, and turn-token validation to prevent race conditions.

### 4. Deep System Telemetry & Administration
> Granular, safe Windows control without arbitrary shell execution risks.

- **Hardware Sensors:** Real-time CPU load, per-core CPU temperatures via WMI, RAM utilization, and NVIDIA GPU metrics (load and VRAM) via `pynvml`.
- **System & Window Management:** Active window inspection, process lifecycle control, clipboard read/write/clear, media controls, and explicit power actions (shutdown, restart).
- **Safe File Operations:** Atomic read, write, append, search, and directory management with strict path boundaries.

---

## Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        User & Desktop Environment                      │
│   Push-to-Talk (Ctrl+Q) • Microphone (16 kHz PCM) • Speaker (24 kHz)   │
│   Chrome Browser • Closed-Shadow-Root Safety HUD • Emergency Stop      │
└──────────────────┬──────────────────────────────────┬──────────────────┘
                   │                                  │
       WASAPI Audio / Hotkeys             DOM Snapshots / Micro-Actions
                   │                                  │
                   ▼                                  ▼
┌─────────────────────────────────────┐    ┌─────────────────────────────┐
│       Quince Desktop Client         │    │   Chrome MV3 Extension      │
│  • WASAPI Audio Streamer & Watchdog │    │  • Accessibility Snapshot   │
│  • Turn State Machine & Tokens      │    │  • Mutation & Idle Detector │
│  • Resilient WebSocket Reconnector  │    │  • Closed Shadow Root HUD   │
└──────────────────┬──────────────────┘    └──────────────┬──────────────┘
                   │                                      │
                   │ WebSocket (audio/events)             │ WebSocket (ws://127.0.0.1:7100)
                   ▼                                      ▼
┌─────────────────────────────────────┐    ┌─────────────────────────────┐
│       Basket Agent Runtime          │    │    Quince Bridge Server     │
│  • Conversation Orchestration       │    │  • Localhost Token Auth     │
│  • Local LLM Host & Inference       │    │  • Chrome Session Router    │
│  • Memory & Vector Retrieval        │    └──────────────┬──────────────┘
│  • STT (Qwen3-ASR) / TTS (Pocket)   │                   │
└──────────────────┬──────────────────┘                   │
                   │ JSON-RPC (HTTP / SSE / Stdio)        │
                   ▼                                      │
┌─────────────────────────────────────────────────────────┴──────────────┐
│                    Quince Hierarchical MCP Server                      │
│   • Single navigate(tool_id, args) dispatch entry point                │
│   • Dynamic schema resolution & pruning (slashes token overhead >75%)  │
│   • RTSI Finite State Machine (Entry -> Act -> Compare -> Judge)       │
│   • Risk Gate & Deterministic await_user Spoken Confirmations          │
└──────────────────┬─────────────────────────────────────────────────────┘
                   │ Host Subsystems
                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   Windows System & Hardware Layer                      │
│   WMI (Thermal) • pynvml (GPU) • psutil (Telemetry) • Win32 (Media)    │
└────────────────────────────────────────────────────────────────────────┘
```

### Architectural Separation
- **Quince** owns the desktop interface, Windows system primitives, audio I/O, browser extension bridge, and the hierarchical capability tree.
- **Basket** acts as the parent agent runtime, owning the LLM inference, long-term memory, conversation context, speech-to-text, and text-to-speech pipelines.

---

## Hierarchical MCP Engine

Instead of presenting an LLM with dozens of flat tools simultaneously, Quince structures capabilities into a directed tree. The model navigates through categories to discover only the schemas relevant to its current intent.

```
root
├── system          -> Hardware telemetry, GPU/VRAM, CPU temp, processes, power, clipboard, media
├── files           -> Directory listing, file reading, writing, appending, searching, deleting
├── web             -> DuckDuckGo web search, webpage text extraction, live weather, HTTP requests
├── productivity    -> Local persistent notes and countdown timers
├── knowledge       -> Wikipedia and Wikimedia knowledge retrieval
├── memory          -> Long-term memories and behavioral command storage
├── browser         -> RTSI live Chrome browser automation and DOM inspection
└── chat            -> Direct conversation routing without external tool execution
```

### Navigation & Control Flow
The MCP server exposes a single callable tool: `navigate(tool_id, arguments)`.

```
                    ┌─────────────────────────┐
                    │      LLM Decision       │
                    └────────────┬────────────┘
                                 │
           ┌─────────────────────┼─────────────────────┐
           ▼                     ▼                     ▼
   navigate(category)    navigate(leaf_tool)    navigate(control)
           │                     │                     │
           ▼                     ▼                     ▼
  Returns category       Executes capability    • reset: returns to root
  children & schemas     & returns result       • terminate: ends loop
```

### Multi-Step Composition Walkthrough

A user asks: *"Check my GPU temperature, search for recommended thermal limits, and write them in my notes."*

```
User Prompt
    │
    ▼
LLM in Basket ──► navigate("root--system--hardware--get-gpu-temp")
                      │
                      ▼
                  Quince MCP returns GPU temperature
                      │
    ┌─────────────────┘
    ▼
LLM retains GPU temp ──► navigate("reset")
                             │
                             ▼
                         Quince MCP resets navigation to root menu
                             │
    ┌────────────────────────┘
    ▼
LLM in Basket ──► navigate("root--web--search", {"query": "NVIDIA thermal limits"})
                      │
                      ▼
                  Quince MCP returns web search results
                      │
    ┌─────────────────┘
    ▼
LLM retains findings ──► navigate("reset") ──► navigate("root--productivity--notes--add-note", {...})
                                                   │
                                                   ▼
                                               Note created successfully
                                                   │
    ┌──────────────────────────────────────────────┘
    ▼
LLM calls navigate("terminate") ──► Basket delivers spoken voice response
```

### Context & Token Efficiency

| Metric | Flat Tool Approach | Quince Hierarchical MCP |
|---|---|---|
| **Tools exposed per turn** | 50+ tools simultaneously | 5 to 8 focused tools |
| **Schema tokens per prompt** | ~3,500 - 5,000 tokens | ~300 - 600 tokens |
| **Token Reduction** | Baseline (0%) | **75% - 85% savings** |
| **Tool hallucination rate** | High (confuses similar arguments) | Near zero (constrained action spaces) |
| **Multi-domain chaining** | Unstructured, single-shot bias | Deterministic branch traversal |

---

## RTSI: Real-Time Screen Interaction

Quince features a purpose-built browser control framework designed for high reliability, minimal token usage, and strict safety.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        RTSI State Machine Loop                         │
│                                                                        │
│   ┌─────────┐      ┌────────┐      ┌────────┐      ┌────────┐          │
│   │  ENTRY  ├─────►│ DECIDE ├─────►│ ACTION ├─────►│COMPARE │          │
│   └─────────┘      └───▲────┘      └────────┘      └───┬────┘          │
│                        │                               │               │
│                        │           ┌───────┐           │               │
│                        └───────────┤ JUDGE ◄───────────┘               │
│                                    └───┬───┘                           │
│                                        │ (Goal Achieved)               │
│                                        ▼                               │
│                                 ┌─────────────┐                        │
│                                 │  TERMINATE  │                        │
│                                 └─────────────┘                        │
└────────────────────────────────────────────────────────────────────────┘
```

### Core Innovations
1. **Accessible DOM Snapshot Engine:** Rather than passing high-resolution screenshots to vision models (which are slow, token-expensive, and prone to coordinate misalignment), the extension extracts an interactive DOM tree with stable element references (`refs: ["e12"]`).
2. **Context Window Garbage Collection:** The server emits `replaces: "observation"`. Basket discards prior snapshot dumps and preserves only the latest observation, preventing context exhaustion during long tasks.
3. **Deterministic Safety Risk Gate:** Irreversible actions (submitting orders, deleting content, sending communications) trigger an `await_user` pause. The assistant speaks the confirmation request and waits for explicit user authorization before firing the action.
4. **Emergency Stop & Closed Shadow HUD:** The browser viewport displays a visible border and kill pill rendered in a closed Shadow DOM root, isolating it from host page styles. The user can press `Alt+Shift+Q` to abort agent execution immediately.

---

## Desktop Voice Client

The desktop client coordinates user voice interactions, WebSocket transport, and local hardware:

```
┌──────────────┐   Hotkey Press    ┌───────────────┐   Hotkey Release   ┌───────────────┐
│     IDLE     ├──────────────────►│   RECORDING   ├───────────────────►│ PIPELINE BUSY │
└──────▲───────┘                   └───────▲───────┘                    └───────┬───────┘
       │                                   │                                    │
       │ Playback Complete                 │ Hotkey Interrupt                   │ TTS Stream
       │                                   │ (Barge-In)                         ▼
┌──────┴────────┐                          │                            ┌───────────────┐
│ PLAYBACK DONE │◄─────────────────────────┴────────────────────────────┤    PLAYING    │
└───────────────┘                                                       └───────────────┘
```

### Low-Latency Audio Subsystem
- **Microphone Capture:** 16 kHz mono 16-bit PCM streaming. Matches the input requirements of local ASR engines (Qwen3-ASR) without resampling overhead.
- **Playback Stream:** 24 kHz mono 16-bit PCM streaming from local TTS engines (Pocket TTS).
- **Audio Device Watchdog:** Monitors active audio endpoints. If a USB microphone or Bluetooth headset disconnects or re-enumerates, the watchdog recovers the stream without requiring an application restart.
- **Race-Condition Turn Tokens:** Unique turn tokens prevent stale completion events from tearing down a new recording turn started during barge-in.

---

## Capability Matrix

| Domain | Leaf Capabilities | Primary Libraries / Backends | Execution Highlights |
|---|---|---|---|
| **System** | CPU usage, per-core CPU temperature, RAM, NVIDIA GPU & VRAM, disk space, network status, Wi-Fi info, process list/kill, active windows, clipboard read/write/clear, media playback/volume, power controls (shutdown/restart) | `psutil`, `pynvml`, `wmi`, `pywin32`, `ctypes` | Real-time hardware telemetry; granular process and window management; explicit system administration. |
| **Files** | Read file, write file, append file, list directory, search files (regex/glob), delete file, file metadata | Python `os`, `pathlib`, `shutil` | Atomic file writes; bounded recursive directory walks; strict path safety checks. |
| **Web** | Web search, fetch webpage article, live weather retrieval, HTTP REST requests | `httpx`, `BeautifulSoup4`, DuckDuckGo HTML | Full text cleanup and HTML tag stripping; resilient HTTP client with timeout guards. |
| **Browser (RTSI)** | Navigate URL, click, type text, clear input, select dropdown, scroll, switch tabs, close tab, go back, wait for element, form submission | Manifest V3 Chrome Extension, WebSockets (`ws://127.0.0.1:7100`) | Fast DOM accessibility tree; stable ref indexing; micro-diff mutation detection; risk-gated execution. |
| **Productivity** | Create note, read note, list notes, edit note, append to note, delete note, set countdown timer, list/cancel timers | Local filesystem JSON storage, Python `asyncio` | Lightweight local persistence; asynchronous non-blocking countdown timers. |
| **Knowledge** | Wikipedia article search, article summary, full page content | Wikimedia REST API, `httpx` | Fast encyclopedic retrieval for offline/local knowledge synthesis. |
| **Memory** | Store memory, retrieve memories, delete memory, add/list behavioral commands | Basket Memory API | Bi-directional synchronization of user preferences and behavioral directives with Basket. |
| **Chat** | Direct conversational route | Internal routing | Fallback path allowing direct conversational responses without tool execution overhead. |

---

## Repository Structure

```
quince/
├── client/                     # Web dashboard bundle assets
├── docs/                       # Technical contracts & extension guides
│   ├── EXTENSION_SETUP.md      # Step-by-step Chrome extension onboarding
│   └── RTSI_BASKET_CONTRACT.md # Formal parent-agent integration contract
├── extension/                  # Manifest V3 Chrome Extension source
│   ├── src/
│   │   ├── background/         # Extension service worker & WebSocket bridge client
│   │   ├── content/            # DOM accessibility tree snapshotter & action executor
│   │   ├── options/            # Bridge connection & authentication options UI
│   │   ├── popup/              # Quick status & connection indicator popup
│   │   └── shared/             # TypeScript protocol definitions and shared types
│   ├── esbuild.config.mjs      # Fast TypeScript/asset bundler configuration
│   └── package.json            # Extension dependencies and build scripts
├── quince_mcp/                 # Hierarchical Model Context Protocol Server
│   ├── bridge/                 # Local loopback WebSocket bridge server (port 7100)
│   ├── rtsi/                   # RTSI finite state machine, comparator, and judge
│   ├── schemas/                # QuinceTool schema abstractions
│   ├── tools/                  # Domain-specific tool implementations
│   │   ├── browser/            # RTSI browser navigation and action tools
│   │   ├── files/              # Filesystem CRUD handlers
│   │   ├── knowledge/          # Wikipedia / Wikimedia integration
│   │   ├── memory/             # Memory and behavioral command bridge
│   │   ├── productivity/       # Local notes and timer services
│   │   ├── system/             # Windows hardware, telemetry, and OS controls
│   │   └── web/                # Search, article extraction, and weather
│   ├── tool_tree.py            # Central capability registry and root hierarchy
│   └── server.py               # MCP server instance (Streamable HTTP, SSE, stdio)
├── src/                        # Windows Desktop Voice Client
│   ├── audio/                  # WASAPI microphone streamer, player, and watchdog
│   ├── input/                  # Global push-to-talk hotkey hook (Ctrl+Q)
│   ├── transport/              # Resilient WebSocket connection to Basket
│   ├── ui/                     # Rich console status dashboard and themes
│   ├── client.py               # Desktop client orchestration and turn state machine
│   └── config.py               # Environment variable dataclass settings
├── tests/                      # Automated test suite and benchmarks
│   ├── test_arg_validation.py  # Tool argument validation coverage
│   ├── test_bridge_e2e.py      # End-to-end WebSocket bridge tests
│   ├── test_rtsi_machine.py    # Finite state machine transition tests
│   └── test_system_files_web_tools.py # Hardware and OS tool verification
├── pytest.ini                  # Pytest configuration
├── requirements.txt            # Python dependencies
├── run.py                      # Desktop voice client & interactive CLI entry point
├── run_mcp.py                  # Standalone MCP server entry point
└── test_rtsi_performance.py    # Comprehensive performance benchmark suite
```

---

## Getting Started

### Prerequisites
- **Operating System:** Windows 10 / 11 (64-bit)
- **Python:** 3.10 or newer
- **Node.js:** 18 or newer (required for building the Chrome extension)
- **Google Chrome:** Any modern release supporting Manifest V3 extensions

---

### Step 1: Environment Setup

```powershell
# Navigate to the Quince root directory
cd quince

# Create and activate a Python virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

### Step 2: Build the Chrome Extension

```powershell
# Navigate to the extension directory
cd extension

# Install packages and compile TypeScript via esbuild
npm install
npm run build

# Return to root directory
cd ..
```

**Load into Chrome:**
1. Open Google Chrome and navigate to `chrome://extensions/`.
2. Toggle **Developer mode** in the top-right corner.
3. Click **Load unpacked** and select the `quince/extension/dist` directory.
4. Pin the extension and verify that the bridge is configured to connect to `ws://127.0.0.1:7100`.

---

### Step 3: Configuration

Copy the example environment settings:

```powershell
cp .env.example .env
```

Configure your audio devices and connection endpoints in `.env`:

```env
# Parent Agent WebSocket Endpoint
BASKET_WS_URL=ws://127.0.0.1:10010/ws

# Push-to-Talk Hotkey
PUSH_TO_TALK_HOTKEY=ctrl+q

# Audio Configuration (WASAPI)
AUDIO_SAMPLE_RATE=16000
AUDIO_CHANNELS=1
AUDIO_HOST_API=Windows WASAPI

# RTSI Browser Bridge
QUINCE_BRIDGE_ENABLED=true
QUINCE_BRIDGE_HOST=127.0.0.1
QUINCE_BRIDGE_PORT=7100
```

---

### Step 4: Running Quince

#### Option A: Desktop Voice Client & CLI
Starts the push-to-talk voice listener, terminal status line, and interactive text prompt:

```powershell
python run.py
```

- **Voice Input:** Hold `Ctrl+Q`, speak your request, and release to submit.
- **Barge-In:** Press `Ctrl+Q` at any time during assistant playback to interrupt immediately.
- **Text Input:** Type directly into the terminal prompt.

#### Option B: Standalone MCP Server
Starts the hierarchical MCP server independently for integration with Basket or any MCP client:

```powershell
# Run using Streamable HTTP transport (default: http://127.0.0.5:10010/mcp)
python run_mcp.py --transport streamable-http

# Or run over stdio transport
python run_mcp.py --transport stdio
```

---

## Configuration Reference

| Environment Variable | Default | Purpose |
|---|---|---|
| `BASKET_WS_URL` | `ws://127.0.0.1:10010/ws` | Parent agent WebSocket endpoint |
| `PUSH_TO_TALK_HOTKEY` | `ctrl+q` | Global Windows hotkey for recording and interruption |
| `AUDIO_SAMPLE_RATE` | `16000` | Input microphone sample rate (PCM16 mono) |
| `AUDIO_BLOCKSIZE` | `640` | Audio stream buffer chunk size (40 ms low-latency blocks) |
| `AUDIO_HOST_API` | `Windows WASAPI` | Preferred Windows audio driver subsystem |
| `AUDIO_INPUT_DEVICE` | *System Default* | Explicit microphone hardware device name |
| `AUDIO_OUTPUT_DEVICE` | *System Default* | Explicit speaker hardware device name |
| `WS_RECONNECT` | `true` | Enable automatic WebSocket reconnection with exponential backoff |
| `WS_RECONNECT_MAX_DELAY` | `30.0` | Maximum reconnection backoff ceiling in seconds |
| `QUINCE_BRIDGE_ENABLED` | `true` | Master switch for the Chrome Extension WebSocket bridge |
| `QUINCE_BRIDGE_PORT` | `7100` | Localhost port for browser extension communication |
| `RTSI_SNAPSHOT_MAX_CHARS` | `6000` | Maximum character budget per accessibility snapshot |
| `RTSI_MAX_STEPS` | `40` | Maximum autonomous browser actions permitted per session |
| `RTSI_RISK_GATE` | `on` | Spoken user confirmation requirement for irreversible actions |
| `QUINCE_MCP_TRANSPORT` | `streamable-http` | Primary MCP server transport protocol (`streamable-http`, `sse`, `stdio`) |
| `QUINCE_MCP_PORT` | `10010` | Port for the Streamable HTTP MCP server |

---

## Testing & Verification

The repository includes a comprehensive, automated test suite:

```powershell
# Run unit and integration tests across tool domains and the state machine
pytest tests -v

# Run the end-to-end RTSI performance and latency benchmark suite
python test_rtsi_performance.py
```

### Benchmark Suite Metrics
Running `test_rtsi_performance.py` measures:
- Tool tree hierarchy discovery and schema pruning latency (< 2 ms).
- Hardware sensor readout throughput (WMI, NVML, psutil).
- Local filesystem CRUD operational latency.
- RTSI finite state machine transitions across all action states.

---

## Engineering Highlights

If you are evaluating this project from an engineering perspective, here are the architectural design decisions that showcase production-grade systems thinking:

1. **Protocol & Distributed Architecture Design:** Custom implementation of Anthropic's Model Context Protocol (MCP) providing Streamable HTTP, SSE, and Stdio transports, integrated with an event-driven WebSocket bridge.
2. **Token Economics & Agent Prompt Optimization:** Replaced monolithic tool schemas with an on-demand hierarchical capability tree, reducing LLM context overhead by up to 85% and virtually eliminating tool parameter confusion.
3. **Real-Time Systems & Audio Programming:** Low-latency Windows WASAPI integration with 40 ms PCM streaming blocks, non-blocking hardware watchdog monitors, and race-free barge-in interruption.
4. **Resilient Finite State Machines:** Formal state machines governing both client turn lifecycles (with turn tokens to handle network dropouts) and RTSI browser automation (Entry -> Decide -> Action -> Compare -> Judge -> Terminate).
5. **Deterministic AI Safety Guardrails:** Implemented a Zero-Trust Risk Gate that halts autonomous browser actions and triggers a spoken `await_user` confirmation whenever high-stakes or destructive operations are detected.

---

## License

Distributed under the **MIT License**.  
Crafted with focus on local-first computing, systems programming, and high-performance AI agent architectures.
