#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书日报（汇报任务）查询脚本 —— lark-report skill 配套工具。

封装 POST /open-apis/report/v1/tasks/query，通过 subprocess 调用 `lark-cli api`
复用其鉴权（不直接处理 token）。内置：日期 → UTC+8 时间戳换算、自动翻页、
中文格式化输出。

用法示例：
    python report_query.py                      # 默认查"今天"
    python report_query.py today                # 今天
    python report_query.py yesterday            # 昨天
    python report_query.py week                 # 本周（周一 ~ 今天）
    python report_query.py month                # 本月 1 号 ~ 今天
    python report_query.py 2026-06-01           # 指定单日
    python report_query.py 2026-06-01 2026-06-29  # 指定区间（含结束当天）
    python report_query.py today --json         # 输出聚合后的原始 JSON
    python report_query.py week --user-id ou_xxx --as bot  # 指定用户/应用身份

退出码：0 成功（含"无数据"）；非 0 表示调用或解析失败。
"""

import argparse
import datetime
import json
import shutil
import subprocess
import sys

API_PATH = "/open-apis/report/v1/tasks/query"
TZ = datetime.timezone(datetime.timedelta(hours=8))  # 北京时间 UTC+8


# ---------- 日期解析 ----------

def _midnight(d: datetime.date) -> int:
    """某日 00:00（UTC+8）的 Unix 秒。"""
    return int(datetime.datetime(d.year, d.month, d.day, tzinfo=TZ).timestamp())


def resolve_range(tokens):
    """
    把命令行里的日期描述解析为 (start_ts, end_ts, label)。
    时间窗一律「左闭右开」：end 取结束日的【次日】00:00，以覆盖当天最晚提交。
    """
    today = datetime.datetime.now(TZ).date()

    if not tokens:
        tokens = ["today"]

    kw = tokens[0].lower()

    if kw == "today":
        return _midnight(today), _midnight(today + datetime.timedelta(days=1)), "今天"
    if kw == "yesterday":
        y = today - datetime.timedelta(days=1)
        return _midnight(y), _midnight(today), "昨天"
    if kw == "week":
        monday = today - datetime.timedelta(days=today.weekday())
        return _midnight(monday), _midnight(today + datetime.timedelta(days=1)), "本周"
    if kw == "month":
        first = today.replace(day=1)
        return _midnight(first), _midnight(today + datetime.timedelta(days=1)), "本月"

    # 显式日期：YYYY-MM-DD [YYYY-MM-DD]
    def parse(s):
        return datetime.datetime.strptime(s, "%Y-%m-%d").date()

    try:
        start = parse(tokens[0])
        end = parse(tokens[1]) if len(tokens) > 1 else start
    except (ValueError, IndexError):
        raise SystemExit(
            f"无法解析日期：{tokens!r}\n"
            "支持 today / yesterday / week / month 或 YYYY-MM-DD [YYYY-MM-DD]"
        )

    if end < start:
        start, end = end, start
    label = f"{start:%Y-%m-%d}" if start == end else f"{start:%Y-%m-%d} ~ {end:%Y-%m-%d}"
    # end 含结束当天 → +1 天作为右开边界
    return _midnight(start), _midnight(end + datetime.timedelta(days=1)), label


# ---------- 调用 lark-cli ----------

def _run_larkcli(payload: dict, identity: str):
    exe = shutil.which("lark-cli") or "lark-cli"
    args = [exe, "api", "POST", API_PATH, "--as", identity,
            "--data", json.dumps(payload, ensure_ascii=False), "--json"]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8")
    except OSError:
        # Windows 上 .cmd 兜底
        proc = subprocess.run(["cmd", "/c", *args], capture_output=True,
                              text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise SystemExit(f"lark-cli 调用失败（exit {proc.returncode}）：\n{proc.stderr or proc.stdout}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise SystemExit(f"无法解析 lark-cli 输出为 JSON：\n{proc.stdout}")


def query(start_ts, end_ts, identity="user", user_id=None, rule_id=None, page_size=20):
    """自动翻页，返回聚合后的 items 列表（user / bot 身份都可能分页）。

    注意：user 身份的 page_token 实为上一条的 task_id，带它翻页会把同一条再返回一遍，
    因此必须按 task_id 去重，并在无新增时主动停止，避免重复 / 死循环。
    """
    items, seen, page_token = [], set(), ""
    while True:
        payload = {
            "commit_start_time": start_ts,
            "commit_end_time": end_ts,
            "page_token": page_token,
            "page_size": page_size,
        }
        if user_id:
            payload["user_id"] = user_id
        if rule_id:
            payload["rule_id"] = rule_id

        resp = _run_larkcli(payload, identity)
        if not resp.get("ok", False):
            raise SystemExit(f"API 返回错误：{json.dumps(resp, ensure_ascii=False, indent=2)}")

        data = resp.get("data") or {}
        new = 0
        for it in data.get("items", []):
            tid = it.get("task_id")
            if tid in seen:
                continue
            seen.add(tid)
            items.append(it)
            new += 1

        next_token = data.get("page_token", "")
        # 无更多 / 无下一页标记 / 本页没有新增（防重复翻页死循环）→ 停止
        if not data.get("has_more") or not next_token or new == 0:
            break
        page_token = next_token
    return items


# ---------- 输出 ----------

def format_zh(items, label):
    """中文格式化汇总，按 commit_time 倒序、按 form 字段分组。"""
    if not items:
        return f"📭 {label}：时间范围内没有日报记录。\n（若确信有数据，请核对时区或扩大范围）"

    items = sorted(items, key=lambda x: x.get("commit_time", 0), reverse=True)
    out = [f"📋 {label} 共 {len(items)} 条日报\n"]
    for it in items:
        ct = it.get("commit_time")
        ct_str = datetime.datetime.fromtimestamp(ct, TZ).strftime("%Y-%m-%d %H:%M") if ct else "?"
        out.append(f"── {it.get('from_user_name', '?')}"
                   f"（{it.get('department_name', '')}）"
                   f" | {it.get('rule_name', '')} | {ct_str} ──")
        for f in it.get("form_contents", []):
            val = (f.get("field_value") or "").strip() or "（空）"
            out.append(f"  【{f.get('field_name', '')}】{val}")
        out.append("")
    return "\n".join(out).rstrip()


def main():
    # Windows 控制台默认 GBK，强制 UTF-8 输出，避免 emoji/生僻字 UnicodeEncodeError
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    p = argparse.ArgumentParser(description="飞书日报查询（lark-report skill 配套）")
    p.add_argument("date", nargs="*",
                   help="today/yesterday/week/month 或 YYYY-MM-DD [YYYY-MM-DD]，缺省=today")
    p.add_argument("--as", dest="identity", default="user", choices=["user", "bot"],
                   help="调用身份，默认 user")
    p.add_argument("--user-id", help="按用户过滤（bot 身份必填）")
    p.add_argument("--rule-id", help="按汇报规则过滤")
    p.add_argument("--json", action="store_true", help="输出聚合后的原始 JSON")
    args = p.parse_args()

    start_ts, end_ts, label = resolve_range(args.date)
    items = query(start_ts, end_ts, identity=args.identity,
                  user_id=args.user_id, rule_id=args.rule_id)

    if args.json:
        print(json.dumps(
            {"label": label, "commit_start_time": start_ts,
             "commit_end_time": end_ts, "count": len(items), "items": items},
            ensure_ascii=False, indent=2))
    else:
        print(format_zh(items, label))


if __name__ == "__main__":
    main()
