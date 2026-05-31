# 技术参考：AIGC 降重

## 一、CNKI AIGC 检测报告格式

### 全文报告结构

```
AIGC检测 · 全文报告单
NO: CNKIAIGC2026FG_xxxx
检测时间：yyyy-MM-dd HH:mm:ss
篇名：论文标题
作者：作者名

全文检测结果
AI特征值：XX.X%
AI特征字符数：XXXX
总字符数：XXXXX

分段检测结果（按章节）
序号 | AI特征值 | AI特征字符数/章节字符数 | 章节名称

片段指标列表（每章节下）
序号 | 片段名称 | 字符数 | AI特征（显著/疑似）

原文内容（标记文本，红=显著，棕=疑似）
```

### 关键规则

- **"AI特征显著"**（红色）→ 计入 AI 特征字符数 → 计入 AIGC 率
- **"AI特征疑似"**（棕色）→ 不计入 → 改写性价比低
- AI特征值 = AI特征字符数 / 总字符数
- 章节级别 AI 率 = 该章节 AI 字符数 / 该章节总字符数

### 从 PDF 提取文本

```bash
# 方法1：pdftotext
pdftotext report.pdf report.txt

# 方法2：如果 PDF 无法提取（扫描件等），手动复制报告内容到文本文件
```

提取后需要清理：去除页码、URL片段、CNKI 水印文字（"知网个人AIGC检测服务"）。

## 二、docx OOXML 操作

### 为什么用 lxml 而不是 python-docx

python-docx 在保存时会重写整个 XML，丢失：
- 复杂的段落样式链（论文1→论文2→论文3）
- 表格格式
- 图片引用
- 域代码（交叉引用、目录）
- OMML 数学公式

lxml 只修改 w:t 文本节点，保留所有其他 XML 结构。

### 核心替换函数

```python
import zipfile, os
from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

def replace_in_paragraph(p, old_text, new_text):
    """在段落 XML 元素中替换文本。
    处理文本分布在多个 w:r/w:t 元素中的情况。"""
    runs = list(p.iter(f'{{{W}}}t'))
    full = ''.join(r.text or '' for r in runs)
    if old_text not in full:
        return False

    # 情况1：old_text 在单个 w:t 元素中
    for run in runs:
        if old_text in (run.text or ''):
            run.text = (run.text or '').replace(old_text, new_text, 1)
            return True

    # 情况2：old_text 跨多个 w:r 元素
    char_map = []
    for ri, run in enumerate(runs):
        for ci, ch in enumerate(run.text or ''):
            char_map.append((ri, ci))

    idx = full.find(old_text)
    if idx < 0:
        return False

    sr, sc = char_map[idx]
    er, ec = char_map[idx + len(old_text) - 1]

    # 在起始 run 中写入新文本（截断到起始位置 + 新文本）
    runs[sr].text = (runs[sr].text or '')[:sc] + new_text

    # 清空中间 run
    for i in range(sr + 1, er):
        runs[i].text = ''

    # 截断结束 run
    runs[er].text = (runs[er].text or '')[ec + 1:]
    return True
```

### 安全的读写模式

```python
src = '论文.docx'

# 1. 读所有文件到内存
with zipfile.ZipFile(src, 'r') as zin:
    all_files = {item.filename: zin.read(item.filename)
                 for item in zin.infolist()}

# 2. 解析并修改 document.xml
doc_xml = all_files['word/document.xml']
doc_tree = etree.fromstring(doc_xml)
body = doc_tree.find(f'{{{W}}}body')

# ... 执行替换 ...

# 3. 序列化并修复 lxml 引入的兼容性问题
doc_xml_new = etree.tostring(doc_tree, xml_declaration=True,
                              encoding='UTF-8', standalone=True)

# 【修复1】lxml.tostring 生成单引号声明 (version='1.0')，
# Microsoft Word (尤其是 macOS 版) 要求双引号 (version="1.0")。
doc_xml_new = doc_xml_new.replace(
    b"<?xml version='1.0' encoding='UTF-8' standalone='yes'?>",
    b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')

# 【修复2】lxml 重排根元素属性顺序（xmlns:* 放前面，mc:Ignorable 被推后），
# 但原始 Word 文件中 mc:Ignorable 在最前面。macOS Word 对此敏感。
# 保存原始根标签后，在序列化结果中恢复原始顺序：
import re
orig_root_tag = re.search(rb'<w:document[^>]*>', orig_doc_xml).group()
new_root_tag = re.search(rb'<w:document[^>]*>', doc_xml_new).group()
if orig_root_tag != new_root_tag:
    doc_xml_new = doc_xml_new.replace(new_root_tag, orig_root_tag, 1)

tmp = src + '.tmp'
with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
    for fn, data in all_files.items():
        zout.writestr(fn, doc_xml_new if fn == 'word/document.xml' else data)
os.replace(tmp, src)
```

**关键点**：
- 必须用 `os.replace`（原子操作），不能直接写同名文件
- 不能边读边写同一个 zipfile（会得到 22 字节的损坏文件）
- `all_files` 保留所有非 document.xml 文件不变
- **lxml 引号陷阱**：`etree.tostring` 输出 `version='1.0'`（单引号），macOS Word 只接受 `version="1.0"`（双引号）。保存前必须替换。

### 遍历段落执行替换

```python
replacements = [
    # (search_key, old_text, new_text)
    ('唯一标识子串', '要替换的原文', '改写后的新文本'),
]

applied = 0
for p in body.iter(f'{{{W}}}p'):
    runs = list(p.iter(f'{{{W}}}t'))
    full = ''.join(r.text or '' for r in runs)
    if not full.strip():
        continue
    for search_key, old_text, new_text in replacements:
        if search_key in full and old_text in full:
            if replace_in_paragraph(p, old_text, new_text):
                applied += 1
                break  # 每段只替换第一个匹配
```

## 三、替换元组设计原则

### search_key 选择

- 选择段落中 10-20 字的唯一子串
- 避免选择可能在前次改写中被修改的部分
- 优先选技术术语密集的片段（更稳定）

### old_text 选择

- 必须是 docx 中的实际文本（不是报告中引用的文本）
- 如果前次改写已修改，需要先读取当前文本再构造 old_text
- 可以是段落的一部分（不必整段替换）

### new_text 设计

- 长度通常比 old_text 短 20-40%（更紧凑 = 更少 AI 特征）
- 保留所有 `[数字]` 引用标记
- 保留所有技术术语、参数名（d_model、n_heads 等）
- 不使用 →（U+2192）等特殊字符（Python 语法冲突）
- 不使用中文引号 """"（与 Python 字符串定界符冲突，用直引号或不用）

## 四、验证检查

### 文件完整性

```python
import os
fsize = os.path.getsize(src)
# 正常范围：原文件大小的 90%-110%

# 检查文本重复
for p in body.iter(f'{{{W}}}p'):
    text = ''.join(r.text or '' for r in p.iter(f'{{{W}}}t'))
    # 检查是否有意外的文本重复
```

### 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| 22 字节文件 | 边读边写同一文件 | 用 tmp + os.replace |
| 文本重复 | replace 逻辑错误 | 检查 replace_in_paragraph 的截断逻辑 |
| 格式丢失 | 用 python-docx 保存 | 改用 lxml + zipfile |
| old_text 不匹配 | 前次改写已修改文本 | 先读取当前文本 |
| Python 语法错误 | 中文引号/箭头字符 | 只用 ASCII 引号 |
