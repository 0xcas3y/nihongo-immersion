#!/usr/bin/env python3
"""
日語沉浸学習器 - 本地服务器
运行方式: python3 server.py
然后在浏览器打开: http://localhost:8765
"""

import http.server
import json
import urllib.request
import urllib.error
import os
import sys
import mimetypes
from pathlib import Path
import urllib.parse

PORT = 8765
HTML_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nihongo.html")
VIDEO_DIR = os.path.expanduser("~/Downloads/日本語youtube")
SUBTITLE_DIR = os.path.expanduser("~/Downloads/日本語youtube/字幕")

# ── JMdict 本地词库 ──────────────────────────────────────────────
import json as _json
JMDICT_PATH = os.path.expanduser("~/Desktop/jmdict_zh.json")
jmdict = {}
if os.path.exists(JMDICT_PATH):
    try:
        with open(JMDICT_PATH, encoding="utf-8") as f:
            jmdict = _json.load(f)
        print(f"✓ JMdict 已加载，共 {len(jmdict)} 条")
    except Exception as e:
        print(f"✗ JMdict 加载失败: {e}")
else:
    print("⚠ JMdict 未找到，将使用 Jisho 英文词典")

# ── MeCab 词性分析 ─────────────────────────────────────────────
POS_MAP = {
    '名詞': 'noun', '動詞': 'verb', '助詞': 'part',
    '形容詞': 'adj', '副詞': 'adv', '助動詞': 'aux',
    '接続詞': 'other', '感動詞': 'other', '記号': 'other', '接頭詞': 'other',
}
POS_ZH = {
    'noun': '名词', 'verb': '动词', 'part': '助词',
    'adj': '形容词', 'adv': '副词', 'aux': '助动词', 'other': '其他'
}

try:
    import fugashi
    _tagger = fugashi.Tagger()
    MECAB_OK = True
    print("✓ MeCab 词性分析已就绪")
except Exception as e:
    MECAB_OK = False
    print(f"⚠ MeCab 未就绪: {e}")

def analyze_text(text):
    if not MECAB_OK:
        return [{'t': text, 'f': '', 'r': '', 'p': 'other', 'm': 'MeCab未安装'}]
    words = _tagger(text)
    result = []
    for w in words:
        surface = w.surface
        if not surface.strip():
            continue
        f = w.feature
        # UniDic format: named attributes
        try:
            pos_jp = f.pos1 if f.pos1 != '*' else '名詞'
            reading = f.pron if f.pron != '*' else (f.kana if f.kana != '*' else '')
            lemma = f.lemma if f.lemma != '*' else surface
        except AttributeError:
            # Fallback: ipadic comma-separated format
            parts = str(f).split(',')
            pos_jp = parts[0] if parts else '名詞'
            reading = parts[7] if len(parts) > 7 and parts[7] != '*' else ''
            lemma = parts[6] if len(parts) > 6 and parts[6] != '*' else surface
        pos = POS_MAP.get(pos_jp, 'other')
        meaning = POS_ZH[pos]
        if lemma and lemma != surface:
            meaning += f'・{lemma}'
        result.append({'t': surface, 'f': reading, 'r': '', 'p': pos, 'm': meaning})
    return result

# ── HTTP Handler ───────────────────────────────────────────────
class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass

    def send_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors()
        self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            try:
                with open(HTML_FILE, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_cors()
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"nihongo.html not found")
        elif self.path.startswith("/dict"):
            from urllib.parse import parse_qs, unquote_plus
            params = parse_qs(self.path.split("?",1)[1] if "?" in self.path else "")
            word = unquote_plus(params.get("word", [""])[0])
            if word and jmdict:
                entry = jmdict.get(word)
                if entry:
                    result = json.dumps({"found": True, "reading": entry.get("r",""), "meaning": entry.get("m","")}, ensure_ascii=False).encode()
                else:
                    result = json.dumps({"found": False}).encode()
            else:
                result = json.dumps({"found": False, "error": "JMdict未加载"}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(result)
            return

        elif self.path.startswith("/proxy/jisho"):
            # Jisho API proxy
            from urllib.parse import urlparse, parse_qs, quote
            word = parse_qs(urlparse(self.path).query).get('word', [''])[0]
            try:
                url = f"https://jisho.org/api/v1/search/words?keyword={quote(word)}"
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    raw = json.loads(resp.read())
                meaning = '—'
                reading = ''
                if raw.get('data'):
                    entry = raw['data'][0]
                    # Get reading
                    if entry.get('japanese'):
                        reading = entry['japanese'][0].get('reading', '')
                    # Get Chinese-friendly meaning (English as fallback)
                    senses = entry.get('senses', [])
                    if senses:
                        defs = senses[0].get('english_definitions', [])
                        meaning = '、'.join(defs[:3])
                result = json.dumps({'meaning': meaning, 'reading': reading}, ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_cors()
                self.end_headers()
                self.wfile.write(result)
            except Exception as e:
                self.send_response(500)
                self.send_cors()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        elif self.path == "/videos":
            # List video files
            try:
                exts = {'.mp4', '.mov', '.webm', '.mkv', '.m4v'}
                files = []
                for f in sorted(Path(VIDEO_DIR).iterdir()):
                    if f.suffix.lower() in exts:
                        size_mb = round(f.stat().st_size / 1024 / 1024, 1)
                        files.append({"name": f.name, "size": size_mb})
                result = json.dumps(files, ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_cors()
                self.end_headers()
                self.wfile.write(result)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

        elif self.path == "/subtitles":
            # List SRT files
            try:
                exts = {'.srt', '.vtt', '.txt'}
                files = []
                for f in sorted(Path(SUBTITLE_DIR).iterdir()):
                    if f.suffix.lower() in exts:
                        files.append({"name": f.name})
                result = json.dumps(files, ensure_ascii=False).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_cors()
                self.end_headers()
                self.wfile.write(result)
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

        elif self.path.startswith("/subtitle/"):
            # Serve SRT file as text
            filename = urllib.parse.unquote(self.path[10:])
            filepath = os.path.join(SUBTITLE_DIR, filename)
            if not os.path.exists(filepath) or not os.path.abspath(filepath).startswith(os.path.abspath(SUBTITLE_DIR)):
                self.send_response(404)
                self.end_headers()
                return
            try:
                with open(filepath, 'rb') as f:
                    content_bytes = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_cors()
                self.end_headers()
                self.wfile.write(content_bytes)
            except Exception as e:
                self.send_response(500)
                self.end_headers()

        elif self.path.startswith("/video/"):
            # Serve video file with range support
            filename = urllib.parse.unquote(self.path[7:])
            filepath = os.path.join(VIDEO_DIR, filename)
            if not os.path.exists(filepath) or not os.path.abspath(filepath).startswith(os.path.abspath(VIDEO_DIR)):
                self.send_response(404)
                self.end_headers()
                return
            try:
                file_size = os.path.getsize(filepath)
                mime = mimetypes.guess_type(filepath)[0] or 'video/mp4'
                range_header = self.headers.get('Range')
                if range_header:
                    # Handle range request for video seeking
                    range_val = range_header.replace('bytes=', '')
                    start_str, end_str = range_val.split('-')
                    start = int(start_str) if start_str else 0
                    end = int(end_str) if end_str else file_size - 1
                    end = min(end, file_size - 1)
                    length = end - start + 1
                    self.send_response(206)
                    self.send_header("Content-Type", mime)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                    self.send_header("Content-Length", str(length))
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_cors()
                    self.end_headers()
                    with open(filepath, 'rb') as f:
                        f.seek(start)
                        remaining = length
                        while remaining:
                            chunk = f.read(min(65536, remaining))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                else:
                    self.send_response(200)
                    self.send_header("Content-Type", mime)
                    self.send_header("Content-Length", str(file_size))
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_cors()
                    self.end_headers()
                    with open(filepath, 'rb') as f:
                        while True:
                            chunk = f.read(65536)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
            except Exception as e:
                print(f"Video serve error: {e}")
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)

        # ── MeCab 分析 ────────────────────────────────────────
        if self.path == "/analyze":
            try:
                data = json.loads(body)
                sentences = data.get("sentences", [])
                results = []
                for s in sentences:
                    words = analyze_text(s.get("text", ""))
                    results.append({"words": words})
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_cors()
                self.end_headers()
                self.wfile.write(json.dumps(results, ensure_ascii=False).encode())
            except Exception as e:
                self.send_response(500)
                self.send_cors()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

        # ── DeepL proxy ───────────────────────────────────────
        elif self.path.startswith("/proxy/deepl"):
            deepl_path = self.path.replace("/proxy/deepl", "")
            auth = self.headers.get("Authorization", "")
            key = auth.replace("DeepL-Auth-Key ", "").replace("Bearer ", "").strip()
            is_free = key.endswith(":fx")
            host = "api-free.deepl.com" if is_free else "api.deepl.com"
            url = f"https://{host}{deepl_path}"
            try:
                req = urllib.request.Request(
                    url, data=body,
                    headers={"Authorization": f"DeepL-Auth-Key {key}", "Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req) as resp:
                    result = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_cors()
                self.end_headers()
                self.wfile.write(result)
            except urllib.error.HTTPError as e:
                err_body = e.read()
                self.send_response(e.code)
                self.send_header("Content-Type", "application/json")
                self.send_cors()
                self.end_headers()
                self.wfile.write(err_body)
            except Exception as e:
                self.send_response(500)
                self.send_cors()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())

        # ── Anthropic proxy ───────────────────────────────────
        elif self.path.startswith("/proxy/anthropic"):
            anthropic_path = self.path.replace("/proxy/anthropic", "")
            auth = self.headers.get("Authorization", "")
            key = auth.replace("Bearer ", "").strip()
            url = f"https://api.anthropic.com{anthropic_path}"
            try:
                req = urllib.request.Request(
                    url, data=body,
                    headers={"x-api-key": key, "Content-Type": "application/json", "anthropic-version": "2023-06-01"},
                    method="POST"
                )
                with urllib.request.urlopen(req) as resp:
                    result = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_cors()
                self.end_headers()
                self.wfile.write(result)
            except urllib.error.HTTPError as e:
                self.send_response(e.code)
                self.send_header("Content-Type", "application/json")
                self.send_cors()
                self.end_headers()
                self.wfile.write(e.read())
            except Exception as e:
                self.send_response(500)
                self.send_cors()
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()


if __name__ == "__main__":
    if not os.path.exists(HTML_FILE):
        print(f"❌ 找不到 nihongo.html，请确保 server.py 和 nihongo.html 在同一文件夹")
        sys.exit(1)

    print(f"""
╔══════════════════════════════════════╗
║       日語沉浸学習器 已启动          ║
╠══════════════════════════════════════╣
║  打开浏览器访问:                     ║
║  → http://localhost:{PORT}           ║
║                                      ║
║  关闭服务器: 按 Ctrl+C              ║
╚══════════════════════════════════════╝
""")
    try:
        server = http.server.HTTPServer(("0.0.0.0", PORT), Handler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n✓ 服务器已关闭")
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"❌ 端口 {PORT} 已被占用")
        else:
            raise
