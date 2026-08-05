# Local LLM Setup (llama.cpp)

NLM supports any local server that implements the Anthropic Messages API.

---

## 1. Clone

```bash
git clone https://github.com/ggml-org/llama.cpp.git
cd llama.cpp
mkdir build && cd build
```

---

## 2. Build

### Linux / Windows — NVIDIA GPU (CUDA)

Set `CMAKE_CUDA_ARCHITECTURES` to match your GPU:

| GPU family | Architecture |
|---|---|
| Blackwell (RTX 50xx) | `120` |
| Ada Lovelace (RTX 40xx) | `89` |
| Ampere (RTX 30xx) | `86` |

```bash
cmake .. -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="<arch>" -DLLAMA_CURL=OFF
```

**Linux:**
```bash
make -j$(nproc)
```

**Windows** (from a Developer Command Prompt or with ninja installed):
```bash
cmake --build . --config Release -j %NUMBER_OF_PROCESSORS%
```

The server binary will be at:
- Linux: `build/bin/llama-server`
- Windows: `build/bin/Release/llama-server.exe`

### macOS — Apple Silicon (Metal)

```bash
cmake .. -DGGML_METAL=ON -DLLAMA_CURL=OFF
make -j$(sysctl -n hw.logicalcpu)
```

---

## 3. Start the Server

Replace the placeholders with your actual paths:

| Placeholder | Example |
|---|---|
| `<llama-server>` | `~/llama.cpp/build/bin/llama-server` |
| `<model.gguf>` | `~/ai_models/granite-4.0-h-tiny-UD-Q8_K_XL.gguf` |
| `<template.jinja>` | `~/llama.cpp/models/templates/ibm-granite-4-tiny.jinja` |

```bash
<llama-server> \
    -m <model.gguf> \
    --chat-template-file <template.jinja> \
    -c 131072 \
    -ngl 99 \
    -ub 8192 \
    --jinja \
    --batch-size 4096 \
    --parallel 1 \
    --host 127.0.0.1 \
    --port 8080
```

Flags:
- `-c` — context length in tokens (match this value in NLM's `local_context_window`)
- `-ngl` — layers offloaded to GPU (set to 99 to put everything on GPU)
- `--parallel` — concurrent request slots (1 is fine for solo use)

To log output: append `2>&1 | tee local_llm/logs/granite-server.log`

---

## 4. Configure NLM

### Option A: Via the UI

Open **Settings > Chat Config** in the Electron app and set:
- **LLM Provider**: `local`
- **Base URL**: `http://127.0.0.1:8080`
- **Model**: `default` (or the model name your server expects)

### Option B: Edit the config file directly

Edit `~/.nlm/chat_config.json`:

```json
{
  "llm_provider": "local",
  "local_base_url": "http://127.0.0.1:8080",
  "local_model": "default",
  "local_context_window": 131072
}
```

Set `local_context_window` to match your server's `-c` value.

### Requirements

- The local server must implement the **Anthropic Messages API** (`/v1/messages` endpoint). llama.cpp supports this natively.
- **Extended thinking is auto-disabled** for local providers. The NLM backend detects `is_local` and skips thinking parameters.
- The Anthropic SDK handles both remote and local — only `base_url` and `api_key` differ. The local provider uses `api_key="local"` as a placeholder.
