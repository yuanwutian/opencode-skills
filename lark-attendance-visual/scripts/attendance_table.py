#!/usr/bin/env python3
"""
Format Lark/Feishu attendance JSON data as a readable table.

Usage: lark-cli attendance user_tasks query ... --format json | python3 attendance_table.py
"""

import json, sys
from datetime import datetime, timezone

def format_table(raw):
    tz = datetime.now().astimezone().tzinfo
    lines = []
    for r in raw['data']['user_task_results']:
        date = str(r['day'])
        recs = r.get('records', [])
        if recs:
            rec = recs[0]
            ci = rec.get('check_in_record', {}).get('check_time', '')
            co = rec.get('check_out_record', {}).get('check_time', '')
            ci_t = datetime.fromtimestamp(int(ci), tz=tz).strftime('%H:%M:%S') if ci else '--:--:--'
            co_t = datetime.fromtimestamp(int(co), tz=tz).strftime('%H:%M:%S') if co else '--:--:--'
            lines.append(f"{date} | {ci_t} | {rec['check_in_result']:>10} | {co_t} | {rec['check_out_result']:>10}")
    return '\n'.join(lines)

if __name__ == '__main__':
    raw = json.load(sys.stdin)
    print(format_table(raw))
