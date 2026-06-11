"""Smoke tests for dealroom. Standard library only, no network."""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dealroom import (
    TOOL_NAME,
    TOOL_VERSION,
    DEAL_TYPES,
    build_checklist,
    checklist_to_dict,
    scan_dataroom,
)
from dealroom.cli import main

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATAROOM = os.path.join(REPO_ROOT, "demos", "01-basic", "sample-dataroom")


class TestMetadata(unittest.TestCase):
    def test_metadata(self):
        self.assertEqual(TOOL_NAME, "dealroom")
        self.assertTrue(TOOL_VERSION)

    def test_deal_types(self):
        self.assertEqual(set(DEAL_TYPES), {"saas", "services", "hardware"})


class TestChecklist(unittest.TestCase):
    def test_each_deal_type_builds(self):
        for dt in DEAL_TYPES:
            items = build_checklist(dt)
            self.assertTrue(items)
            ids = [i.id for i in items]
            self.assertEqual(len(ids), len(set(ids)), f"dup ids in {dt}")
            # every deal type carries the common corporate items.
            self.assertIn("corp.captable", ids)
            # at least one required item.
            self.assertTrue(any(i.required for i in items))

    def test_saas_has_security_item(self):
        ids = {i.id for i in build_checklist("saas")}
        self.assertIn("saas.security", ids)

    def test_unknown_deal_type_raises(self):
        from dealroom.core import DataroomError
        with self.assertRaises(DataroomError):
            build_checklist("widgets")

    def test_checklist_to_dict_shape(self):
        d = checklist_to_dict("hardware")
        self.assertEqual(d["deal_type"], "hardware")
        self.assertEqual(d["item_count"], len(d["items"]))


class TestScanEngine(unittest.TestCase):
    def test_demo_scan_failed(self):
        result = scan_dataroom(DATAROOM, "saas")
        self.assertTrue(result.failed)
        # required items intentionally missing in the demo dataroom.
        missing = {i.id for i in result.missing_required}
        self.assertIn("saas.security", missing)
        self.assertIn("saas.privacy", missing)

    def test_demo_scan_present_items(self):
        result = scan_dataroom(DATAROOM, "saas")
        present = {i.id for i in result.present_items}
        self.assertIn("corp.captable", present)
        self.assertIn("saas.metrics", present)
        self.assertIn("legal.contracts", present)

    def test_demo_risks_detected(self):
        result = scan_dataroom(DATAROOM, "saas")
        rules = {r.rule for r in result.risks}
        self.assertIn("contract.unlimited_liability", rules)
        self.assertIn("contract.change_of_control", rules)
        self.assertIn("contract.auto_renew", rules)
        self.assertIn("ip.no_assignment", rules)
        self.assertIn("contract.expired", rules)


class TestCli(unittest.TestCase):
    def test_init_exit_zero(self):
        self.assertEqual(main(["init", "--deal-type", "services"]), 0)

    def test_scan_demo_fails_and_json(self):
        proc = subprocess.run(
            [sys.executable, "-m", "dealroom", "scan", DATAROOM,
             "--deal-type", "saas", "--format", "json"],
            cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertTrue(data["summary"]["failed"])
        self.assertGreater(data["summary"]["total_risks"], 0)

    def test_report_table_runs(self):
        self.assertEqual(
            main(["report", DATAROOM, "--deal-type", "saas"]), 1)

    def test_missing_dir_exits_2(self):
        self.assertEqual(
            main(["scan", "/no/such/dataroom", "--deal-type", "saas"]), 2)

    def test_no_command_exits_2(self):
        self.assertEqual(main([]), 2)


if __name__ == "__main__":
    unittest.main()
