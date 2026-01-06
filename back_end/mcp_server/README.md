# NLM Database MCP Server

MCP (Model Context Protocol) server exposing MongoDB collections to Claude Code/Desktop for AI-assisted dictionary generation, grammar analysis, and translation verification.

## Installation

```bash
pip install "mcp[cli]"
```

## Running the Server

```bash
# From back_end directory
python -m mcp_server.server
```

## Claude Code Configuration

Add to `~/.claude/claude_code_config.json`:

```json
{
  "mcpServers": {
    "nlm-database": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/nlm_public/back_end"
    }
  }
}
```
## Claude Project level configuration 
.mcp.json 
{
  "mcpServers": {
    "nlm-database": {
      "command": "/pathtovirtualenvironment",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/pathtoworkingdirectory",
      "env": {
        "PYTHONPATH": "/pathtovirtualenvironment"
      }
    }
  }
}

Or for VS Code, add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "nlm-database": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "${workspaceFolder}/back_end"
    }
  }
}
```

## Available Tools

### Language Tools
- `list_languages` - Get all languages with translation progress stats
- `get_language_info` - Get detailed info for a specific language

### Bible Tools
- `list_bible_books` - Get all Bible books for a language
- `get_chapter` - Get all verses for a Bible chapter
- `get_bible_chunk` - Get paginated Bible verses for large text processing

### Dictionary Tools
- `list_dictionary_entries` - Get paginated dictionary entries
- `get_dictionary_entry` - Get a specific dictionary entry by word
- `upsert_dictionary_entries` - Insert or update dictionary entries

### Grammar Tools
- `list_grammar_categories` - List all grammar categories with content status
- `get_grammar_category` - Get specific grammar category content
- `update_grammar_category` - Update grammar category content

## Common Parameters

- `language_code`: Language identifier (e.g., 'english', 'heb', 'kope')
- `translation_type`: Filter by 'human' or 'ai' translations (optional for reads, required for writes)

## Testing

```bash
pytest tests/unit/mcp_server/ -v
```
