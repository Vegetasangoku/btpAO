#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Functional test for the Batch-11 additions to gantt_service.py, loading the REAL
patched module by path (matching the Batch-9 discipline) after stubbing its one
unavailable dependency (app.core.storage), so this exercises the actual shipped
class methods (self.compute_critical_path / self.seed_tasks_from_phases /
self.generate_gantt_chart_png_from_tasks), not a hand-copied lookalike.
"""
import sys
import types
import importlib.util
import datetime

GANTT_SERVICE_PATH = sys.argv[1]

app_pkg = types.ModuleType("app")
app_pkg.__path__ = []
sys.modules["app"] = app_pkg
app_core_pkg = types.ModuleType("app.core")
app_core_pkg.__path__ = []
sys.modules["app.core"] = app_core_pkg
app_core_storage = types.ModuleType("app.core.storage")


class _FakeStorage:
    def upload_file(self, tenant_id, subpath, file_obj, content_type):
        return f"tenants/{tenant_id}/{subpath}"


app_core_storage.storage_service = _FakeStorage()
sys.modules["app.core.storage"] = app_core_storage

spec = importlib.util.spec_from_file_location("gantt_service_under_test", GANTT_SERVICE_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print("MODULE LOADED OK:", GANTT_SERVICE_PATH)

svc = mod.GanttService()
D = datetime.date

# Test 1: diamond DAG critical path (via the REAL bound method, not the standalone copy)
diamond = [
    {"id": "A", "start_date": D(2026, 1, 1), "end_date": D(2026, 1, 8), "depends_on": []},
    {"id": "B", "start_date": D(2026, 1, 8), "end_date": D(2026, 1, 22), "depends_on": ["A"]},
    {"id": "C", "start_date": D(2026, 1, 8), "end_date": D(2026, 1, 12), "depends_on": ["A"]},
    {"id": "D", "start_date": D(2026, 1, 22), "end_date": D(2026, 1, 29), "depends_on": ["B", "C"]},
]
result = svc.compute_critical_path(diamond)
assert result == {"A", "B", "D"}, f"expected A,B,D critical, got {result}"
print("TEST 1 PASSED: real bound compute_critical_path matches standalone-verified logic.")

# Test 2: seed_tasks_from_phases produces a correct sequential FS chain
phases = [
    {"phase": "1. Terrassements", "duree_semaines": 2, "jalon": "Plateforme prête"},
    {"phase": "2. Fondations", "duree_semaines": 3, "jalon": None},
    {"phase": "3. Livraison", "duree_semaines": 1, "jalon": "Remise des clés"},
]
seeded = svc.seed_tasks_from_phases(phases, "2026-03-01")
assert len(seeded) == 3
assert seeded[0]["depends_on"] == []
assert seeded[1]["depends_on"] == [seeded[0]["id"]]
assert seeded[2]["depends_on"] == [seeded[1]["id"]]
assert seeded[0]["start_date"] == D(2026, 3, 1)
assert seeded[0]["end_date"] == D(2026, 3, 15)  # 2 weeks = 14 days
assert seeded[1]["start_date"] == seeded[0]["end_date"]
assert seeded[0]["milestone_label"] == "Plateforme prête"
assert seeded[1]["milestone_label"] is None
# All 3 phases chained sequentially -> all critical (no parallel branch)
seeded_critical = svc.compute_critical_path(seeded)
assert seeded_critical == {t["id"] for t in seeded}
print("TEST 2 PASSED: seed_tasks_from_phases builds a correct sequential FS chain, all critical.")

# Test 3: seed_tasks_from_phases([]) -> [] (never invents a default)
assert svc.seed_tasks_from_phases([], "2026-03-01") == []
print("TEST 3 PASSED: empty phases -> empty task list, no invented default.")

# Test 4: generate_gantt_chart_png_from_tasks runs end-to-end and uploads to the
# SAME storage key convention as the original phases-based method.
result = svc.generate_gantt_chart_png_from_tasks("tenant-x", "proj-y", "Chantier Test", seeded)
assert result["s3_key"] == "tenants/tenant-x/visuals/proj-y/gantt_planning.png"
assert result["critical_task_count"] == 3
assert result["bytes_length"] > 0
print("TEST 4 PASSED: PNG renders end-to-end from real tasks, uploads to the canonical s3 key,",
      f"{result['bytes_length']} bytes, {result['critical_task_count']} critical task(s).")

# Test 5: empty tasks list falls back to the original generic-default generator without crashing
fallback = svc.generate_gantt_chart_png_from_tasks("tenant-x", "proj-z", "Chantier Vide", [])
assert fallback["bytes_length"] > 0
print("TEST 5 PASSED: empty task list falls back to generate_gantt_chart_png without crashing.")

print("\nALL BATCH-11 GANTT_SERVICE FUNCTIONAL TESTS PASSED.")
