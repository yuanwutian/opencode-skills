---
name: lark-attendance-visual
description: "Visualized Lark/Feishu attendance query: formatted summary tables and dark-theme trend charts. Use when the user wants to query and visualize attendance records (打卡记录) — triggers: '打卡', '考勤', 'attendance', '签到记录', '上下班时间', '工作时长', '考勤图表', '考勤报告'. Prefer this over lark-attendance when tables, charts, or reports are wanted. Do NOT use for non-attendance Lark operations like calendar, IM, docs, etc."
---

# Lark/Feishu Attendance Record Query

## Overview

Query personal attendance (打卡) records via `lark-cli attendance user_tasks query`. Supports date range queries, renders results as formatted tables and charts.

## Prerequisites

- User must be logged in: `lark-cli auth login --domain attendance`
- Requires scope: `attendance:task:readonly`

## Workflow

### Step 1: Check auth status

```bash
lark-cli auth status
```

If user identity is missing, log in:

```bash
lark-cli auth login --domain attendance
```

After login, the open_id is shown (e.g., `ou_xxxxx`). Use this as `employee_id`.

### Step 2: Query attendance records

```bash
lark-cli attendance user_tasks query \
  --employee-type employee_id \
  --data '{"check_date_from": <YYYYMMDD>, "check_date_to": <YYYYMMDD>, "user_ids": ["<open_id>"]}' \
  --format json
```

Key parameters:
- `check_date_from` / `check_date_to`: integer, format `yyyyMMdd`
- `user_ids`: array of employee IDs (open_id for `employee_id` type)
- `employee_type`: `employee_id` (open_id) or `employee_no` (工号)

### Step 3: Parse output

The response structure is:
```
.data.user_task_results[]:
  .day              - date (yyyyMMdd)
  .employee_name    - user name
  .records[]:
    .check_in_record.check_time   - unix timestamp
    .check_in_result              - Normal | NoNeedCheck | Early | Late | Lack | Todo
    .check_out_record.check_time  - unix timestamp
    .check_out_result             - Normal | NoNeedCheck | Early | Late | Lack | Todo
    .task_shift_type              - 0=normal, 1=overtime
```

### Step 4: Format as readable table

```bash
lark-cli attendance user_tasks query ... --format json | python3 scripts/attendance_table.py
```

### Step 5: Generate cyber-style chart

安装依赖（首次运行需要）：

```bash
python3 -m venv ~/.opencode/tmp/attendance_venv
~/.opencode/tmp/attendance_venv/bin/pip install matplotlib numpy -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn
```

生成暗色主题考勤趋势图：

```bash
lark-cli attendance user_tasks query ... --format json | ~/.opencode/tmp/attendance_venv/bin/python scripts/attendance_chart.py
```

自定义输出路径：

```bash
lark-cli attendance user_tasks query ... --format json | ~/.opencode/tmp/attendance_venv/bin/python scripts/attendance_chart.py /path/to/output.png
```

## Attendance Result Values

| Result | Meaning |
|--------|---------|
| Normal | 正常打卡 |
| NoNeedCheck | 无需打卡（休息日/无需打卡班次） |
| Early | 早退 |
| Late | 迟到 |
| Lack | 缺卡 |
| Todo | 未打卡 |

Supplement values: `None`(无), `ManagerModification`(管理员修改), `CardReplacement`(补卡通过), `ShiftChange`(换班), `Travel`(出差), `Leave`(请假), `GoOut`(外出), `CardReplacementApplication`(补卡申请中), `FieldPunch`(外勤打卡).
