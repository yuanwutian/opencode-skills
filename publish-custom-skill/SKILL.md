---
name: publish-custom-skill
description: 检索本地自定义 Claude/opencode skill 并推送到 GitHub 云端仓库（yuanwutian/opencode-skills）。当用户要把自定义 skill 提交/推送/同步到 GitHub、把本地 skill 上云、或提到"推送 skill""提交 skill 到云端""同步自定义 skill""skill 提交到 git""skill 上传"时使用——即使没明说 publish 也应主动用。覆盖 gh 认证检查、SSH/HTTPS 重写配置、clone-追加-提交流程、lark-shared 依赖处理、CRLF 行尾判断、commit message 规范。
---

# Publish Custom Skill

把本地自定义 skill 检索出来，整理后推送到 GitHub 仓库 `yuanwutian/opencode-skills`（Public，默认分支 master）。

这套流程的核心难点不在 git 本身，而在三个容易踩的坑：**远程仓库已存在时不能新建 root-commit 仓库**、**本机 github.com:443 被墙需走 SSH**、**Windows CRLF 与仓库 LF 的行尾差异**。下面按顺序处理。

## 何时触发

- 用户要把某个/某些自定义 skill 提交到云端 git 仓库
- "推送 skill""提交 skill 到 github""同步自定义 skill 上云""skill 上传"
- 本地新建/改名了 skill，需要版本管理

## 前置检查

```bash
gh auth status                    # 确认已登录（账号 yuanwutian，SSH 协议）
ssh -T git@github.com             # 确认 SSH key 可连（应回 "Hi yuanwutian!"）
git config --global --get-regexp '^url\.'
```

`url.` 规则应为 `url."git@github.com:".insteadof "https://github.com/"`（HTTPS→SSH）。若发现反向规则 `url.https://github.com/.insteadof git@github.com:`（SSH→HTTPS），会导致所有 SSH URL 被改成 HTTPS、因 443 被墙而失败。修正：

```bash
git config --global --unset url.https://github.com/.insteadof 2>/dev/null
git config --global url."git@github.com:".insteadof "https://github.com/"
```

## 检索本地自定义 skill

本地 skill 可能分布在三处，逐一枚举：

```bash
ls ~/.config/opencode/skills/     # opencode 平台
ls ~/.claude/skills/              # Claude Code 全局
ls <project>/.claude/skills/      # 项目级
```

区分"自定义"与"官方"：自定义 skill 通常无 `homepage` 指向官方仓库、或为用户改名/手写。lark-* 系列多为 lark-cli 官方安装，但用户改名或改过内容的也算自定义（如 lark-attendance-visual）。读 SKILL.md frontmatter 判断身份。

## 工作流

### 1. 确认远程仓库状态（关键，避免误建仓库）

```bash
gh repo view yuanwutian/opencode-skills --json url,visibility,defaultBranchRef
gh api repos/yuanwutian/opencode-skills/commits/master --jq '.[0:3]|.[]|{sha:.sha[0:7],msg:(.commit.message|split("\n")[0])}'
gh api repos/yuanwutian/opencode-skills/contents --jq '.[].name'
```

- **已存在**（常见）：clone 后追加提交。绝不要 `git init` 新仓库——新仓库与远程无共同历史，push 会被拒。
- **不存在**：`gh repo create yuanwutian/opencode-skills --public --source=<local> --push`

### 2. clone 到临时工作副本

临时目录按 CLAUDE.md 规范用 `D:\AIAgent\CCTempStore`（不放用户主目录/工程目录/系统临时目录）：

```bash
git clone git@github.com:yuanwutian/opencode-skills.git D:/AIAgent/CCTempStore/opencode-skills
```

若 clone 报 HTTPS 连接失败，说明 insteadof 规则反了，先按"前置检查"修正后重试。`gh repo clone` 默认走 HTTPS 也会失败，直接用 `git clone git@github.com:` 即可。

### 3. 拷入待提交 skill

```bash
cp -r <skill源目录> D:/AIAgent/CCTempStore/opencode-skills/
find D:/AIAgent/CCTempStore/opencode-skills -type d -name __pycache__ -exec rm -rf {} +
```

### 4. 处理依赖与行尾

**依赖**：lark-* skill 的 SKILL.md 可能写"MUST 先读 `../lark-shared/SKILL.md`"。lark-shared 是 lark 系列公共认证文档。是否一并提交需与用户确认：

- 一并提交：仓库自包含，引用不断链
- 只提交目标 skill：lark-shared 留本地 `~/.claude/skills/lark-shared`，仓库内引用断链但本机使用不受影响（脚本通常只调 lark-cli、不 import lark-shared，属文档级依赖）

**行尾**：Windows 本地 CRLF vs 仓库 LF，`git diff` 会显示"differ"。先判断是否纯行尾差异：

```bash
diff -rq --strip-trailing-cr <repo>/<skill> <skill源目录> && echo "纯行尾差异，无需改动"
```

纯行尾差异说明远程已是最新，不必重新提交该 skill。

### 5. 提交并推送

```bash
git -C D:/AIAgent/CCTempStore/opencode-skills add <skill>/
git -C D:/AIAgent/CCTempStore/opencode-skills commit -F - <<'EOF'
feat(<scope>): <一句话说明>

[需求来源]
<来源>

[变更内容]
- <具体改动>

[测试重点]
- <验证点>

[影响范围]
新增 skill，无破坏性变更

[备注]
源文件来自 <路径>
EOF
git -C D:/AIAgent/CCTempStore/opencode-skills push origin master
```

commit message 严格按 CLAUDE.md 规范：`type(scope): subject` + [需求来源][变更内容][测试重点][影响范围][备注]，**[变更内容] 最低必填**。type: feat/fix/refactor/perf/test/docs/chore/style/ci。

### 6. 验证

```bash
gh api repos/yuanwutian/opencode-skills/contents --jq '.[].name'
gh api repos/yuanwutian/opencode-skills/commits/master --jq '{sha:.sha[0:7],msg:(.commit.message|split("\n")[0])}'
```

## 常见坑

- **误建 root-commit 仓库**：远程已存在时 `git init` 新仓库会与远程无共同历史，push 被拒。先 `gh repo view` 确认，已存在就 clone。
- **HTTPS 被墙**：本机 github.com:443 不通，SSH 22 通。靠 `url."git@github.com:".insteadof "https://github.com/"` 把所有 HTTPS 重写为 SSH。`gh repo clone` 默认走 HTTPS 也会失败，直接 `git clone git@github.com:`。
- **CRLF 误判**：`diff` 报差异时先加 `--strip-trailing-cr`，避免把行尾差异当内容差异重复提交。
- **gh api vs git HTTPS**：`gh api` 走 api.github.com（通常可达），与 github.com:443 是不同端点，gh api 通不代表 git HTTPS 通。
- **临时文件位置**：工作副本放 `D:\AIAgent\CCTempStore`，不放用户主目录/工程目录/系统临时目录。

## 参考环境

- 远程仓库：`yuanwutian/opencode-skills`（Public，默认分支 master）
- gh 账号：yuanwutian（SSH 协议）
- 临时工作副本：`D:\AIAgent\CCTempStore\opencode-skills`
- commit 规范来源：`~/.claude/CLAUDE.md` 的 Git 工作流章节
