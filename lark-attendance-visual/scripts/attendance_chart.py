#!/usr/bin/env python3
"""
Generate cyber-style attendance chart from Lark/Feishu attendance JSON data.

Usage: lark-cli attendance user_tasks query ... --format json | python3 attendance_chart.py [output_path]

Arguments:
  output_path  Optional. Path to save the chart PNG (default: ~/.opencode/tmp/attendance_chart.png)
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
import matplotlib.ticker as ticker
from matplotlib.lines import Line2D
import subprocess, os, json, sys
from datetime import datetime, timezone
import numpy as np

def find_zh_font():
    font_path = None
    try:
        for line in subprocess.run(['fc-list', ':lang=zh'], capture_output=True, text=True, timeout=5).stdout.strip().split('\n'):
            if line:
                p = line.split(':')[0].strip()
                if p and os.path.exists(p):
                    font_path = p
                    break
    except Exception:
        pass
    return FontProperties(fname=font_path) if font_path else FontProperties(family='sans-serif')

def parse_data(raw):
    tz = datetime.now().astimezone().tzinfo
    labels, ci_vs, co_vs, wh_vs, names = [], [], [], [], []
    for r in raw['data']['user_task_results']:
        d = str(r['day'])
        p = datetime.strptime(d, '%Y%m%d')
        lb = p.strftime('%m-%d')
        if p.weekday() >= 5:
            lb += '\n(周%s)' % ('六' if p.weekday() == 5 else '日')
        labels.append(lb)
        names.append(r.get('employee_name', ''))
        recs = r.get('records', [])
        if recs:
            rc = recs[0]
            ci = rc.get('check_in_record', {}).get('check_time', '')
            co = rc.get('check_out_record', {}).get('check_time', '')
            ci_r, co_r = rc.get('check_in_result', ''), rc.get('check_out_result', '')
            c = datetime.fromtimestamp(int(ci), tz=tz) if ci and ci_r not in ('NoNeedCheck', 'Todo', 'Lack') else None
            o = datetime.fromtimestamp(int(co), tz=tz) if co and co_r not in ('NoNeedCheck', 'Todo', 'Lack') else None
            ci_vs.append(c.hour + c.minute / 60 if c else None)
            co_vs.append(o.hour + o.minute / 60 if o else None)
            wh_vs.append(round(co_vs[-1] - ci_vs[-1], 2) if ci_vs[-1] and co_vs[-1] else None)
        else:
            ci_vs.append(None)
            co_vs.append(None)
            wh_vs.append(None)
    return labels, ci_vs, co_vs, wh_vs, names

def draw_chart(labels, ci_vs, co_vs, wh_vs, names, output_path):
    x = range(len(labels))
    BG, CARD, GRID = '#0A0E17', '#111827', '#1E293B'
    CYAN, AMBER, NEON = '#00F0FF', '#FFB300', '#00FF41'
    TP, TS = '#F1F5F9', '#64748B'
    zh_font = find_zh_font()

    plt.rcParams.update({
        'axes.facecolor': CARD, 'axes.edgecolor': GRID,
        'text.color': TP, 'xtick.color': TS, 'ytick.color': TS,
        'figure.facecolor': BG
    })

    fig = plt.figure(figsize=(16, 10), facecolor=BG)
    hdr = fig.add_axes([0, 0.93, 1, 0.07], facecolor=CARD)
    hdr.axis('off')
    hdr.scatter(0.02, 0.5, s=40, color=NEON, alpha=0.8, zorder=5)
    hdr.scatter(0.02, 0.5, s=120, color=NEON, alpha=0.2, zorder=4)
    hdr.text(0.04, 0.5, 'ATTENDANCE MONITOR', fontsize=16, fontweight='bold', color=CYAN, fontfamily='monospace', va='center')
    hdr.text(0.04, 0.15, 'SYSTEM v2.4.1', fontsize=7, color=TS, fontfamily='monospace', va='center')
    employee_name = names[0] if names else 'UNKNOWN'
    hdr.text(0.5, 0.5, f'{datetime.now().strftime("%Y.%m")}  |  {employee_name}', fontsize=13, color=TP, fontproperties=zh_font, va='center', ha='center')
    hdr.text(0.88, 0.6, '● ONLINE', fontsize=8, color=NEON, fontfamily='monospace', va='center')
    hdr.text(0.88, 0.3, f'{len([v for v in wh_vs if v])} RECORDS', fontsize=8, color=TS, fontfamily='monospace', va='center')
    hdr.axhline(y=0, color=GRID, lw=0.5)

    ax1 = fig.add_axes([0.07, 0.38, 0.87, 0.50], facecolor=CARD)
    ax1.set_axisbelow(True)
    ax1.yaxis.grid(True, alpha=0.06, color=CYAN, linestyle='-', lw=0.5)
    ax1.text(-0.02, 1.02, '● SHIFT TIMELINE', fontsize=9, color=NEON, fontfamily='monospace', fontweight='bold', transform=ax1.transAxes)

    vxi = [i for i, v in enumerate(ci_vs) if v]
    vyi = [v for v in ci_vs if v]
    vxo = [i for i, v in enumerate(co_vs) if v]
    vyo = [v for v in co_vs if v]

    for ry, rc, rl in [(9, CYAN, '09:00'), (18, AMBER, '18:00')]:
        ax1.axhline(y=ry, color=rc, ls=':', alpha=0.08, lw=1)
        ax1.text(len(labels) - 0.3, ry + 0.05, rl, color=rc, alpha=0.15, fontsize=7, fontfamily='monospace', ha='right', va='bottom')

    if len(vxi) >= 2:
        p_ci = np.poly1d(np.polyfit(vxi, vyi, min(3, len(vxi) - 1)))
        ax1.fill_between(np.linspace(min(vxi), max(vxi), 200), p_ci(np.linspace(min(vxi), max(vxi), 200)), 7, alpha=0.04, color=CYAN)
    if len(vxo) >= 2:
        p_co = np.poly1d(np.polyfit(vxo, vyo, min(3, len(vxo) - 1)))
        ax1.fill_between(np.linspace(min(vxo), max(vxo), 200), p_co(np.linspace(min(vxo), max(vxo), 200)), 7, alpha=0.04, color=AMBER)

    for lw, a in [(5, 0.08), (3, 0.15), (1.8, 0.7)]:
        ax1.plot(vxi, vyi, '-', color=CYAN, lw=lw, alpha=a, zorder=3)
        ax1.plot(vxo, vyo, '-', color=AMBER, lw=lw, alpha=a, zorder=3)
    for s, a in [(280, 0.12), (140, 0.7)]:
        ax1.scatter(vxi, vyi, s=s, color=CYAN, alpha=a, zorder=4)
        ax1.scatter(vxo, vyo, s=s, color=AMBER, alpha=a, zorder=4)
    ax1.scatter(vxi, vyi, s=60, color='white', alpha=0.9, zorder=5)
    ax1.scatter(vxo, vyo, s=60, color='white', alpha=0.9, zorder=5)

    for i, v in zip(vxi, vyi):
        h, m = int(v), int((v - int(v)) * 60)
        ax1.annotate(f'{h:02d}:{m:02d}', (i, v), xytext=(0, 16), textcoords='offset points',
                     ha='center', fontsize=8.5, color=CYAN, fontweight='bold', fontfamily='monospace',
                     bbox=dict(boxstyle='round,pad=0.15', facecolor='#0A0E17', edgecolor=CYAN, alpha=0.85, lw=0.8))
    for i, v in zip(vxo, vyo):
        h, m = int(v), int((v - int(v)) * 60)
        ax1.annotate(f'{h:02d}:{m:02d}', (i, v), xytext=(0, -20), textcoords='offset points',
                     ha='center', fontsize=8.5, color=AMBER, fontweight='bold', fontfamily='monospace',
                     bbox=dict(boxstyle='round,pad=0.15', facecolor='#0A0E17', edgecolor=AMBER, alpha=0.85, lw=0.8))

    ax1.set_xticks(list(x))
    ax1.set_xticklabels(labels, fontsize=8.5, color=TS, fontproperties=zh_font)
    ax1.set_ylabel('CLOCK TIME', fontsize=9, color=TS, fontfamily='monospace', labelpad=8)
    ax1.set_ylim(7, 21)
    ax1.set_xlim(-0.5, len(labels) - 0.5)
    ax1.yaxis.set_major_locator(ticker.MultipleLocator(1))
    ax1.tick_params(axis='y', labelsize=7, colors=TS)

    leg = ax1.legend(
        handles=[
            Line2D([0], [0], marker='o', color='w', markerfacecolor=CYAN, markersize=9, lw=0),
            Line2D([0], [0], marker='o', color='w', markerfacecolor=AMBER, markersize=9, lw=0)
        ],
        labels=['CHECK IN', 'CHECK OUT'], loc='upper left', fontsize=8,
        framealpha=0.8, facecolor='#0D1117', edgecolor=GRID, labelcolor=TP
    )
    leg.get_frame().set_linewidth(0.5)

    ax2 = fig.add_axes([0.07, 0.06, 0.87, 0.28], facecolor=CARD)
    ax2.text(-0.02, 1.12, '● WORK DURATION', fontsize=9, color=NEON, fontfamily='monospace', fontweight='bold', transform=ax2.transAxes)
    work = [v or 0 for v in wh_vs]
    bc = []
    for v in wh_vs:
        if v and v > 0:
            bc.append(NEON if v >= 9.2 else CYAN if v >= 9.0 else '#7C3AED')
        else:
            bc.append(GRID)
    bars = ax2.bar(x, work, width=0.5, color=bc, alpha=0.85, zorder=3, edgecolor='none')
    for i, (b, v) in enumerate(zip(bars, wh_vs)):
        if v and v > 0:
            ax2.scatter(b.get_x() + b.get_width() / 2, v, s=400, color=bc[i], alpha=0.08, zorder=2)
            ax2.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.12, f'{v:.2f}h',
                     ha='center', fontsize=9, fontweight='bold', color=TP, fontfamily='monospace',
                     bbox=dict(boxstyle='round,pad=0.1', facecolor='#0A0E17', edgecolor=bc[i], alpha=0.7, lw=0.5))

    ax2.set_xticks(list(x))
    ax2.set_xticklabels(labels, fontsize=8.5, color=TS, fontproperties=zh_font)
    ax2.set_ylabel('HOURS', fontsize=9, color=TS, fontfamily='monospace', labelpad=8)
    ax2.set_ylim(0, 11)
    ax2.set_xlim(-0.5, len(labels) - 0.5)
    ax2.yaxis.set_major_locator(ticker.MultipleLocator(2))
    ax2.tick_params(axis='y', labelsize=7, colors=TS)
    ax2.yaxis.grid(True, alpha=0.06, color=CYAN, linestyle='-', lw=0.5)
    ax2.set_axisbelow(True)
    ax2.axhline(y=8, color=TS, ls=':', alpha=0.15, lw=0.5)
    ax2.axhline(y=0, color=GRID, lw=0.5)

    fig.text(0.5, 0.005, f'LARK-CLI | FEISHU ATTENDANCE API | GENERATED {datetime.now().strftime("%Y-%m-%d %H:%M")}',
             fontsize=6.5, color=TS, ha='center', fontfamily='monospace', alpha=0.4)

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor=BG, edgecolor='none')
    plt.close()
    print(f'Chart saved to {output_path}')

if __name__ == '__main__':
    output_path = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser('~/.opencode/tmp/attendance_chart.png')
    raw = json.load(sys.stdin)
    labels, ci_vs, co_vs, wh_vs, names = parse_data(raw)
    draw_chart(labels, ci_vs, co_vs, wh_vs, names, output_path)
