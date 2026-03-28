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

Add to your project-level `.mcp.json` or `~/.claude.json`:

```json
{
  "mcpServers": {
    "nlm-database": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/nlm/back_end"
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
- `save_bible_batches` - Save multiple batches of verses to files in one call
- `get_parallel_verses` - Fetch verses across multiple languages for comparison

### Dictionary Tools
- `list_dictionary_entries` - Get paginated dictionary entries
- `get_dictionary_entry` - Get a specific dictionary entry by word
- `upsert_dictionary_entries` - Insert or update dictionary entries

### Grammar Tools
- `list_grammar_categories` - List all grammar categories with content status
- `get_grammar_category` - Get specific grammar category content
- `update_grammar_category` - Update grammar category content

### Word Index Tools
- `get_word_index` - Look up a word's frequency, locations, and dictionary status
- `get_words_not_in_dictionary` - Find frequent corpus words missing from the dictionary
- `get_word_frequency_list` - Get top N most frequent words with dictionary status

### Memories Tools
- `list_language_notes` - List all notes for a language, sorted by recency
- `search_language_notes` - Search notes by phrase (case-insensitive)
- `list_correction_log` - List correction log entries with optional type filtering
- `search_correction_log` - Search correction log across text fields

## Common Parameters

- `language_code`: Language identifier (e.g., 'english', 'heb', 'kope')

## Testing

```bash
pytest tests/unit/mcp_server/ -v
```
