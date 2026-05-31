#!/usr/bin/env python3
"""
docx_rewrite.py - 安全替换 docx 文件中的文本，保留所有格式。

用法:
    python docx_rewrite.py 论文.docx replacements.json

replacements.json 格式:
    [
        {
            "search_key": "唯一标识子串",
            "old_text": "要替换的原文",
            "new_text": "改写后的新文本"
        }
    ]

特性:
    - 仅修改 w:t 文本节点，保留所有格式（样式、表格、图片、公式）
    - 处理文本跨多个 w:r 元素的情况
    - 原子写入（tmp + os.replace），防止文件损坏
    - 完成后输出统计信息
"""

import json
import re
import os
import sys
import zipfile

from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'


def replace_in_paragraph(p, old_text, new_text):
    """在段落 XML 元素中替换文本，处理跨 w:r 元素的文本。"""
    runs = list(p.iter(f'{{{W}}}t'))
    full = ''.join(r.text or '' for r in runs)
    if old_text not in full:
        return False

    for run in runs:
        if old_text in (run.text or ''):
            run.text = (run.text or '').replace(old_text, new_text, 1)
            return True

    char_map = []
    for ri, run in enumerate(runs):
        for ci, ch in enumerate(run.text or ''):
            char_map.append((ri, ci))

    idx = full.find(old_text)
    if idx < 0:
        return False

    sr, sc = char_map[idx]
    er, ec = char_map[idx + len(old_text) - 1]

    runs[sr].text = (runs[sr].text or '')[:sc] + new_text
    for i in range(sr + 1, er):
        runs[i].text = ''
    runs[er].text = (runs[er].text or '')[ec + 1:]
    return True


def apply_replacements(docx_path, replacements):
    """对 docx 文件应用一组文本替换。"""
    with zipfile.ZipFile(docx_path, 'r') as zin:
        all_files = {item.filename: zin.read(item.filename)
                     for item in zin.infolist()}

    doc_xml = all_files['word/document.xml']
    doc_tree = etree.fromstring(doc_xml)
    body = doc_tree.find(f'{{{W}}}body')

    applied = 0
    failed = []
    for p in body.iter(f'{{{W}}}p'):
        runs = list(p.iter(f'{{{W}}}t'))
        full = ''.join(r.text or '' for r in runs)
        if not full.strip():
            continue
        for rep in replacements:
            search_key = rep['search_key']
            old_text = rep['old_text']
            new_text = rep['new_text']
            if search_key in full and old_text in full:
                if replace_in_paragraph(p, old_text, new_text):
                    applied += 1
                    print(f'OK: {search_key[:40]}')
                else:
                    failed.append(search_key[:40])
                break

    doc_xml_new = etree.tostring(doc_tree, xml_declaration=True,
                                  encoding='UTF-8', standalone=True)
    doc_xml_new = doc_xml_new.replace(
        b"<?xml version='1.0' encoding='UTF-8' standalone='yes'?>",
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>')

    # Restore original root element attribute ordering (lxml reorders them)
    orig_root_tag = re.search(rb'<w:document[^>]*>', all_files['word/document.xml'])
    new_root_tag = re.search(rb'<w:document[^>]*>', doc_xml_new)
    if orig_root_tag and new_root_tag and orig_root_tag.group() != new_root_tag.group():
        doc_xml_new = doc_xml_new.replace(new_root_tag.group(), orig_root_tag.group(), 1)

    tmp = docx_path + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for fn, data in all_files.items():
            zout.writestr(fn, doc_xml_new if fn == 'word/document.xml' else data)
    os.replace(tmp, docx_path)

    print(f'\nApplied: {applied}/{len(replacements)}')
    if failed:
        print(f'Failed: {failed}')
    return applied, failed


def verify_integrity(docx_path):
    """验证 docx 文件完整性。"""
    fsize = os.path.getsize(docx_path)
    with zipfile.ZipFile(docx_path, 'r') as z:
        doc_xml = z.read('word/document.xml')
    tree = etree.fromstring(doc_xml)
    body = tree.find(f'{{{W}}}body')

    total_chars = 0
    issues = []
    for p in body.iter(f'{{{W}}}p'):
        runs = list(p.iter(f'{{{W}}}t'))
        text = ''.join(r.text or '' for r in runs)
        total_chars += len(text)
        if len(text) > 0 and text == text[0] * len(text) and len(text) > 10:
            issues.append(f'Repeated chars: {text[:30]}...')

    print(f'File: {fsize} bytes, {total_chars} chars')
    if issues:
        for i in issues:
            print(f'ISSUE: {i}')
    else:
        print('Integrity: OK')
    return len(issues) == 0


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    docx_path = sys.argv[1]
    replacements_path = sys.argv[2]

    with open(replacements_path, 'r', encoding='utf-8') as f:
        replacements = json.load(f)

    print(f'Loading {len(replacements)} replacements for {docx_path}')
    applied, failed = apply_replacements(docx_path, replacements)

    print('\nVerifying...')
    verify_integrity(docx_path)
