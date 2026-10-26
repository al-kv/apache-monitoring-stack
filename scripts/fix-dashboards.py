#!/usr/bin/env python3
"""
fix-dashboards.py — one-shot patch for apache-monitoring-stack dashboards.

Fixes:
  1. `|~ "5xx"` / `|~ "4xx"` / `|~ "404"` line-filters → `status` label selectors
  2. Removes no-op `| label_format ip=`{{.ip}}``
  3. Adds `| regexp ... | unwrap bytes` where the pipeline is missing it
  4. Sets "id": null (avoids import conflicts)
  5. Converts `selected_ip` (custom) → Loki query variable (topk 50 over 1h)

Idempotent: safe to run multiple times.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DASHBOARDS = ROOT / "grafana" / "provisioning" / "dashboards"

# LogQL rewrites
STATUS_PATTERNS = [
    (re.compile(r'\{job="apache_access"\}\s*\|\~\s*"5\[0-9\]\{2\}"'),
     '{job="apache_access", status=~"5.."}'),
    (re.compile(r'\{job="apache_access"\}\s*\|\~\s*"4\[0-9\]\{2\}"'),
     '{job="apache_access", status=~"4.."}'),
    (re.compile(r'\{job="apache_access"\}\s*\|\~\s*"\[45\]\[0-9\]\{2\}"'),
     '{job="apache_access", status=~"[45].."}'),
    (re.compile(r'\{job="apache_access"\}\s*\|\~\s*"404"'),
     '{job="apache_access", status="404"}'),
]

NOOP_LABEL = re.compile(r'\s*\|\s*label_format\s+ip=`\{\{\.ip\}\}`')

BARE_UNWRAP = re.compile(r'\{job="apache_access"\}\s*\|\s*unwrap\s+bytes')

BYTES_REGEXP = 'regexp `\\s(?P<bytes>\\d+)(?:\\s|-)`'

# detalizaciya-po-ip.json: query-based variable
IP_VAR_DEFINITION = (
    'topk(50, sum by (ip) '
    '(count_over_time({job="apache_access"} | regexp `^(?P<ip>\\S+)` [1h])))'
)
IP_VAR_REGEX = '/ip="(?P<text>[^"]+)"/'


def fix_expr(expr: str) -> str:
    if not expr:
        return expr

    for pattern, repl in STATUS_PATTERNS:
        expr = pattern.sub(repl, expr)

    expr = NOOP_LABEL.sub('', expr)

    # Only inject regexp when `unwrap bytes` appears with NO earlier `| regexp`
    if 'unwrap bytes' in expr and '| regexp' not in expr.split('unwrap')[0]:
        expr = BARE_UNWRAP.sub(
            lambda _: '{job="apache_access"} | ' + BYTES_REGEXP + ' | unwrap bytes',
            expr,
        )
    return expr


def walk(obj):
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if k == 'expr' and isinstance(v, str):
                obj[k] = fix_expr(v)
            else:
                walk(v)
    elif isinstance(obj, list):
        for v in obj:
            walk(v)


def fix_ip_template_variable(var: dict) -> None:
    var.clear()
    var.update({
        "current": {},
        "datasource": {"type": "loki", "uid": "loki"},
        "definition": IP_VAR_DEFINITION,
        "hide": 0,
        "includeAll": True,
        "label": "IP",
        "multi": True,
        "name": "selected_ip",
        "options": [],
        "query": {"query": IP_VAR_DEFINITION, "refId": "IPVariableQuery"},
        "refresh": 2,
        "regex": IP_VAR_REGEX,
        "sort": 1,
        "type": "query",
    })


def fix_dashboard(path: Path) -> None:
    print(f"→ {path.name}")
    with path.open() as f:
        doc = json.load(f)

    if isinstance(doc.get('id'), int):
        doc['id'] = None
        print("  · id → null")

    walk(doc)

    if path.name == 'detalizaciya-po-ip.json':
        for var in doc.get('templating', {}).get('list', []):
            if var.get('name') == 'selected_ip' and var.get('type') == 'custom':
                fix_ip_template_variable(var)
                print("  · selected_ip → query variable (topk 50, last 1h)")

    with path.open('w') as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write('\n')


def main() -> int:
    if not DASHBOARDS.is_dir():
        print(f"ERROR: {DASHBOARDS} not found. Run from repo root.", file=sys.stderr)
        return 1
    for p in sorted(DASHBOARDS.glob('*.json')):
        fix_dashboard(p)
    print("\n✅ Dashboards patched. Review with `git diff` before committing.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
