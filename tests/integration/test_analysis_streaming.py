"""Tests for run_analysis_streaming agentic loop."""

import json
import pytest
from unittest.mock import patch, MagicMock


def make_tool_use_block(name="get_realtime_quote", input_data=None, block_id="tool_1"):
    """Create a mock tool_use content block."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.input = input_data or {"ticker": "AAPL"}
    block.id = block_id
    return block


def make_text_block(text="Analysis complete."):
    """Create a mock text content block."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def make_response(stop_reason="end_turn", content=None):
    """Create a mock Anthropic API response."""
    resp = MagicMock()
    resp.stop_reason = stop_reason
    resp.content = content or []
    return resp


class TestRunAnalysisStreaming:
    """Tests for the run_analysis_streaming generator."""

    def _collect_events(self, generator):
        """Consume a generator and parse SSE events into dicts."""
        events = []
        for line in generator:
            if line.startswith("data: "):
                payload = line[len("data: "):].rstrip("\n")
                events.append(json.loads(payload))
        return events

    @patch("app.process_tool_call")
    @patch("app.claude_client")
    def test_single_tool_then_text(self, mock_client, mock_tool_call):
        """One tool_use turn followed by end_turn produces status + content + done."""
        from app import run_analysis_streaming

        tool_block = make_tool_use_block()
        text_block = make_text_block("Final analysis.")

        mock_client.messages.create.side_effect = [
            make_response("tool_use", [tool_block]),
            make_response("end_turn", [text_block]),
        ]
        mock_tool_call.return_value = {"price": 150}

        events = self._collect_events(run_analysis_streaming("AAPL"))

        assert events[0]["type"] == "status"
        assert events[-1]["type"] == "done"
        content_events = [e for e in events if e["type"] == "content"]
        assert len(content_events) == 1
        assert content_events[0]["text"] == "Final analysis."

    @patch("app.process_tool_call")
    @patch("app.claude_client")
    def test_multiple_tools_in_one_response(self, mock_client, mock_tool_call):
        """Two tool_use blocks in one response generate two status events."""
        from app import run_analysis_streaming

        tool1 = make_tool_use_block("get_realtime_quote", block_id="t1")
        tool2 = make_tool_use_block("get_stock_quote", block_id="t2")
        text_block = make_text_block()

        mock_client.messages.create.side_effect = [
            make_response("tool_use", [tool1, tool2]),
            make_response("end_turn", [text_block]),
        ]
        mock_tool_call.return_value = {"data": True}

        events = self._collect_events(run_analysis_streaming("AAPL"))

        status_events = [e for e in events if e["type"] == "status"]
        assert len(status_events) == 2
        assert mock_tool_call.call_count == 2

    @patch("app.process_tool_call")
    @patch("app.claude_client")
    def test_multi_turn_loop(self, mock_client, mock_tool_call):
        """Three sequential tool_use responses before end_turn."""
        from app import run_analysis_streaming

        tool_resp1 = make_response("tool_use", [make_tool_use_block(block_id="t1")])
        tool_resp2 = make_response("tool_use", [make_tool_use_block("get_stock_quote", block_id="t2")])
        tool_resp3 = make_response("tool_use", [make_tool_use_block("get_key_metrics", block_id="t3")])
        final = make_response("end_turn", [make_text_block()])

        mock_client.messages.create.side_effect = [tool_resp1, tool_resp2, tool_resp3, final]
        mock_tool_call.return_value = {"data": True}

        events = self._collect_events(run_analysis_streaming("AAPL"))

        status_events = [e for e in events if e["type"] == "status"]
        assert len(status_events) == 3
        assert mock_client.messages.create.call_count == 4

    @patch("app.process_tool_call")
    @patch("app.claude_client")
    def test_done_event_always_last(self, mock_client, mock_tool_call):
        """The final event is always type='done'."""
        from app import run_analysis_streaming

        mock_client.messages.create.return_value = make_response("end_turn", [make_text_block()])

        events = self._collect_events(run_analysis_streaming("AAPL"))

        assert events[-1] == {"type": "done"}

    @patch("app.process_tool_call")
    @patch("app.claude_client")
    def test_tool_status_messages(self, mock_client, mock_tool_call):
        """Each known tool maps to its correct status message."""
        from app import run_analysis_streaming

        tools = [
            ("get_realtime_quote", "Getting real-time price"),
            ("get_stock_quote", "Fetching stock data"),
            ("get_company_info", "Getting company info"),
            ("get_financial_statements", "Loading financials"),
            ("get_sec_filing", "Fetching SEC filing"),
            ("get_key_metrics", "Getting metrics"),
        ]

        tool_blocks = [make_tool_use_block(name, block_id=f"t{i}") for i, (name, _) in enumerate(tools)]
        mock_client.messages.create.side_effect = [
            make_response("tool_use", tool_blocks),
            make_response("end_turn", [make_text_block()]),
        ]
        mock_tool_call.return_value = {"data": True}

        events = self._collect_events(run_analysis_streaming("AAPL"))

        status_events = [e for e in events if e["type"] == "status"]
        for status_event, (_, expected_substr) in zip(status_events, tools):
            assert expected_substr in status_event["message"]

    @patch("app.process_tool_call")
    @patch("app.claude_client")
    def test_unknown_tool_status_fallback(self, mock_client, mock_tool_call):
        """Unknown tool name produces 'Working...' status."""
        from app import run_analysis_streaming

        block = make_tool_use_block("some_future_tool", block_id="t1")
        mock_client.messages.create.side_effect = [
            make_response("tool_use", [block]),
            make_response("end_turn", [make_text_block()]),
        ]
        mock_tool_call.return_value = {}

        events = self._collect_events(run_analysis_streaming("AAPL"))

        status = [e for e in events if e["type"] == "status"][0]
        assert status["message"] == "Working..."

    @patch("app.process_tool_call")
    @patch("app.claude_client")
    def test_sse_format(self, mock_client, mock_tool_call):
        """Each yielded string follows SSE format: 'data: <json>\\n\\n'."""
        from app import run_analysis_streaming

        mock_client.messages.create.return_value = make_response("end_turn", [make_text_block()])

        for line in run_analysis_streaming("AAPL"):
            assert line.startswith("data: ")
            assert line.endswith("\n\n")
            payload = line[len("data: "):-2]
            json.loads(payload)  # should not raise

    @patch("app.process_tool_call")
    @patch("app.claude_client")
    def test_message_accumulation(self, mock_client, mock_tool_call):
        """Messages list grows with assistant and user pairs after each tool turn."""
        from app import run_analysis_streaming

        tool_block = make_tool_use_block()
        tool_resp = make_response("tool_use", [tool_block])
        final_resp = make_response("end_turn", [make_text_block()])

        mock_client.messages.create.side_effect = [tool_resp, final_resp]
        mock_tool_call.return_value = {"data": True}

        # Consume the generator
        list(run_analysis_streaming("AAPL"))

        # The second call should have messages with assistant + user tool_result entries
        second_call_args = mock_client.messages.create.call_args_list[1]
        messages = second_call_args.kwargs.get("messages") or second_call_args[1].get("messages")

        # Original user message + assistant response + user tool_result = 3 messages
        assert len(messages) == 3
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"
        assert messages[2]["role"] == "user"
