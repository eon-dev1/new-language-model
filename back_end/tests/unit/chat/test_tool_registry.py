"""
Tests for shared/tool_registry.py

Failure points targeted:
- get_tools(readonly=True) leaks write tools
- call_tool with unknown name
- call_tool strips save_to_file from args
- is_write_tool correctly identifies write vs read tools
"""

import pytest
from shared.tool_registry import get_tools, call_tool, is_write_tool, get_tool_names


# ---------------------------------------------------------------------------
# get_tools filtering
# ---------------------------------------------------------------------------

class TestGetTools:
    def test_readonly_excludes_write_tools(self):
        tools = get_tools(readonly=True)
        names = {t["name"] for t in tools}
        assert "upsert_dictionary_entries" not in names
        assert "update_grammar_category" not in names

    def test_readonly_includes_read_tools(self):
        tools = get_tools(readonly=True)
        names = {t["name"] for t in tools}
        assert "list_languages" in names
        assert "get_chapter" in names
        assert "get_parallel_verses" in names

    def test_all_tools_includes_write_tools(self):
        tools = get_tools(readonly=False)
        names = {t["name"] for t in tools}
        assert "upsert_dictionary_entries" in names
        assert "update_grammar_category" in names

    def test_no_readonly_key_in_output(self):
        """Anthropic API would reject an unknown 'readonly' key."""
        for tool in get_tools(readonly=False):
            assert "readonly" not in tool

    def test_all_tools_have_required_keys(self):
        for tool in get_tools(readonly=False):
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool

    def test_save_to_file_not_in_schemas(self):
        """save_to_file should be stripped from get_bible_chunk and get_parallel_verses schemas."""
        tools = get_tools(readonly=True)
        for tool in tools:
            if tool["name"] in ("get_bible_chunk", "get_parallel_verses"):
                props = tool["input_schema"].get("properties", {})
                assert "save_to_file" not in props, f"save_to_file found in {tool['name']} schema"


# ---------------------------------------------------------------------------
# is_write_tool
# ---------------------------------------------------------------------------

class TestIsWriteTool:
    def test_write_tools(self):
        assert is_write_tool("upsert_dictionary_entries") is True
        assert is_write_tool("update_grammar_category") is True

    def test_read_tools(self):
        assert is_write_tool("list_languages") is False
        assert is_write_tool("get_chapter") is False

    def test_unknown_tool(self):
        assert is_write_tool("nonexistent_tool") is False


# ---------------------------------------------------------------------------
# call_tool
# ---------------------------------------------------------------------------

class TestCallTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_raises(self):
        with pytest.raises(ValueError, match="Unknown tool"):
            await call_tool("nonexistent_tool", {}, None)

    @pytest.mark.asyncio
    async def test_save_to_file_stripped(self):
        """call_tool should silently strip save_to_file from args before dispatch."""
        calls = []

        async def fake_get_bible_chunk(db, *, language_code, **kwargs):
            calls.append(kwargs)
            return {"verses": []}

        # Monkey-patch just for this test
        import shared.tool_registry as reg
        original = reg._TOOL_FUNCTIONS["get_bible_chunk"]
        reg._TOOL_FUNCTIONS["get_bible_chunk"] = fake_get_bible_chunk
        try:
            await call_tool("get_bible_chunk", {
                "language_code": "english",
                "save_to_file": "should_be_stripped",
            }, None)
            assert len(calls) == 1
            assert "save_to_file" not in calls[0]
        finally:
            reg._TOOL_FUNCTIONS["get_bible_chunk"] = original


# ---------------------------------------------------------------------------
# get_tool_names
# ---------------------------------------------------------------------------

class TestGetToolNames:
    def test_readonly_count(self):
        names = get_tool_names(readonly=True)
        # 19 total - 2 write = 17 readonly
        assert len(names) == 17

    def test_all_count(self):
        names = get_tool_names(readonly=False)
        assert len(names) == 19


# ---------------------------------------------------------------------------
# T1 — Extraction completeness (Step 1)
# ---------------------------------------------------------------------------

class TestExtractionCompleteness:
    def test_llm_tool_loop_exports_required_symbols(self):
        import shared.llm_tool_loop as loop
        assert hasattr(loop, "run_tool_loop")
        assert hasattr(loop, "get_context_window")
        assert hasattr(loop, "CONVERSATIONS_COLLECTION")


# ---------------------------------------------------------------------------
# T2 — Translation tool filter: propose_verse_translation excluded from chat (Step 2)
# ---------------------------------------------------------------------------

class TestTranslationToolFilter:
    """After Step 2: verify propose_verse_translation is invisible to chat."""

    def test_excluded_from_readonly_chat(self):
        names = {t["name"] for t in get_tools(readonly=True)}
        assert "propose_verse_translation" not in names

    def test_excluded_from_chat_with_write_tools(self):
        names = {t["name"] for t in get_tools(readonly=False)}
        assert "propose_verse_translation" not in names, (
            "propose_verse_translation leaked into chat tool set — "
            "LLM can call it, causing tool_approval event with no frontend handler."
        )

    def test_present_in_translation_tool_set(self):
        names = {t["name"] for t in get_tools(readonly=False, translation_only=True)}
        assert "propose_verse_translation" in names

    def test_is_write_tool(self):
        assert is_write_tool("propose_verse_translation") is True


# ---------------------------------------------------------------------------
# T4 — propose_verse_translation registered in _TOOL_FUNCTIONS (Step 2)
# ---------------------------------------------------------------------------

class TestCallToolProposalStub:
    """After Step 2: verify propose_verse_translation stub exists and is async."""

    @pytest.mark.asyncio
    async def test_propose_verse_translation_stub_is_async(self):
        import inspect
        import shared.tool_registry as reg
        assert "propose_verse_translation" in reg._TOOL_FUNCTIONS, (
            "propose_verse_translation missing from _TOOL_FUNCTIONS. "
            "call_tool() raises ValueError on any resume path that reaches it."
        )
        stub = reg._TOOL_FUNCTIONS["propose_verse_translation"]
        assert inspect.iscoroutinefunction(stub), (
            "propose_verse_translation stub must be async (call_tool uses await)"
        )


# ---------------------------------------------------------------------------
# T6 — verse_number field in propose_verse_translation schema (Step 3a)
# ---------------------------------------------------------------------------

class TestVerseNumberInSchema:
    """After Step 3a: verse_number is optional in schema for backward compat."""

    def test_verse_number_field_present(self):
        from shared.tool_registry import get_tools
        tools = {t["name"]: t for t in get_tools(readonly=False, translation_only=True)}
        pvt = tools["propose_verse_translation"]
        props = pvt["input_schema"]["properties"]
        assert "verse_number" in props, (
            "verse_number missing from propose_verse_translation schema. "
            "Batch mode uses it for frontend routing."
        )

    def test_verse_number_is_integer(self):
        from shared.tool_registry import get_tools
        tools = {t["name"]: t for t in get_tools(readonly=False, translation_only=True)}
        pvt = tools["propose_verse_translation"]
        props = pvt["input_schema"]["properties"]
        assert props["verse_number"]["type"] == "integer"

    def test_verse_number_is_required(self):
        """verse_number is required — used for frontend routing in both batch and chat modes."""
        from shared.tool_registry import get_tools
        tools = {t["name"]: t for t in get_tools(readonly=False, translation_only=True)}
        pvt = tools["propose_verse_translation"]
        required = pvt["input_schema"].get("required", [])
        assert "verse_number" in required, (
            "verse_number must be required for frontend routing"
        )
