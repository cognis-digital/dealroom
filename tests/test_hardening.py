"""Hardening tests — error paths, edge cases, and input validation.

Covers:
- Empty / None / whitespace-only directory to scan_dataroom -> DataroomError
- Non-existent output file directory -> exit 2 (not a traceback)
- MCP server: non-dict JSON payload -> proper JSON-RPC error response
- MCP server: stdout broken-pipe -> loop exits cleanly (no crash)
- CLI: init to a read-only/missing output path -> exit 2
- build_checklist with None -> DataroomError
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dealroom.core import DataroomError, scan_dataroom, build_checklist
from dealroom.cli import main
from dealroom import mcp_server


class TestScanDataroomInputValidation(unittest.TestCase):
    def test_empty_string_directory_raises(self):
        with self.assertRaises(DataroomError) as ctx:
            scan_dataroom("", "saas")
        self.assertIn("empty", str(ctx.exception).lower())

    def test_whitespace_only_directory_raises(self):
        with self.assertRaises(DataroomError):
            scan_dataroom("   ", "saas")

    def test_nonexistent_directory_raises(self):
        with self.assertRaises(DataroomError) as ctx:
            scan_dataroom("/no/such/path/xyzzy", "saas")
        self.assertIn("directory", str(ctx.exception).lower())

    def test_invalid_deal_type_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(DataroomError) as ctx:
                scan_dataroom(tmp, "unicorn")
        self.assertIn("unicorn", str(ctx.exception))


class TestBuildChecklistInputValidation(unittest.TestCase):
    def test_none_deal_type_raises(self):
        with self.assertRaises(DataroomError):
            build_checklist(None)  # type: ignore[arg-type]

    def test_empty_deal_type_raises(self):
        with self.assertRaises(DataroomError):
            build_checklist("")

    def test_whitespace_deal_type_raises(self):
        with self.assertRaises(DataroomError):
            build_checklist("   ")


class TestCliOutputFileErrors(unittest.TestCase):
    def test_unwritable_output_path_exits_2(self):
        """Writing to a directory inside a non-existent parent -> exit 2, not traceback."""
        rc = main(["init", "--deal-type", "saas",
                   "--out", "/no/such/dir/output.txt"])
        self.assertEqual(rc, 2)

    def test_unwritable_output_path_scan_exits_2(self):
        """scan --out to a bad path -> exit 2."""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        dataroom = os.path.join(repo_root, "demos", "01-basic", "sample-dataroom")
        rc = main(["scan", dataroom, "--deal-type", "saas",
                   "--out", "/no/such/dir/output.json", "--format", "json"])
        self.assertEqual(rc, 2)


class TestMcpServerNonDictInput(unittest.TestCase):
    def _roundtrip(self, raw_lines):
        stdin = io.StringIO("\n".join(raw_lines) + "\n")
        stdout = io.StringIO()
        mcp_server.run_mcp_server(stdin=stdin, stdout=stdout)
        return [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]

    def test_json_array_input_returns_invalid_request(self):
        """A JSON array (not object) should produce a -32600 invalid-request error."""
        out = self._roundtrip(['[1, 2, 3]'])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["error"]["code"], -32600)

    def test_json_string_input_returns_invalid_request(self):
        """A bare JSON string should produce a -32600 invalid-request error."""
        out = self._roundtrip(['"hello"'])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["error"]["code"], -32600)

    def test_json_null_input_returns_invalid_request(self):
        """JSON null should produce a -32600 invalid-request error."""
        out = self._roundtrip(['null'])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["error"]["code"], -32600)


class TestMcpServerBrokenPipe(unittest.TestCase):
    def test_broken_pipe_does_not_raise(self):
        """If stdout raises OSError (simulated broken pipe), the server loop exits cleanly."""

        class _BrokenPipeWriter:
            def write(self, _):
                raise OSError("broken pipe")

            def flush(self):
                pass

        stdin = io.StringIO(
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) + "\n"
        )
        # Should not raise any exception.
        try:
            mcp_server.run_mcp_server(stdin=stdin, stdout=_BrokenPipeWriter())
        except OSError:
            self.fail("run_mcp_server raised OSError on broken pipe instead of handling it")


if __name__ == "__main__":
    unittest.main()
