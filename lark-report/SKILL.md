---
name: lark-report
version: 1.3.0
description: "飞书汇报模块日报查询：读取当前用户发起及收到的工作日报/周报等汇报任务，含今日总结、明日计划等表单内容。配套 report_query.py 脚本，传日期范围即可查询。当用户需要查看、汇总飞书日报/汇报记录时使用。"
metadata:
  requires:
    bins: ["lark-cli", "python"]
---

# 飞书汇报（日报）查询

> **前置条件：** 开始前 MUST 先用 Read 工具读取 [`../lark-shared/SKILL.md`](../lark-shared/SKILL.md)，其中包含认证、权限、错误处理。

`report` 模块未被 lark-cli 内置 service/shortcut 封装，需裸调 `POST /open-apis/report/v1/tasks/query`。本 skill 已把该请求封装为 **`scripts/report_query.py`**（自动处理日期换算、翻页去重、中文格式化），**首选直接调脚本**，无需手写 bash + 时间戳。

## 首选：scripts/report_query.py（推荐）

脚本位于本 skill 的 `scripts/` 目录，**从 skill 根目录用相对路径调用**。它内部用 `subprocess` 调 `lark-cli api`（复用其鉴权），自己负责日期→UTC+8 时间戳、自动翻页、按 `task_id` 去重、中文汇总。

```bash
# 在 skill 根目录下执行；传日期描述即可，缺省=今天
python scripts/report_query.py                       # 今天
python scripts/report_query.py today                 # 今天
python scripts/report_query.py yesterday             # 昨天
python scripts/report_query.py week                  # 本周（周一~今天）
python scripts/report_query.py month                 # 本月 1 号~今天
python scripts/report_query.py 2026-06-01            # 指定单日
python scripts/report_query.py 2026-06-01 2026-06-29 # 指定区间（含结束当天）

# 选项
python scripts/report_query.py today --json                      # 输出聚合后原始 JSON（含 count/items）
python scripts/report_query.py week --as bot --user-id ou_xxx    # 应用身份查指定用户
python scripts/report_query.py month --rule-id 7627447202571619521  # 按汇报规则过滤
```

> 不在 skill 根目录时，用绝对路径调用（脚本自身可在任意 cwd 运行）：
> ```bash
> python "C:/Users/Windows/.claude/skills/lark-report/scripts/report_query.py" today
> ```

### 调用 sample（AI 使用脚本的标准姿势）

1. **查询 + 直接汇总给用户**（默认中文格式化输出，拿到即可转述）：
   ```bash
   python scripts/report_query.py today
   ```
2. **程序化二次处理**（需要逐条字段时，取 JSON 再解析）：
   ```bash
   python scripts/report_query.py 2026-06-22 2026-06-26 --json
   ```
   返回结构：
   ```json
   {
     "label": "2026-06-22 ~ 2026-06-26",
     "commit_start_time": 1782403200,
     "commit_end_time": 1782835200,
     "count": 5,
     "items": [ { "from_user_name": "...", "commit_time": 1782297931,
                  "form_contents": [ {"field_name": "今日总结", "field_value": "..."} ] } ]
   }
   ```
   解析要点：遍历 `items[]`，每条按 `form_contents[].field_name` / `field_value` 取「今日总结/明日计划/需要协调与帮助」。

- **默认输出**：中文格式化文本，按 `commit_time` 倒序、按表单字段分组。
- **`--json`**：输出 `{label, commit_start_time, commit_end_time, count, items}`，便于程序二次处理。
- 脚本已强制 UTF-8 输出（规避 Windows GBK 控制台的 emoji 报错），并按 `task_id` 去重（见下方「翻页去重坑」）。
- 退出码：`0` 成功（含「无数据」）；非 0 表示调用 / 解析失败，`stderr` 含原因。

## 底层 API（裸调，供脚本维护 / 调试参考）

```bash
# Windows Git Bash 必须加 MSYS_NO_PATHCONV=1，否则 /open-apis 路径会被转换
MSYS_NO_PATHCONV=1 lark-cli api POST /open-apis/report/v1/tasks/query \
  --as user \
  --data '{
    "commit_start_time": 1767196800,
    "commit_end_time": 1782316800,
    "page_token": "",
    "page_size": 20
  }' \
  --json
```

### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `commit_start_time` | int | ✅ | 提交开始时间（Unix 秒，UTC+8 计算） |
| `commit_end_time` | int | ✅ | 提交结束时间（Unix 秒，UTC+8 计算） |
| `page_token` | string | ✅ | 分页标记，首次传 `""` |
| `page_size` | int | ✅ | 每页条数，0~20 |
| `rule_id` | string | 否 | 按汇报规则过滤 |
| `user_id` | string | 否 | 按用户过滤（bot 身份必填） |

### 身份差异

| 身份 | 行为 |
|------|------|
| `--as user` | 获取**当前用户**发起及收到的汇报（推荐）。⚠️ 实测**也会分页**：返回 `has_more: true` + `page_token` 时必须继续翻页，不要假设一次取全 |
| `--as bot` | 需指定 `user_id`，结果分页（依赖 `page_token` 翻页） |

> ⚠️ 历史文档曾称 user 身份「不分页」，实测有误：当时间窗内记录较多时，user 身份同样返回 `has_more: true`，需用 `page_token` 翻完。**两种身份都按下方「响应处理」的翻页逻辑处理。**

## 时间戳计算（北京时间 UTC+8）

时间戳必须按 UTC+8 计算。不要向用户询问时间戳，根据其自然语言（如"今天""昨天""本周""6月"）自行换算：

```python
import datetime
tz = datetime.timezone(datetime.timedelta(hours=8))

# 固定窗口示例
start = int(datetime.datetime(2026, 1, 1, tzinfo=tz).timestamp())   # 1767196800
end   = int(datetime.datetime(2026, 6, 25, tzinfo=tz).timestamp())

# 自然语言 → 时间戳（推荐：基于"上下文今日日期"构造，避免依赖运行环境时区）
# "今天"：今天 00:00 ~ 明天 00:00
today = datetime.datetime(2026, 6, 29, tzinfo=tz)
start = int(today.timestamp())
end   = int((today + datetime.timedelta(days=1)).timestamp())
# "昨天"：start/end 各减一天
# "本周"：start = 本周一 00:00，end = 下周一 00:00
```

> 时间窗用「左闭右开」：`end` 取目标日**次日** 00:00，确保覆盖当天最晚提交（如 18:43 提交的日报）。

## 响应处理

成功返回 `data.items[]`，每条含 `rule_name`、`from_user_name`、`commit_time`、`form_contents[]`（字段如「今日总结」「明日计划」「需要协调与帮助」，按 `field_name` + `field_value` 提取）。向用户汇总时按 `commit_time`（UTC+8）倒序、按 `field_name` 分组呈现。

> **输出语言：本 skill 一律用中文向用户汇总与回复**（字段名、表头、说明文字均用中文），不论用户上一句用什么语言提问。

- 返回 `"data": {}`（空对象）= 时间范围内无数据，**非权限问题**。提示用户扩大时间范围或核对时区。
- `has_more: true`（**user / bot 任一身份都可能出现**）时，用返回的 `page_token` 作为下次请求的 `page_token` 继续翻页，直到 `has_more: false` 为止，再汇总。切勿只取首页就当作全部。

### ⚠️ 翻页去重坑（裸调时务必注意，脚本已处理）

实测 **user 身份的 `page_token` 实为上一条记录的 `task_id`**，带它翻页会把**同一条记录再返回一遍**（首页 1 条 + 第二页同一条 → 误判成 2 条）。因此裸调翻页时必须：

1. 按 `task_id` 去重；
2. 当某页**没有新增** `task_id` 时主动停止，防止重复翻页 / 死循环。

`report_query.py` 已内置去重与停止逻辑，直接用脚本即可避开此坑。

## 权限

| 操作 | 所需 scope |
|------|-----------|
| 查询汇报任务 | `report:task:readonly` |

频率限制 10 次/秒。缺权限/未登录时按 `lark-shared` 指引执行 `lark-cli auth login`。
