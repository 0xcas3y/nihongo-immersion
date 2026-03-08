#!/usr/bin/env python3
"""
SRT 字幕翻译补全工具
用法: python3 fix_srt.py 字幕文件.srt --key YOUR_DEEPL_KEY
输出: 字幕文件_fixed.srt
"""

import re
import sys
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path

# ── SRT 解析 ──────────────────────────────────────────────────

def parse_srt(text):
    """解析 SRT，返回 list of dict: {idx, time, lines}"""
    blocks = re.split(r'\n\s*\n', text.strip())
    entries = []
    for block in blocks:
        lines = block.strip().splitlines()
        if len(lines) < 2:
            continue
        # 第一行是序号
        try:
            idx = int(lines[0].strip())
        except ValueError:
            continue
        # 第二行是时间轴
        if '-->' not in lines[1]:
            continue
        time_line = lines[1].strip()
        content = '\n'.join(lines[2:]).strip()
        entries.append({'idx': idx, 'time': time_line, 'content': content})
    return entries

def write_srt(entries):
    """把 entries 写回 SRT 格式"""
    blocks = []
    for e in entries:
        blocks.append(f"{e['idx']}\n{e['time']}\n{e['content']}")
    return '\n\n'.join(blocks) + '\n'

# ── 判断是否缺翻译 ────────────────────────────────────────────

def is_missing(content):
    """判断这条字幕是否缺中文翻译"""
    stripped = content.strip()
    if stripped in ('...', ' ...', '…'):
        return True
    if not stripped:
        return True
    return False

def is_japanese(text):
    """判断文本是否为日文（含假名）"""
    return bool(re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', text))

def has_chinese(text):
    """是否已有中文（有汉字且无假名）"""
    has_kanji = bool(re.search(r'[\u4e00-\u9fff]', text))
    has_kana = bool(re.search(r'[\u3040-\u30ff]', text))
    return has_kanji and not has_kana

# ── DeepL 翻译 ────────────────────────────────────────────────

def translate_batch(texts, key):
    """批量翻译，返回翻译结果列表"""
    is_free = key.endswith(':fx')
    host = 'api-free.deepl.com' if is_free else 'api.deepl.com'
    url = f'https://{host}/v2/translate'
    
    payload = json.dumps({
        'text': texts,
        'source_lang': 'JA',
        'target_lang': 'ZH'
    }).encode()
    
    req = urllib.request.Request(
        url, data=payload,
        headers={
            'Authorization': f'DeepL-Auth-Key {key}',
            'Content-Type': 'application/json'
        },
        method='POST'
    )
    
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    
    return [t['text'] for t in data['translations']]

# ── 主逻辑 ────────────────────────────────────────────────────

def fix_srt(input_path, deepl_key, dry_run=False):
    text = Path(input_path).read_text(encoding='utf-8')
    entries = parse_srt(text)
    
    print(f'✓ 共解析 {len(entries)} 条字幕')
    
    # 找出缺翻译的偶数条目（中文行）
    # 格式：奇数条 = 日文，偶数条 = 对应中文
    # 但 idx 不一定连续，按顺序配对
    
    missing = []  # [(entry_index_in_list, jp_text)]
    
    for i, entry in enumerate(entries):
        # 偶数位置（0-indexed）是中文条目
        if i % 2 == 1:  # 第2、4、6... 条
            if is_missing(entry['content']):
                # 对应的日文是上一条
                jp_entry = entries[i - 1]
                jp_text = jp_entry['content']
                # 去掉音效标记如 [音楽]
                jp_clean = re.sub(r'\[.*?\]', '', jp_text).strip()
                if jp_clean:
                    missing.append((i, jp_clean))
    
    print(f'⚠ 发现 {len(missing)} 条缺失翻译')
    
    if not missing:
        print('✓ 所有翻译都完整，无需修复！')
        return
    
    if dry_run:
        print('\n缺失翻译的句子：')
        for i, (entry_i, jp) in enumerate(missing[:10]):
            print(f'  {i+1}. [{entries[entry_i]["time"]}] {jp[:50]}...' if len(jp) > 50 else f'  {i+1}. [{entries[entry_i]["time"]}] {jp}')
        if len(missing) > 10:
            print(f'  ... 还有 {len(missing)-10} 条')
        print('\n加上 --key YOUR_DEEPL_KEY 参数来执行翻译')
        return
    
    if not deepl_key:
        print('❌ 请提供 DeepL API Key: --key YOUR_KEY')
        sys.exit(1)
    
    # 批量翻译
    BATCH = 50
    translated_map = {}  # entry_index -> zh_text
    
    print(f'\n开始翻译（共 {len(missing)} 句，每批 {BATCH} 句）...')
    
    for batch_start in range(0, len(missing), BATCH):
        batch = missing[batch_start:batch_start + BATCH]
        jp_texts = [jp for _, jp in batch]
        
        try:
            zh_texts = translate_batch(jp_texts, deepl_key)
            for (entry_i, _), zh in zip(batch, zh_texts):
                translated_map[entry_i] = zh
            done = min(batch_start + BATCH, len(missing))
            print(f'  已翻译 {done}/{len(missing)} 句...')
        except urllib.error.HTTPError as e:
            print(f'❌ DeepL API 错误 {e.code}: {e.read().decode()}')
            sys.exit(1)
        except Exception as e:
            print(f'❌ 翻译失败: {e}')
            sys.exit(1)
    
    # 填入翻译
    fixed_count = 0
    for entry_i, zh in translated_map.items():
        entries[entry_i]['content'] = zh
        fixed_count += 1
    
    # 写出文件
    output_path = Path(input_path).stem + '_fixed.srt'
    output_path = Path(input_path).parent / output_path
    output_path.write_text(write_srt(entries), encoding='utf-8')
    
    print(f'\n✅ 完成！已补全 {fixed_count} 条翻译')
    print(f'📄 输出文件：{output_path}')

# ── CLI ───────────────────────────────────────────────────────

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='SRT 字幕翻译补全工具')
    parser.add_argument('input', help='输入的 SRT 文件路径')
    parser.add_argument('--key', default='', help='DeepL API Key')
    parser.add_argument('--dry-run', action='store_true', help='只检查缺失，不翻译')
    args = parser.parse_args()
    
    fix_srt(args.input, args.key, dry_run=args.dry_run)
