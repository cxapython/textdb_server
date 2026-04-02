#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TextDB - 简单的在线文本数据库
类似 textdb.online，支持通过 HTTP 存储和获取文本
"""

import os
import hashlib
import json
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
import cgi

DATA_DIR = "/root/textdb/data"
os.makedirs(DATA_DIR, exist_ok=True)

class TextDBHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # 静默日志，减少输出
        pass
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.strip('/')
        
        # 首页
        if path == '' or path == '/':
            self.send_html(self.get_home_page())
            return
        
        # API: 获取文本
        if path.startswith('api/'):
            key = path[4:]  # 去掉 api/ 前缀
            self.handle_get(key)
            return
        
        # 直接通过 key 获取
        self.handle_get(path)
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.strip('/')
        
        content_type = self.headers.get('Content-Type', '')
        
        if 'application/json' in content_type:
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode('utf-8')
            try:
                data = json.loads(body)
                key = data.get('key', '').strip()
                content = data.get('content', '')
            except:
                self.send_error(400, "Invalid JSON")
                return
        else:
            # 表单数据
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode('utf-8')
            params = parse_qs(body)
            key = params.get('key', [''])[0].strip()
            content = params.get('content', [''])[0]
        
        if not key:
            key = self.generate_key(content)
        
        self.save_text(key, content)
        self.send_json({"success": True, "key": key, "url": f"http://{self.headers.get('Host', 'localhost')}/{key}"})
    
    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path.strip('/')
        key = path.replace('api/', '') if path.startswith('api/') else path
        
        length = int(self.headers.get('Content-Length', 0))
        content = self.rfile.read(length).decode('utf-8')
        
        if not key:
            key = self.generate_key(content)
        
        self.save_text(key, content)
        self.send_text(key)
    
    def handle_get(self, key):
        filepath = os.path.join(DATA_DIR, f"{key}.txt")
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            self.send_text(content)
        else:
            self.send_error(404, "Not Found")
    
    def save_text(self, key, content):
        filepath = os.path.join(DATA_DIR, f"{key}.txt")
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        # 保存元数据
        meta_path = os.path.join(DATA_DIR, f"{key}.json")
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump({
                "key": key,
                "size": len(content),
                "created": datetime.now().isoformat()
            }, f)
    
    def generate_key(self, content):
        """生成短 key"""
        return hashlib.md5(content.encode()).hexdigest()[:8]
    
    def send_text(self, content):
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def send_html(self, html):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
    
    def get_home_page(self):
        count = len([f for f in os.listdir(DATA_DIR) if f.endswith('.txt')])
        return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>TextDB - 在线文本数据库</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; line-height: 1.6; }}
        h1 {{ color: #333; }}
        textarea {{ width: 100%; height: 300px; padding: 10px; font-family: monospace; font-size: 14px; border: 1px solid #ddd; border-radius: 4px; }}
        input[type="text"] {{ width: 200px; padding: 8px; font-size: 14px; border: 1px solid #ddd; border-radius: 4px; }}
        button {{ padding: 10px 20px; font-size: 14px; background: #0066cc; color: white; border: none; border-radius: 4px; cursor: pointer; }}
        button:hover {{ background: #0052a3; }}
        .result {{ margin-top: 20px; padding: 15px; background: #f5f5f5; border-radius: 4px; word-break: break-all; }}
        .api {{ background: #f9f9f9; padding: 15px; border-radius: 4px; margin-top: 20px; }}
        code {{ background: #e8e8e8; padding: 2px 6px; border-radius: 3px; font-family: monospace; }}
    </style>
</head>
<body>
    <h1>📝 TextDB - 在线文本数据库</h1>
    <p>已存储 {count} 条文本 | 类似 <a href="https://textdb.online">textdb.online</a></p>
    
    <h3>保存文本</h3>
    <textarea id="content" placeholder="在此输入文本内容..."></textarea>
    <p>
        自定义Key（可选）: <input type="text" id="key" placeholder="留空自动生成">
        <button onclick="saveText()">保存</button>
    </p>
    <div id="result" class="result" style="display:none;"></div>
    
    <div class="api">
        <h3>📡 API 使用</h3>
        <p><b>保存文本（PUT）:</b></p>
        <code>curl -X PUT -d "你的文本内容" http://{self.headers.get('Host', 'your-server')}/your-key</code>
        
        <p><b>保存文本（POST）:</b></p>
        <code>curl -X POST -H "Content-Type: application/json" -d '{{"key":"test","content":"hello"}}' http://{self.headers.get('Host', 'your-server')}/</code>
        
        <p><b>获取文本:</b></p>
        <code>curl http://{self.headers.get('Host', 'your-server')}/your-key</code>
        
        <p><b>浏览器直接访问:</b></p>
        <code>http://{self.headers.get('Host', 'your-server')}/your-key</code>
    </div>
    
    <script>
        function saveText() {{
            const content = document.getElementById('content').value;
            const key = document.getElementById('key').value;
            if (!content) {{ alert('请输入内容'); return; }}
            
            fetch('/', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{key: key, content: content}})
            }})
            .then(r => r.json())
            .then(data => {{
                const result = document.getElementById('result');
                result.style.display = 'block';
                result.innerHTML = '<b>保存成功!</b><br>Key: ' + data.key + '<br>URL: <a href="' + data.url + '">' + data.url + '</a>';
            }});
        }}
    </script>
</body>
</html>'''

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 80))
    server = HTTPServer(('0.0.0.0', port), TextDBHandler)
    print(f"TextDB 服务启动: http://0.0.0.0:{port}")
    server.serve_forever()