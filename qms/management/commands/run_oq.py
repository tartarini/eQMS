"""
Operational qualification: run the automated test suite and write evidence traced to the
user requirements in qms/validation.py.

    python manage.py run_oq --executed-by "Jane Smith" --output oq_evidence/

Writes oq_report.html (human-readable, for signing), oq_results.csv and oq_results.json.
Exits non-zero if any test fails, any traced test is missing, or a requirement with only
automated verification has no tests.
"""
import csv
import html
import io
import json
import os
import platform
import sys
import time
import unittest
from datetime import datetime, timezone

import django
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.test.utils import get_runner

from qms.validation import REQUIREMENTS, automated_test_ids


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes = {}
        self._start = {}

    def startTest(self, test):
        self._start[test.id()] = time.monotonic()
        super().startTest(test)

    def _record(self, test, outcome, detail=""):
        tid = test.id().removeprefix("qms.")
        self.outcomes[tid] = {"outcome": outcome, "detail": detail,
                              "seconds": round(time.monotonic() - self._start.get(test.id(), 0), 3)}

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "pass")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, "fail", self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, "error", self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, "skipped", reason)


def _version(pkg):
    from importlib.metadata import PackageNotFoundError, version
    try:
        return version(pkg)
    except PackageNotFoundError:
        return "not installed"




class Command(BaseCommand):
    help = "Run the operational qualification tests and write traced evidence."

    def add_arguments(self, parser):
        parser.add_argument("--output", default="oq_evidence", help="Directory for the evidence")
        parser.add_argument("--executed-by", default="", help="Name of the person running OQ")
        parser.add_argument("--release", default="", help="SAMD_QMS release / version label")

    def handle(self, *args, output, executed_by, release, **options):
        started = datetime.now(timezone.utc)
        runner_cls = get_runner(django.conf.settings)
        runner = runner_cls(verbosity=0, interactive=False)
        runner.setup_test_environment()
        suite = runner.build_suite(["qms"])
        old_config = runner.setup_databases()
        stream = io.StringIO()
        try:
            result = unittest.TextTestRunner(stream=stream, verbosity=0,
                                             resultclass=RecordingResult).run(suite)
        finally:
            runner.teardown_databases(old_config)
            runner.teardown_test_environment()
        outcomes = result.outcomes
        finished = datetime.now(timezone.utc)

        traced = automated_test_ids()
        missing = sorted(t for t in traced if t not in outcomes)
        untraced = sorted(t for t in outcomes if t not in traced)
        rows = []
        for rid, area, text, risk, tests, manual in REQUIREMENTS:
            results = [outcomes.get(t, {"outcome": "missing"})["outcome"] for t in tests]
            if not tests:
                verdict = "manual"
            elif all(r == "pass" for r in results):
                verdict = "pass"
            else:
                verdict = "fail"
            rows.append({"id": rid, "area": area, "requirement": text, "risk": risk,
                         "tests": tests, "results": results, "manual_protocols": manual,
                         "automated_verdict": verdict})

        failed_tests = sorted(t for t, o in outcomes.items() if o["outcome"] in ("fail", "error"))
        failed_reqs = [r["id"] for r in rows if r["automated_verdict"] == "fail"]
        overall = ("PASS" if not failed_tests and not missing and not failed_reqs and not untraced
               else "FAIL")

        env = {
            "release": release or "unspecified",
            "executed_by": executed_by or "unspecified",
            "started_utc": started.isoformat(timespec="seconds"),
            "finished_utc": finished.isoformat(timespec="seconds"),
            "host": platform.node(),
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "django": _version("django"),
            "django-allauth": _version("django-allauth"),
            "python-docx": _version("python-docx"),
            "database_engine": connection.vendor,
            "git_commit": settings.QMS_COMMIT,
        }
        summary = {"overall": overall, "tests_run": len(outcomes),
                   "tests_passed": sum(1 for o in outcomes.values() if o["outcome"] == "pass"),
                   "tests_failed": failed_tests, "traced_tests_missing": missing,
                   "untraced_tests": untraced, "requirements": len(rows),
                   "requirements_failed": failed_reqs,
                   "requirements_manual_only": [r["id"] for r in rows
                                                if r["automated_verdict"] == "manual"]}

        os.makedirs(output, exist_ok=True)
        with open(os.path.join(output, "oq_results.json"), "w") as fh:
            json.dump({"environment": env, "summary": summary, "requirements": rows,
                       "tests": outcomes}, fh, indent=2)
        with open(os.path.join(output, "oq_results.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["requirement", "risk", "test", "outcome", "seconds"])
            for r in rows:
                for t in r["tests"]:
                    o = outcomes.get(t, {"outcome": "missing", "seconds": ""})
                    w.writerow([r["id"], r["risk"], t, o["outcome"], o["seconds"]])
        with open(os.path.join(output, "oq_report.html"), "w") as fh:
            fh.write(_report_html(env, summary, rows, outcomes))

        self.stdout.write(f"{summary['tests_passed']}/{summary['tests_run']} tests passed; "
                          f"{len(rows)} requirements, {len(failed_reqs)} failed, "
                          f"{len(summary['requirements_manual_only'])} verified manually.")
        self.stdout.write(f"Evidence written to {os.path.abspath(output)}")
        if overall != "PASS":
            raise CommandError(f"OQ FAILED: tests {failed_tests or 'ok'}; missing {missing or 'none'}; "
                               f"requirements {failed_reqs or 'ok'}; untraced {untraced or 'none'}")
        self.stdout.write(self.style.SUCCESS("OQ PASSED"))


def _report_html(env, summary, rows, outcomes):
    e = html.escape
    badge = lambda v: {"pass": "#e5f4e4", "fail": "#fbebeb", "manual": "#e7f1fb"}.get(v, "#f9eeda")  # noqa: E731
    out = ["<!doctype html><html lang='en'><head><meta charset='utf-8'><title>SAMD_QMS OQ report"
           "</title><style>body{font:14px/1.45 system-ui,sans-serif;max-width:1100px;margin:24px "
           "auto;padding:0 16px;color:#1d1d1b}table{border-collapse:collapse;width:100%;margin:"
           "10px 0 20px;font-size:13px}th,td{border:1px solid #c9c8c2;padding:5px 7px;text-align:"
           "left;vertical-align:top}th{background:#f0efec}code{font-size:11.5px;overflow-wrap:anywhere}table.trace td:nth-child(3){width:30%}table.trace td:nth-child(4){width:42%}.sig td{height:42px}"
           "@media print{tr{break-inside:avoid}}</style></head><body>",
           f"<h1>SAMD_QMS operational qualification report</h1>",
           f"<p><strong>Result: {e(summary['overall'])}</strong> — {summary['tests_passed']} of "
           f"{summary['tests_run']} automated tests passed; {summary['requirements']} "
           f"requirements traced.</p>", "<h2>Environment</h2><table>"]
    out += [f"<tr><th>{e(k)}</th><td>{e(str(v))}</td></tr>" for k, v in env.items()]
    out.append("</table><h2>Requirements traceability</h2><table class='trace'><tr><th>ID</th><th>Risk</th>"
               "<th>Requirement</th><th>Automated tests</th><th>Manual protocols</th>"
               "<th>Automated result</th></tr>")
    for r in rows:
        tests = "<br>".join(f"<code>{e(t)}</code> {e(res)}" for t, res in
                            zip(r["tests"], r["results"])) or "—"
        out.append(f"<tr><td>{e(r['id'])}</td><td>{e(r['risk'])}</td><td>{e(r['requirement'])}"
                   f"</td><td>{tests}</td><td>{e(', '.join(r['manual_protocols']) or '—')}</td>"
                   f"<td style='background:{badge(r['automated_verdict'])}'>"
                   f"{e(r['automated_verdict'])}</td></tr>")
    out.append("</table>")
    failures = {t: o for t, o in outcomes.items() if o["outcome"] in ("fail", "error")}
    if failures:
        out.append("<h2>Failures</h2>")
        for t, o in failures.items():
            out.append(f"<h3><code>{e(t)}</code></h3><pre>{e(o['detail'])}</pre>")
    if summary["untraced_tests"]:
        out.append("<h2>Tests not traced to a requirement</h2><ul>"
                   + "".join(f"<li><code>{e(t)}</code></li>" for t in summary["untraced_tests"])
                   + "</ul>")
    out.append("<h2>Review and approval</h2><table class='sig'><tr><th>Role</th><th>Name</th>"
               "<th>Signature</th><th>Date</th></tr><tr><td>Executed by</td><td></td><td></td>"
               "<td></td></tr><tr><td>Reviewed by (QA)</td><td></td><td></td><td></td></tr>"
               f"</table><p style='color:#6b6b66;font-size:12px;text-align:center'>"
               f"{e(settings.QMS_COPYRIGHT)}</p></body></html>")
    return "".join(out)
