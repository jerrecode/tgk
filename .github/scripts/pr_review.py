"""Conservative static PR check (not a substitute for human review)."""
import re
import subprocess
import sys

base = "origin/" + __import__("os").environ.get("GITHUB_BASE_REF", "main")
try:
    patch = subprocess.check_output(["git", "diff", "--unified=0", base + "...HEAD"], text=True)
except subprocess.CalledProcessError as exc:
    print("Unable to examine diff:", exc, file=sys.stderr)
    raise SystemExit(1)
rules = [
    ("pipe-shell", re.compile(r"\b(curl|wget)\b[^\n]*\|\s*(sh|bash)\b"), "Do not pipe unverified remote content into a shell."),
    ("force-push", re.compile(r"git\s+push\s+[^\n]*--force\b"), "Do not force-push from automation."),
    ("unguarded-deletion", re.compile(r"\brm\s+-rf\s+/(?:\s|$)"), "Never recursively delete the filesystem root."),
]
findings = []
for ln in patch.splitlines():
    if ln.startswith("+") and not ln.startswith("+++"):
        for name, rx, msg in rules:
            if rx.search(ln[1:]):
                findings.append(f"{name}: {msg}: {ln[:180]}")
for f in findings:
    print("::error::" + f)
if findings:
    raise SystemExit(1)
print("No configured static PR safety patterns detected; manual code review is still required.")
