# chhsich-thesis-aigc-skills

降低中文学术论文 AIGC 检测率（知网/维普/万方）的实战方法论和工具。

## 核心发现

- **完全段落重写有效，逐词替换无效**
- **预防性写作比事后修复高效得多**

基于实战验证：知网 AIGC 检测率从 **48.9% 降至 11.3%**。

## 安装

### 方式一：npx（推荐）

```bash
npx @chhsiching/chhsich-thesis-aigc-skills
```

自动安装到 Claude Code / AionUI 的 skills 目录，重启会话即可使用。

### 方式二：从 GitHub 手动安装

```bash
# 克隆到 skills 目录
git clone https://github.com/ChHsiching/chhsich-thesis-aigc-skills.git \
  ~/.claude/skills/chhsich-thesis-aigc-skills
```

或者直接将 `SKILL.md` 复制到你的 skills 目录。

## 双模式工作流

### 模式一：预防性写作

写新文本时遵循 8 条规则，从源头避免 AI 特征：

1. 用具体动词，不用抽象动词（"做了"而非"进行了"）
2. 长短句交替，打破均匀节奏
3. 不编号，自然过渡
4. 直接说事，不做铺垫
5. 去连接词，用标点代替
6. 段落长度不均匀
7. 用"而""则"做对比，不用"不仅…而且…"
8. 学术文本中偶尔用短句穿插

详见 [SKILL.md](SKILL.md) 的"预防性写作规则"章节。

### 模式二：事后修复

已有 AI 文本的五步修复流程：

1. **解析检测报告** — 提取"显著"片段
2. **定位目标段落** — 在 docx 中用唯一子串定位
3. **重写段落** — 完全重写（6 条策略）
4. **应用替换** — 用 lxml 操作 OOXML，仅修改文本节点
5. **验证** — 检查文件完整性和实际降幅

## 文件说明

| 文件 | 说明 |
|------|------|
| [SKILL.md](SKILL.md) | 完整工作流（预防性写作规则 + 事后修复流程） |
| [REFERENCE.md](REFERENCE.md) | 技术参考（docx OOXML 操作、CNKI 报告格式） |
| [EXAMPLES.md](EXAMPLES.md) | 改写前后对照示例（6 个示例 + 效果统计） |
| [scripts/docx_rewrite.py](scripts/docx_rewrite.py) | docx 文本替换工具脚本 |

## 不工作的方法

| 方法 | 为什么不行 |
|------|-----------|
| 自动化改写工具 | 插入古文、错误替换、产生新的 AI 特征 |
| 逐词替换 AI 高频词 | 只改词汇不改结构，检测器仍标记 |
| python-docx 库操作 | 会重写整个 XML，丢失复杂格式 |
| 只改"疑似"片段 | "疑似"不计入 AI 率，改了也不降分 |

## 使用要求

- Python 3.8+
- lxml（`pip install lxml`）

## License

MIT
