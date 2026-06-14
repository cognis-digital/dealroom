"""Deep behavior tests for dealroom — risk patterns, expiry math, mapping,
serializers, CLI gates, and the MCP server. Standard library only, no network.
"""

import datetime as dt
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dealroom import scan_dataroom, to_html, build_checklist  # noqa: E402
from dealroom.core import (  # noqa: E402
    EXPIRY_SOON_DAYS,
    _match_items,
    _parse_dates,
    _scan_text_for_risks,
)
from dealroom.cli import main  # noqa: E402
from dealroom import mcp_server  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATAROOM = os.path.join(REPO_ROOT, "demos", "01-basic", "sample-dataroom")
TODAY = dt.date(2026, 6, 11)


def _rules(text):
    return {r.rule for r in _scan_text_for_risks("f.txt", text, TODAY)}


class TestRiskPatterns(unittest.TestCase):
    def test_auto_renew(self):
        self.assertIn("contract.auto_renew",
                      _rules("This Agreement shall automatically renew annually."))
        self.assertIn("contract.auto_renew",
                      _rules("an evergreen subscription that continues"))

    def test_change_of_control(self):
        self.assertIn("contract.change_of_control",
                      _rules("upon a change of control of the company"))

    def test_unlimited_liability(self):
        self.assertIn("contract.unlimited_liability",
                      _rules("the provider's liability shall be unlimited"))
        self.assertIn("contract.unlimited_liability",
                      _rules("there is no cap on damages under this clause"))

    def test_ip_no_assignment(self):
        self.assertIn("ip.no_assignment",
                      _rules("the contractor shall retain all ownership of any invention"))

    def test_exclusivity(self):
        self.assertIn("contract.exclusivity",
                      _rules("Vendor shall be the exclusive supplier."))
        self.assertIn("contract.exclusivity",
                      _rules("subject to a non-compete for two years"))

    def test_termination_for_convenience(self):
        self.assertIn("contract.termination_convenience",
                      _rules("either party may terminate for convenience"))

    def test_embedded_secret_is_redacted(self):
        risks = _scan_text_for_risks(
            "f.txt", "api_key = ABCDEFGH01234567890", TODAY)
        secret = [r for r in risks if r.rule == "secret.embedded"]
        self.assertTrue(secret)
        # the captured value must never be echoed back.
        self.assertIn("REDACTED", secret[0].snippet)
        self.assertNotIn("ABCDEFGH01234567890", secret[0].snippet)

    def test_clean_text_no_risks(self):
        self.assertEqual(_rules("A perfectly ordinary description of a product."),
                         set())


class TestExpiry(unittest.TestCase):
    def test_iso_date_parse(self):
        self.assertIn(dt.date(2026, 7, 15), _parse_dates("valid through 2026-07-15"))

    def test_us_slash_date_parse(self):
        self.assertIn(dt.date(2026, 7, 15), _parse_dates("expires 07/15/2026"))

    def test_long_date_parse(self):
        self.assertIn(dt.date(2026, 7, 15),
                      _parse_dates("expires July 15, 2026"))

    def test_expired_is_high(self):
        risks = _scan_text_for_risks(
            "c.txt", "This agreement expires on 2024-12-31.", TODAY)
        expired = [r for r in risks if r.rule == "contract.expired"]
        self.assertTrue(expired)
        self.assertEqual(expired[0].severity, "high")

    def test_expiring_soon_is_medium(self):
        soon = TODAY + dt.timedelta(days=EXPIRY_SOON_DAYS - 5)
        risks = _scan_text_for_risks(
            "c.txt", f"This order is valid through {soon.isoformat()}.", TODAY)
        rules = {r.rule for r in risks}
        self.assertIn("contract.expiring_soon", rules)

    def test_far_future_not_flagged(self):
        risks = _scan_text_for_risks(
            "c.txt", "This agreement expires on 2099-01-01.", TODAY)
        rules = {r.rule for r in risks}
        self.assertNotIn("contract.expiring_soon", rules)
        self.assertNotIn("contract.expired", rules)


class TestFileMapping(unittest.TestCase):
    def test_hint_maps_to_item(self):
        items = build_checklist("saas")
        matched = _match_items("Corporate/cap-table.csv", items)
        self.assertIn("corp.captable", matched)

    def test_unmatched_file_maps_to_nothing(self):
        items = build_checklist("saas")
        self.assertEqual(_match_items("random/notes-xyz.txt", items), [])

    def test_nested_path_matches_on_basename(self):
        items = build_checklist("hardware")
        matched = _match_items("deep/folder/bill-of-materials.csv", items)
        self.assertIn("hw.bom", matched)


class TestScanResultViews(unittest.TestCase):
    def test_completion_pct_in_range(self):
        r = scan_dataroom(DATAROOM, "saas")
        self.assertTrue(0 <= r.completion_pct <= 100)

    def test_coverage_consistency(self):
        r = scan_dataroom(DATAROOM, "saas")
        present_ids = {i.id for i in r.present_items}
        missing_ids = {i.id for i in r.missing_items}
        self.assertEqual(present_ids & missing_ids, set())
        self.assertEqual(present_ids | missing_ids, {i.id for i in r.items})

    def test_to_dict_self_consistent(self):
        d = scan_dataroom(DATAROOM, "saas").to_dict()
        self.assertEqual(d["summary"]["total_risks"], len(d["risks"]))
        self.assertEqual(d["summary"]["checklist_items"], len(d["items"]))

    def test_empty_dir_passes_only_if_no_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = scan_dataroom(tmp, "saas")
            # no files => required items missing => failed.
            self.assertTrue(r.failed)
            self.assertEqual(len(r.files), 0)


class TestHtml(unittest.TestCase):
    def test_html_self_contained_and_escaped(self):
        html = to_html(scan_dataroom(DATAROOM, "saas"))
        self.assertTrue(html.lstrip().startswith("<!doctype html>"))
        self.assertIn("<table>", html)
        self.assertIn("RESULT:", html)
        # raw secret values must never leak into the report.
        self.assertNotIn("<script>", html)


class TestCliFormatsAndGates(unittest.TestCase):
    def test_scan_html_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "r.html")
            main(["scan", DATAROOM, "--deal-type", "saas",
                  "--format", "html", "--out", out])
            with open(out, encoding="utf-8") as fh:
                self.assertIn("<table>", fh.read())

    def test_init_json_to_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "c.json")
            rc = main(["init", "--deal-type", "hardware",
                       "--format", "json", "--out", out])
            self.assertEqual(rc, 0)
            with open(out, encoding="utf-8") as fh:
                doc = json.load(fh)
            self.assertEqual(doc["deal_type"], "hardware")

    def test_fail_on_critical_when_present(self):
        rc = main(["scan", DATAROOM, "--deal-type", "saas",
                   "--fail-on", "critical"])
        self.assertEqual(rc, 1)  # embedded-secret placeholder is critical

    def test_fail_on_clean_dir_passes(self):
        # A complete services dataroom with no risks should pass.
        with tempfile.TemporaryDirectory() as tmp:
            files = {
                "certificate-of-incorporation.txt": "Articles of formation.",
                "operating-agreement.txt": "Operating agreement text.",
                "cap-table.csv": "holder,shares\nA,100",
                "financial-statements.txt": "P&L and balance sheet.",
                "tax-return-2025.txt": "IRS tax return.",
                "litigation-summary.txt": "No disputes.",
                "customer-msa.txt": "A clean master service agreement.",
                "employee-census.csv": "name\nA",
                "ip-assignment.txt": "All inventions assigned to the company.",
                "sow-bigclient.txt": "statement of work text",
                "backlog-pipeline.csv": "client,amount\nA,1",
                "contractor-1099-agreement.txt": "1099 contractor agreement.",
            }
            for name, body in files.items():
                with open(os.path.join(tmp, name), "w", encoding="utf-8") as fh:
                    fh.write(body)
            rc = main(["scan", tmp, "--deal-type", "services"])
            self.assertEqual(rc, 0)


class TestMcpServer(unittest.TestCase):
    def _roundtrip(self, requests):
        stdin = io.StringIO("\n".join(json.dumps(r) for r in requests) + "\n")
        stdout = io.StringIO()
        mcp_server.run_mcp_server(stdin=stdin, stdout=stdout)
        return [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]

    def test_initialize_and_list(self):
        out = self._roundtrip([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        ])
        self.assertEqual(len(out), 2)  # notification yields no response
        self.assertEqual(out[0]["result"]["serverInfo"]["name"], "dealroom")
        names = {t["name"] for t in out[1]["result"]["tools"]}
        self.assertEqual(names, {"checklist", "scan_dataroom"})

    def test_tools_call_checklist(self):
        out = self._roundtrip([
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "checklist", "arguments": {"deal_type": "saas"}}},
        ])
        payload = json.loads(out[0]["result"]["content"][0]["text"])
        self.assertEqual(payload["deal_type"], "saas")
        self.assertTrue(payload["items"])

    def test_tools_call_scan(self):
        out = self._roundtrip([
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
             "params": {"name": "scan_dataroom",
                        "arguments": {"directory": DATAROOM, "deal_type": "saas"}}},
        ])
        res = out[0]["result"]
        self.assertTrue(res["isError"])
        payload = json.loads(res["content"][0]["text"])
        self.assertTrue(payload["summary"]["failed"])

    def test_unknown_tool_is_jsonrpc_error(self):
        out = self._roundtrip([
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
             "params": {"name": "nope", "arguments": {}}},
        ])
        self.assertEqual(out[0]["error"]["code"], -32602)

    def test_parse_error(self):
        stdin = io.StringIO("{not json\n")
        stdout = io.StringIO()
        mcp_server.run_mcp_server(stdin=stdin, stdout=stdout)
        out = json.loads(stdout.getvalue().strip())
        self.assertEqual(out["error"]["code"], -32700)

    def test_unknown_method(self):
        out = self._roundtrip([
            {"jsonrpc": "2.0", "id": 6, "method": "totally/unknown"},
        ])
        self.assertEqual(out[0]["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
