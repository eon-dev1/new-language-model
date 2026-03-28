
## Configuring NLM to Use a Local LLM

Once your local server is running, configure the NLM app to use it.

### Option A: Via the UI

Open **Settings > Chat Config** in the Electron app and set:
- **LLM Provider**: `local`
- **Base URL**: `http://127.0.0.1:8080` (match your server's `--host` and `--port`)
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

Set `local_context_window` to match your server's `-c` flag (context length in tokens).

### Requirements

- The local server must implement the **Anthropic Messages API** (`/v1/messages` endpoint). llama.cpp supports this natively.
- **Extended thinking is auto-disabled** for local providers. The NLM backend detects `is_local` and skips thinking parameters.
- The Anthropic SDK is used for both remote and local — only the `base_url` and `api_key` differ. The local provider uses `api_key="local"` as a placeholder.