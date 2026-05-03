#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, hashlib, secrets, sqlite3, io, base64, re
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string, send_file, abort
import qrcode
from qrcode.image.pil import PilImage

app = Flask(__name__)
DATA_DIR = "/root/textdb/data"
UPLOAD_DIR = "/root/textdb/uploads"
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "textdb.db")

def cleanup_expired_items():
    """清理所有过期的记录和文件，启动时和访问时调用"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now().isoformat()
    c.execute("SELECT id, key, file_path FROM items WHERE expires_at IS NOT NULL AND expires_at < ?", (now,))
    expired = c.fetchall()
    for item_id, key, file_path in expired:
        # 删除物理文件
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        # 删除数据库记录
        c.execute("DELETE FROM items WHERE id=?", (item_id,))
    conn.commit()
    conn.close()
    return len(expired)

def delete_item_by_key(key):
    """根据 key 删除一条记录及其文件"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT file_path FROM items WHERE key=?", (key,))
    row = c.fetchone()
    if row:
        file_path = row[0]
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass
        c.execute("DELETE FROM items WHERE key=?", (key,))
        conn.commit()
    conn.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        key TEXT UNIQUE NOT NULL, type TEXT DEFAULT 'text',
        content TEXT, filename TEXT, file_path TEXT,
        password_hash TEXT, expires_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        access_count INTEGER DEFAULT 0
    )''')
    conn.commit()
    conn.close()
    # 启动时清理过期记录
    cleanup_expired_items()


def generate_key():
    return secrets.token_urlsafe(8)


def generate_qr_code(url):
    """生成二维码，返回 base64 图片数据"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # 转换为 base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    img_str = base64.b64encode(buffer.read()).decode()
    
    return f"data:image/png;base64,{img_str}"

def hash_password(password):
    if not password:
        return None
    return hashlib.sha256(password.encode()).hexdigest()[:16]

def detect_code_lang(text):
    """根据内容自动检测代码语言，优先检测编程语言，最后检测Markdown（避免误匹配）"""
    if not text or not text.strip():
        return 'plaintext'
    sample = text[:3000]
    # 优先检查 shebang
    if re.search(r'^#!.*python', sample, re.I | re.M):
        return 'python'
    if re.search(r'^#!.*node', sample, re.I | re.M):
        return 'javascript'
    if re.search(r'^#!.*bash|^#!/bin/sh', sample, re.I | re.M):
        return 'bash'
    # HTML（特异性高，优先）
    if re.search(r'^\s*<!DOCTYPE\s+html', sample, re.I) or \
       (re.search(r'^\s*<[a-zA-Z]+[\s>]', sample, re.M) and re.search(r'<\/', sample, re.M)):
        return 'html'
    # Python（放在Markdown之前，避免#注释和__变量名被误判）
    if re.search(r'^\s*import\s+\w+|from\s+\w+\s+import|def\s+\w+\s*\(|class\s+\w+.*:|print\s*\(|if\s+.*:\s*$', sample, re.M):
        return 'python'
    # JSON
    if re.search(r'^\s*(\{[\s\S]*\}|\[[\s\S]*\])\s*$', sample, re.M) and re.search(r'"[\w]+"\s*:', sample, re.M):
        return 'json'
    # CSS
    if re.search(r'^\s*(\.[\w-]+\s*\{|body\s*\{|@media|@import|color\s*:|padding\s*:|margin\s*:)', sample, re.M):
        return 'css'
    # JavaScript
    if re.search(r'^\s*(function|const|let|var)\s+\w+|console\.|document\.|window\.|=>|import\s+.*from|export\s+default', sample, re.M):
        return 'javascript'
    # C/C++
    if re.search(r'^\s*#include\s+|int\s+main\s*\(|cout\s*<<|printf\s*\(|std::', sample, re.M):
        return 'cpp'
    # Java
    if re.search(r'^\s*public\s+class\s+|private\s+|protected\s+|System\.out\.println|import\s+java\.', sample, re.M):
        return 'java'
    # Go
    if re.search(r'^\s*package\s+main|import\s+\(|func\s+\w+\(|fmt\.Println|go\s+func', sample, re.M):
        return 'go'
    # Rust
    if re.search(r'^\s*fn\s+main|let\s+\w+:|println!|use\s+std::|impl\s+', sample, re.M):
        return 'rust'
    # SQL
    if re.search(r'^\s*SELECT\s+|INSERT\s+|UPDATE\s+|DELETE\s+|CREATE\s+TABLE|FROM\s+\w+\s+WHERE', sample, re.I | re.M):
        return 'sql'
    # YAML
    if re.search(r'^\s*---\s*$|^\s*\w+:\s', sample, re.M):
        return 'yaml'
    # Bash
    if re.search(r'^\s*#!/bin/(bash|sh)|^\s*echo\s|^\s*cd\s|^\s*mkdir\s|^\s*git\s', sample, re.M):
        return 'bash'
    # Markdown（特征宽泛，放最后避免误匹配代码）
    md_patterns = [
        r'^#{1,6}\s', r'^\s*[-*+]\s', r'^\s*\d+\.\s', r'^\s*```',
        r'\|.*\|', r'!?\[.+\]\(.+\)', r'^\s*>\s', r'^\s*---\s*$', r'\*\*|__'
    ]
    if any(re.search(p, sample, re.M) for p in md_patterns):
        return 'markdown'
    return 'plaintext'

def get_file_extension(text, key):
    """根据内容自动获取文件扩展名，返回完整文件名"""
    lang = detect_code_lang(text)
    ext_map = {
        'python': 'py', 'javascript': 'js', 'json': 'json', 'html': 'html',
        'css': 'css', 'java': 'java', 'cpp': 'cpp', 'bash': 'sh',
        'sql': 'sql', 'yaml': 'yaml', 'go': 'go', 'rust': 'rs',
        'markdown': 'md', 'plaintext': 'txt'
    }
    ext = ext_map.get(lang, 'txt')
    # 如果 key 已经有扩展名，保留它
    if re.search(r'\.[a-zA-Z0-9]+$', key):
        return key
    return f"{key}.{ext}"

# 首页模板（简化版）
HOME_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TextDB - 在线文本与文件分享</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #f8fafc;
    color: #334155;
    line-height: 1.6;
}
a { text-decoration: none; color: inherit; }
.nav {
    position: sticky;
    top: 0;
    z-index: 50;
    background: rgba(255,255,255,0.85);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid #e2e8f0;
}
.nav-inner {
    max-width: 1100px;
    margin: 0 auto;
    padding: 0 20px;
    height: 64px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.nav-logo {
    font-size: 1.4rem;
    font-weight: 700;
    color: #3b82f6;
    display: flex;
    align-items: center;
    gap: 8px;
}
.nav-links { display: flex; gap: 32px; }
.nav-links a {
    font-size: 0.95rem;
    color: #64748b;
    font-weight: 500;
    transition: color 0.2s;
}
.nav-links a:hover { color: #3b82f6; }
.nav-mobile-btn { display: none; background: none; border: none; font-size: 1.5rem; cursor: pointer; color: #64748b; }
.hero {
    text-align: center;
    padding: 60px 20px 40px;
    background: linear-gradient(180deg, #eff6ff 0%, #f8fafc 100%);
}
.hero h1 { font-size: 2.4rem; color: #1e293b; margin-bottom: 10px; }
.hero p { font-size: 1.1rem; color: #64748b; max-width: 500px; margin: 0 auto 30px; }
.main-card {
    max-width: 720px;
    margin: 0 auto;
    background: #fff;
    border-radius: 16px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 4px 20px rgba(0,0,0,0.05);
    overflow: hidden;
}
.tabs { display: flex; border-bottom: 1px solid #e2e8f0; background: #f8fafc; }
.tab {
    flex: 1;
    padding: 16px;
    text-align: center;
    cursor: pointer;
    font-weight: 500;
    color: #64748b;
    background: transparent;
    border: none;
    font-size: 0.95rem;
    transition: all 0.2s;
}
.tab.active { color: #3b82f6; background: #fff; box-shadow: inset 0 -2px 0 #3b82f6; }
.tab-content { display: none; padding: 24px; }
.tab-content.active { display: block; }
textarea {
    width: 100%;
    min-height: 260px;
    padding: 16px;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    font-size: 15px;
    line-height: 1.6;
    resize: vertical;
    outline: none;
    transition: border-color 0.2s, box-shadow 0.2s;
    font-family: inherit;
}
textarea:focus { border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59,130,246,0.08); }
.upload-zone {
    border: 2px dashed #cbd5e1;
    border-radius: 12px;
    padding: 48px 24px;
    text-align: center;
    cursor: pointer;
    transition: all 0.2s;
    color: #64748b;
}
.upload-zone:hover { border-color: #3b82f6; background: #f8fafc; }
.file-info {
    display: none;
    margin-top: 16px;
    padding: 12px 16px;
    background: #f1f5f9;
    border-radius: 8px;
    font-size: 0.9rem;
    align-items: center;
    gap: 10px;
}
.file-info.show { display: flex; }
.options {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-top: 16px;
}
.option label {
    display: block;
    font-size: 0.85rem;
    color: #64748b;
    margin-bottom: 6px;
    font-weight: 500;
}
input, select {
    width: 100%;
    padding: 10px 12px;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    font-size: 0.9rem;
    outline: none;
    background: #fff;
}
input:focus, select:focus { border-color: #3b82f6; }
.btn-primary {
    width: 100%;
    margin-top: 16px;
    padding: 14px;
    background: #3b82f6;
    color: #fff;
    border: none;
    border-radius: 10px;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
    transition: background 0.2s, transform 0.1s;
}
.btn-primary:hover { background: #2563eb; }
.btn-primary:active { transform: scale(0.99); }
.result {
    display: none;
    margin-top: 20px;
    padding: 16px;
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 10px;
}
.result.show { display: block; }
.result-url {
    display: flex;
    gap: 8px;
    margin-top: 10px;
}
.result-url input {
    flex: 1;
    background: #fff;
}
.result-url button {
    padding: 10px 16px;
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    cursor: pointer;
    font-size: 0.9rem;
    white-space: nowrap;
}
.result-url button:hover { border-color: #3b82f6; color: #3b82f6; }
.qr-img { max-width: 160px; margin-top: 12px; border-radius: 8px; }
.section { padding: 60px 20px; max-width: 1100px; margin: 0 auto; }
.section-title { font-size: 1.6rem; color: #1e293b; text-align: center; margin-bottom: 8px; }
.section-subtitle { text-align: center; color: #64748b; margin-bottom: 36px; font-size: 0.95rem; }
.features {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 20px;
}
.feature-card {
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 24px;
    transition: box-shadow 0.2s, transform 0.2s;
}
.feature-card:hover { box-shadow: 0 8px 24px rgba(0,0,0,0.06); transform: translateY(-2px); }
.feature-icon { width: 40px; height: 40px; background: #eff6ff; color: #3b82f6; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.2rem; margin-bottom: 14px; }
.feature-card h3 { font-size: 1.1rem; color: #1e293b; margin-bottom: 6px; }
.feature-card p { font-size: 0.9rem; color: #64748b; }
.steps { display: flex; flex-wrap: wrap; justify-content: center; gap: 24px; margin-top: 20px; }
.step { text-align: center; max-width: 260px; }
.step-num {
    width: 36px; height: 36px;
    background: #3b82f6; color: #fff;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-weight: 600; margin: 0 auto 12px;
}
.step h4 { font-size: 1rem; color: #1e293b; margin-bottom: 4px; }
.step p { font-size: 0.9rem; color: #64748b; }
.faq-item { border-bottom: 1px solid #e2e8f0; padding: 18px 0; }
.faq-item h4 { font-size: 1rem; color: #1e293b; margin-bottom: 6px; }
.faq-item p { font-size: 0.9rem; color: #64748b; }
footer {
    border-top: 1px solid #e2e8f0;
    padding: 40px 20px;
    text-align: center;
    color: #94a3b8;
    font-size: 0.85rem;
    background: #fff;
}
@media (max-width: 768px) {
    .nav-links { display: none; }
    .nav-mobile-btn { display: block; }
    .hero h1 { font-size: 1.8rem; }
    .hero { padding: 40px 16px 30px; }
    .options { grid-template-columns: 1fr; }
    .features { grid-template-columns: 1fr; }
    .section { padding: 40px 16px; }
}
</style>
</head>
<body>
<nav class="nav">
    <div class="nav-inner">
        <a href="/" class="nav-logo">📋 TextDB</a>
        <div class="nav-links">
            <a href="#features">功能</a>
            <a href="#usage">使用</a>
            <a href="#faq">FAQ</a>
        </div>
        <button class="nav-mobile-btn" onclick="document.getElementById('mobileMenu').classList.toggle('show')">☰</button>
    </div>
</nav>
<div class="hero">
    <h1>在线文本 & 文件分享</h1>
    <p>极简的数据暂存和传送工具，无需登录，即开即用</p>
    <div class="main-card">
        <div class="tabs">
            <button class="tab active" onclick="switchTab('text')">📝 文本</button>
            <button class="tab" onclick="switchTab('file')">📎 文件</button>
        </div>
        <div id="tab-text" class="tab-content active">
            <textarea id="content" placeholder="在此输入或粘贴文本内容..."></textarea>
            <div style="display:flex;justify-content:flex-end;margin-top:12px;gap:10px;">
                <button class="btn-copy" onclick="downloadHomeText()" style="padding:8px 16px;font-size:0.9rem;font-weight:500;cursor:pointer;border:none;border-radius:8px;background:#f1f5f9;color:#334155;">⬇️ 下载</button>
            </div>
        </div>
        <div id="tab-file" class="tab-content">
            <div class="upload-zone" onclick="document.getElementById('file-input').click()">
                <div style="font-size:2rem;margin-bottom:8px;">📁</div>
                <p>拖拽文件到此处，或 <span style="color:#3b82f6;text-decoration:underline;">点击选择</span></p>
                <p style="font-size:0.8rem;color:#94a3b8;margin-top:4px;">支持任意类型文件</p>
            </div>
            <input type="file" id="file-input" style="display:none" onchange="handleFile(this.files[0])">
            <div class="file-info" id="fileInfo">
                <span>📎</span>
                <span id="fileName" style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;"></span>
                <span id="fileSize" style="color:#94a3b8;font-size:0.85rem;"></span>
                <span onclick="removeFile()" style="color:#ef4444;cursor:pointer;font-size:0.85rem;">删除</span>
            </div>
        </div>
        <div style="padding: 0 24px 24px;">
            <div class="options">
                <div class="option">
                    <label>🔗 自定义链接（可选）</label>
                    <input type="text" id="customKey" placeholder="留空则自动生成">
                </div>
                <div class="option">
                    <label>⏱ 过期时间</label>
                    <select id="ttl">
                        <option value="">永不过期</option>
                        <option value="1h">1 小时</option>
                        <option value="1d">1 天</option>
                        <option value="7d">7 天</option>
                        <option value="30d">30 天</option>
                    </select>
                </div>
                <div class="option">
                    <label>🔑 访问密码（可选）</label>
                    <input type="password" id="password" placeholder="不设密码直接访问">
                </div>
            </div>
            <button class="btn-primary" onclick="submit()">🚀 创建分享链接</button>
            <div class="result" id="result">
                <div style="color:#16a34a;font-weight:600;margin-bottom:4px;">✅ 创建成功！</div>
                <div class="result-url">
                    <input id="resultUrl" readonly>
                    <button onclick="copyUrl()">📋 复制</button>
                </div>
                <div id="resultExtra" style="margin-top:8px;font-size:0.85rem;color:#64748b;"></div>
                <div style="text-align:center;">
                    <img id="qrImg" class="qr-img" src="" alt="二维码">
                </div>
            </div>
        </div>
    </div>
</div>
<section class="section" id="usage">
    <h2 class="section-title">使用方法</h2>
    <p class="section-subtitle">三步完成数据暂存与分享</p>
    <div class="steps">
        <div class="step">
            <div class="step-num">1</div>
            <h4>输入内容</h4>
            <p>在文本框中输入内容，或拖拽上传任意文件</p>
        </div>
        <div class="step">
            <div class="step-num">2</div>
            <h4>设置选项</h4>
            <p>选择过期时间、设置访问密码，或自定义链接地址</p>
        </div>
        <div class="step">
            <div class="step-num">3</div>
            <h4>复制链接</h4>
            <p>一键生成专属链接，跨设备随时访问</p>
        </div>
    </div>
</section>
<section class="section" id="features" style="background:#fff;border-radius:24px 24px 0 0;margin-top:20px;">
    <h2 class="section-title">核心优势</h2>
    <p class="section-subtitle">为什么选择 TextDB</p>
    <div class="features">
        <div class="feature-card">
            <div class="feature-icon">🔒</div>
            <h3>密码保护</h3>
            <p>敏感信息可设置访问密码，防止被他人随意查看</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">⏱</div>
            <h3>自动过期</h3>
            <p>支持设置过期时间，到期自动清理，不留痕迹</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">📱</div>
            <h3>扫码访问</h3>
            <p>生成链接的同时提供二维码，手机扫码即可查看</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">✏️</div>
            <h3>在线编辑</h3>
            <p>文本内容支持在线直接编辑和保存，实时更新</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">📎</div>
            <h3>文件分享</h3>
            <p>不仅支持文本，任意类型文件均可快速分享</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon">⚡</div>
            <h3>无需登录</h3>
            <p>打开网页即用，无需注册账号，简单高效</p>
        </div>
    </div>
</section>
<section class="section">
    <h2 class="section-title">使用建议</h2>
    <p class="section-subtitle">为了更好地使用 TextDB，请参考以下建议</p>
    <div class="features">
        <div class="feature-card">
            <div class="feature-icon" style="background:#fef2f2;color:#ef4444;">⚠️</div>
            <h3>勿作永久存储</h3>
            <p>TextDB 定位为临时数据中转，重要文件请保存到本地或专业网盘</p>
        </div>
        <div class="feature-card">
            <div class="feature-icon" style="background:#fef2f2;color:#ef4444;">🔐</div>
            <h3>敏感信息设密码</h3>
            <p>传递账号密码等私密信息时，务必添加访问密码</p>
        </div>
    </div>
</section>
<section class="section" id="faq">
    <h2 class="section-title">常见问题</h2>
    <div class="faq-item">
        <h4>Q: 数据会保存多久？</h4>
        <p>A: 默认永久保存，但您可以设置 1小时到30天不等的过期时间。过期后内容将自动清理。</p>
    </div>
    <div class="faq-item">
        <h4>Q: 最大支持多大的文件？</h4>
        <p>A: 当前支持绝大多数常见文件类型，具体大小限制取决于服务器配置。</p>
    </div>
    <div class="faq-item">
        <h4>Q: 忘记密码怎么办？</h4>
        <p>A: 由于无需注册账号，如果您遗忘了访问密码，我们将无法为您找回，请妥善保管。</p>
    </div>
</section>
<footer>
    <p>TextDB · 安全可靠的在线分享工具</p>
    <p style="margin-top:6px;">已存储 {{ stats.text_count }} 个文本 · {{ stats.file_count }} 个文件</p>
</footer>
<script>
let currentTab = 'text';
let selectedFile = null;
function switchTab(tab) {
    currentTab = tab;
    document.querySelectorAll('.tab').forEach((t, i) => {
        t.classList.toggle('active', (i === 0 && tab === 'text') || (i === 1 && tab === 'file'));
    });
    document.getElementById('tab-text').classList.toggle('active', tab === 'text');
    document.getElementById('tab-file').classList.toggle('active', tab === 'file');
    document.getElementById('result').classList.remove('show');
}
const zone = document.querySelector('.upload-zone');
zone.addEventListener('dragover', e => { e.preventDefault(); zone.style.borderColor = '#3b82f6'; zone.style.background = '#f8fafc'; });
zone.addEventListener('dragleave', () => { zone.style.borderColor = ''; zone.style.background = ''; });
zone.addEventListener('drop', e => { e.preventDefault(); zone.style.borderColor = ''; zone.style.background = ''; if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]); });
function handleFile(file) {
    if (!file) return;
    selectedFile = file;
    document.getElementById('fileName').textContent = file.name;
    document.getElementById('fileSize').textContent = (file.size / 1024).toFixed(1) + ' KB';
    document.getElementById('fileInfo').classList.add('show');
}
function removeFile() {
    selectedFile = null;
    document.getElementById('file-input').value = '';
    document.getElementById('fileInfo').classList.remove('show');
}
async function submit() {
    const ttl = document.getElementById('ttl').value;
    const password = document.getElementById('password').value;
    const customKey = document.getElementById('customKey').value.trim();
    if (currentTab === 'text') {
        const content = document.getElementById('content').value.trim();
        if (!content) { alert('请输入内容'); return; }
        const body = { content: content, key: customKey, expires: ttl, password: password };
        const r = await fetch('/api/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        const d = await r.json();
        if (d.success) showResult(d);
        else if (d.exists) {
            if (confirm('该链接已存在内容，是否覆盖？')) {
                body.overwrite = true;
                const r2 = await fetch('/api/save', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
                const d2 = await r2.json();
                if (d2.success) showResult(d2);
                else alert(d2.error || '保存失败');
            }
        } else alert(d.error || '创建失败');
    } else {
        if (!selectedFile) { alert('请选择文件'); return; }
        const fd = new FormData();
        fd.append('file', selectedFile);
        fd.append('key', customKey);
        fd.append('expires', ttl);
        fd.append('password', password);
        const r = await fetch('/api/upload', { method: 'POST', body: fd });
        const d = await r.json();
        if (d.success) showResult(d);
        else alert(d.error || '上传失败');
    }
}
function showResult(d) {
    document.getElementById('resultUrl').value = d.url;
    document.getElementById('result').classList.add('show');
    let extra = '';
    const ttl = document.getElementById('ttl');
    if (ttl.value) extra += '⏱ 过期时间: ' + ttl.options[ttl.selectedIndex].text;
    if (d.has_password) extra += ' 🔒 已设置密码保护';
    if (document.getElementById('customKey').value.trim()) extra += ' 🔗 自定义链接';
    document.getElementById('resultExtra').textContent = extra;
    if (d.qr_code) { document.getElementById('qrImg').src = d.qr_code; document.getElementById('qrImg').style.display = 'inline-block'; }
    else { document.getElementById('qrImg').style.display = 'none'; }
    document.getElementById('result').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
function copyUrl() {
    const input = document.getElementById('resultUrl');
    navigator.clipboard.writeText(input.value).then(() => {
        const btn = document.querySelector('.result-url button');
        btn.textContent = '✅ 已复制';
        setTimeout(() => btn.textContent = '📋 复制', 1500);
    });
}
function showToast(msg) {
    const t = document.createElement('div');
    t.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#1e293b;color:#fff;padding:12px 24px;border-radius:8px;font-size:0.9rem;z-index:100;';
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 2000);
}
function isMarkdownLike(text) {
    if (!text) return false;
    const mdPatterns = [
        /^#{1,6}\s/m, /^\s*[-*+]\s/m, /^\s*\d+\.\s/m,
        /^\s*```/m, /\|.*\|/, /!?\[.+\]\(.+\)/,
        /^\s*>\s/m, /^\s*---\s*$/m, /\*\*|__/
    ];
    return mdPatterns.some(p => p.test(text));
}
function detectCodeLang(text) {
    if (!text || text.trim().length === 0) return 'plaintext';
    if (isMarkdownLike(text)) return 'markdown';
    const sample = text.slice(0, 3000);
    if (/^\s*<!DOCTYPE\s+html/i.test(sample) || (/^\s*<[a-zA-Z]+[\s>]/m.test(sample) && /<\//m.test(sample))) return 'html';
    if (/^\s*(function|const|let|var)\s+\w+|console\.|document\.|window\.|=>|import\s+.*from|export\s+default/m.test(sample)) return 'javascript';
    if (/^\s*import\s+\w+|from\s+\w+\s+import|def\s+\w+\s*\(|class\s+\w+.*:|print\s*\(|if\s+.*:\s*$|#.*python|#!\\/usr\\/bin\\/env python/m.test(sample)) return 'python';
    if (/^\s*(\{[\s\S]*\}|\[[\s\S]*\])\s*$/m.test(sample) && /"[\w]+"\s*:/m.test(sample)) return 'json';
    if (/^\s*(\.[\w-]+\s*\{|body\s*\{|@media|@import|color\s*:|padding\s*:|margin\s*:)/m.test(sample)) return 'css';
    if (/^\s*#include\s+|int\s+main\s*\(|cout\s*<<|printf\s*\(|std::/m.test(sample)) return 'cpp';
    if (/^\s*public\s+class\s+|private\s+|protected\s+|System\.out\.println|import\s+java\./m.test(sample)) return 'java';
    if (/^\s*package\s+main|import\s+\(|func\s+\w+\(|fmt\.Println|go\s+func/m.test(sample)) return 'go';
    if (/^\s*fn\s+main|let\s+\w+:|println!|use\s+std::|impl\s+/m.test(sample)) return 'rust';
    if (/^\s*SELECT\s+|INSERT\s+|UPDATE\s+|DELETE\s+|CREATE\s+TABLE|FROM\s+\w+\s+WHERE/mi.test(sample)) return 'sql';
    if (/^\s*---\s*$|^\s*\w+:\s/m.test(sample)) return 'yaml';
    if (/^\\s*#!\\/bin\\/(bash|sh)|^\\s*echo\\s|^\\s*cd\\s|^\\s*mkdir\\s|^\\s*git\\s/m.test(sample)) return 'bash';
    return 'plaintext';
}
function downloadHomeText() {
    var content = document.getElementById('content').value;
    if (!content.trim()) { showToast('内容为空'); return; }
    var detected = detectCodeLang(content);
    var extMap = {
        'python': 'py', 'javascript': 'js', 'json': 'json', 'html': 'html',
        'css': 'css', 'java': 'java', 'cpp': 'cpp', 'bash': 'sh',
        'sql': 'sql', 'yaml': 'yaml', 'go': 'go', 'rust': 'rs',
        'markdown': 'md', 'plaintext': 'txt'
    };
    var ext = extMap[detected] || 'txt';
    var filename = 'download.' + ext;
    var blob = new Blob([content], {type: 'text/plain;charset=utf-8'});
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('✅ 已下载 ' + filename);
}
</script>
</body>
</html>"""

VIEW_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ title }} - TextDB</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/python.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/javascript.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/bash.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/json.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/css.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/xml.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/java.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/cpp.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/sql.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/go.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/rust.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/yaml.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/js-beautify/1.15.1/beautify.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/js-beautify/1.15.1/beautify-css.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/js-beautify/1.15.1/beautify-html.min.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #f8fafc;
    color: #334155;
    line-height: 1.6;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}
a { text-decoration: none; color: inherit; }
.nav {
    position: sticky;
    top: 0;
    z-index: 50;
    background: rgba(255,255,255,0.9);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid #e2e8f0;
}
.nav-inner {
    max-width: 1100px;
    margin: 0 auto;
    padding: 0 20px;
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.nav-logo { font-size: 1.3rem; font-weight: 700; color: #3b82f6; display: flex; align-items: center; gap: 8px; }
.nav-back {
    font-size: 0.9rem;
    color: #64748b;
    font-weight: 500;
    padding: 8px 14px;
    border-radius: 8px;
    transition: background 0.2s;
}
.nav-back:hover { background: #f1f5f9; color: #3b82f6; }
.main { flex: 1; display: flex; flex-direction: column; }
.container { max-width: 900px; margin: 0 auto; padding: 24px 20px; width: 100%; }
.card {
    background: #fff;
    border-radius: 16px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 4px 20px rgba(0,0,0,0.05);
    overflow: hidden;
}
.editor-header {
    padding: 16px 20px;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    background: #fafafa;
}
.editor-title { font-size: 1rem; font-weight: 600; color: #1e293b; display: flex; align-items: center; gap: 8px; }
.editor-meta { font-size: 0.85rem; color: #94a3b8; }
.editor-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.editor-actions button {
    padding: 8px 16px;
    border: none;
    border-radius: 8px;
    font-size: 0.9rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
}
.btn-save { background: #3b82f6; color: #fff; }
.btn-save:hover { background: #2563eb; }
.btn-copy { background: #f1f5f9; color: #334155; }
.btn-copy:hover { background: #e2e8f0; }
.editor-area {
    padding: 20px;
    min-height: calc(100vh - 200px);
}
.editor-area textarea {
    width: 100%;
    min-height: 60vh;
    padding: 16px;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    font-family: "SF Mono", SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
    font-size: 14px;
    line-height: 1.7;
    resize: vertical;
    outline: none;
    background: #fafafa;
    color: #1e293b;
}
.lang-bar {
    padding: 10px 20px;
    background: #f8fafc;
    border-bottom: 1px solid #e2e8f0;
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
}
.lang-bar span { font-size: 0.85rem; color: #64748b; font-weight: 500; }
.lang-bar select {
    padding: 6px 12px;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    font-size: 0.9rem;
    background: #fff;
    cursor: pointer;
}
.lang-bar button { padding: 6px 14px; font-size: 0.85rem; }
.editor-area textarea:focus { border-color: #3b82f6; background: #fff; }
.markdown-body {
    padding: 24px;
    line-height: 1.8;
    color: #334155;
    background: #fff;
}
.markdown-body h1, .markdown-body h2, .markdown-body h3,
.markdown-body h4, .markdown-body h5, .markdown-body h6 {
    margin-top: 24px; margin-bottom: 16px;
    font-weight: 600; color: #1e293b;
}
.markdown-body h1 { font-size: 1.8em; border-bottom: 1px solid #e2e8f0; padding-bottom: 10px; }
.markdown-body h2 { font-size: 1.4em; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px; }
.markdown-body p { margin-bottom: 16px; }
.markdown-body ul, .markdown-body ol { padding-left: 2em; margin-bottom: 16px; }
.markdown-body code { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 85%; }
.markdown-body pre { background: #f8fafc; padding: 16px; border-radius: 8px; overflow-x: auto; margin-bottom: 16px; }
.markdown-body pre code { background: transparent; padding: 0; }
.markdown-body blockquote { border-left: 4px solid #e2e8f0; padding-left: 16px; color: #64748b; margin-bottom: 16px; }
.markdown-body a { color: #3b82f6; }
.markdown-body img { max-width: 100%; }
.file-card { text-align: center; padding: 60px 40px; }
.file-icon { font-size: 4rem; margin-bottom: 16px; }
.file-name { font-size: 1.3rem; color: #1e293b; margin-bottom: 8px; word-break: break-word; }
.file-size { color: #64748b; margin-bottom: 24px; }
.btn-download {
    display: inline-block;
    background: #3b82f6;
    color: #fff;
    padding: 14px 36px;
    border-radius: 10px;
    font-weight: 600;
    transition: background 0.2s;
}
.btn-download:hover { background: #2563eb; }
.auth-card { max-width: 400px; margin: 80px auto; text-align: center; padding: 40px; }
.auth-card h2 { font-size: 1.4rem; margin-bottom: 8px; color: #1e293b; }
.auth-card p { color: #64748b; margin-bottom: 24px; font-size: 0.95rem; }
.auth-card input {
    width: 100%;
    padding: 14px;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    font-size: 16px;
    margin-bottom: 16px;
    outline: none;
}
.auth-card input:focus { border-color: #3b82f6; }
.auth-card button {
    width: 100%;
    padding: 14px;
    background: #3b82f6;
    color: #fff;
    border: none;
    border-radius: 10px;
    font-size: 1rem;
    font-weight: 600;
    cursor: pointer;
}
.auth-card button:hover { background: #2563eb; }
.auth-error { color: #ef4444; margin-top: 12px; font-size: 0.9rem; }
.error-card { text-align: center; padding: 80px 40px; }
.error-card h1 { font-size: 1.8rem; color: #1e293b; margin-bottom: 10px; }
.error-card p { color: #64748b; }
.notice {
    text-align: center;
    padding: 12px;
    font-size: 0.85rem;
    color: #94a3b8;
    background: #fff;
    border-top: 1px solid #e2e8f0;
}
.toast {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%) translateY(100px);
    background: #1e293b;
    color: #fff;
    padding: 12px 24px;
    border-radius: 8px;
    font-size: 0.9rem;
    opacity: 0;
    transition: all 0.3s;
    z-index: 100;
}
.toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
.hidden { display: none !important; }
.mode-active { background: #3b82f6 !important; color: #fff !important; }
@media (max-width: 640px) {
    .editor-header { padding: 12px 16px; }
    .editor-area { padding: 12px; min-height: calc(100vh - 160px); }
    .editor-area textarea { min-height: 50vh; font-size: 15px; }
    .auth-card { margin: 40px 16px; padding: 32px 24px; }
    .file-card { padding: 40px 24px; }
    .markdown-body { padding: 16px; }
}
</style>
</head>
<body>
<nav class="nav">
    <div class="nav-inner">
        <a href="/" class="nav-logo">📋 TextDB</a>
        <a href="/" class="nav-back">← 返回首页</a>
    </div>
</nav>
<div class="main">
    <div class="container">
        {% if need_password %}
        <div class="card auth-card">
            <h2>🔒 需要密码</h2>
            <p>此内容已设置密码保护</p>
            <form method="POST">
                <input type="password" name="password" placeholder="请输入访问密码" required autofocus>
                <button type="submit">🔓 解锁查看</button>
                {% if error %}<div class="auth-error">{{ error }}</div>{% endif %}
            </form>
        </div>
        {% elif expired %}
        <div class="card error-card">
            <h1>⏰ 内容已过期</h1>
            <p>此内容已达到设定的过期时间，已被自动清理</p>
        </div>
        {% elif not_found %}
        <div class="card error-card">
            <h1>❓ 内容不存在</h1>
            <p>您访问的内容不存在或已被删除</p>
        </div>
        {% else %}
        <div class="card">
            <div class="editor-header">
                <div>
                    <div class="editor-title">📝 {{ title }}</div>
                    <div class="editor-meta">访问次数 {{ access_count }} · 可直接编辑保存</div>
                </div>
                <div class="editor-actions">
                    {% if is_text %}
                    <button class="btn-copy" id="btnPreview" onclick="switchMode('preview')">👁 预览</button>
                    <button class="btn-copy" id="btnEdit" onclick="switchMode('edit')">📝 编辑</button>
                    <button class="btn-copy" onclick="copyAll()">📋 复制</button>
                    <button class="btn-copy" onclick="downloadText()">⬇️ 下载</button>
                    <button class="btn-save" onclick="saveEdit()">💾 保存</button>
                    {% endif %}
                </div>
            </div>
            {% if is_text %}
            <div class="lang-bar" id="langBar">
                <span>语言模式</span>
                <select id="langSelect" onchange="onLangChange()">
                    <option value="auto">🔍 自动检测</option>
                    <option value="markdown">📝 Markdown</option>
                    <option value="plaintext">📄 纯文本</option>
                    <option value="python">🐍 Python</option>
                    <option value="javascript">📜 JavaScript</option>
                    <option value="json">📋 JSON</option>
                    <option value="html">🌐 HTML</option>
                    <option value="css">🎨 CSS</option>
                    <option value="java">☕ Java</option>
                    <option value="cpp">🔧 C/C++</option>
                    <option value="bash">💻 Bash</option>
                    <option value="sql">🗄️ SQL</option>
                    <option value="yaml">⚙️ YAML</option>
                    <option value="go">🐹 Go</option>
                    <option value="rust">⚙️ Rust</option>
                </select>
                <button class="btn-copy" onclick="formatCode()">🎨 格式化</button>
            </div>
            {% endif %}
            <div class="content-area">
                {% if is_text %}
                <div class="editor-area" id="editorArea">
                    <textarea id="editContent" oninput="updateCharCount()">{{ content | forceescape }}</textarea>
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:12px;">
                        <span id="charCount" style="font-size:0.85rem;color:#94a3b8;">{{ content | length }} 字符</span>
                        <span id="editResult" style="font-size:0.9rem;display:none;"></span>
                    </div>
                </div>
                <div class="markdown-body hidden" id="markdownBody"></div>
                {% else %}
                <div class="file-card">
                    <div class="file-icon">📁</div>
                    <div class="file-name">{{ filename }}</div>
                    <div class="file-size">{{ file_size }}</div>
                    <a href="/d/{{ key }}" class="btn-download">⬇️ 下载文件</a>
                </div>
                {% endif %}
            </div>
        </div>
        {% endif %}
    </div>
</div>
<div class="notice">
    TextDB · 安全可靠的在线分享工具
</div>
<div class="toast" id="toast"></div>
<script>
function showToast(msg) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), 2000);
}
function saveEdit(){
    var content=document.getElementById('editContent').value;
    if(!content.trim()){showToast('内容不能为空');return}
    var btn=document.querySelector('.btn-save');
    var old=btn.textContent;btn.textContent='⏳ 保存中...';btn.disabled=true;
    fetch('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:content,key:'{{ title }}',overwrite:true})}).then(r=>r.json()).then(data=>{
        btn.textContent=old;btn.disabled=false;
        if(data.success){showToast('✅ 保存成功');}
        else{showToast('❌ '+data.error)}
    }).catch(()=>{btn.textContent=old;btn.disabled=false;showToast('网络错误')})
}
function copyAll(){
    var content=document.getElementById('editContent').value;
    navigator.clipboard.writeText(content).then(()=>showToast('✅ 已复制')).catch(()=>showToast('复制失败'))
}
function downloadText(){
    var content=document.getElementById('editContent').value;
    var filename='{{ title }}';
    var lang=document.getElementById('langSelect').value;
    var detected=lang==='auto'?detectCodeLang(content):lang;
    var extMap={
        'python':'py','javascript':'js','json':'json','html':'html',
        'css':'css','java':'java','cpp':'cpp','bash':'sh',
        'sql':'sql','yaml':'yaml','go':'go','rust':'rs',
        'markdown':'md','plaintext':'txt'
    };
    var ext=extMap[detected]||'txt';
    var hasExt=filename.match(/\.[a-zA-Z0-9]+$/i);
    if(hasExt){
        var currentExt=hasExt[0].toLowerCase();
        if(currentExt==='.txt'&&ext!=='txt'){
            filename=filename.slice(0,-4)+'.'+ext;
        }
    }else{
        filename+='.'+ext;
    }
    var blob=new Blob([content],{type:'text/plain;charset=utf-8'});
    var url=URL.createObjectURL(blob);
    var a=document.createElement('a');
    a.href=url;
    a.download=filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('✅ 已下载 '+filename);
}
function updateCharCount(){
    var c=document.getElementById('editContent').value.length;
    document.getElementById('charCount').textContent=c+' 字符';
}
function isMarkdownLike(text) {
    if (!text) return false;
    const mdPatterns = [
        /^#{1,6}\s/m,               // 标题
        /^\s*[-*+]\s/m,            // 列表
        /^\s*\d+\.\s/m,             // 有序列表
        /^\s*```/m,                // 代码块
        /\|.*\|/,                   // 表格
        /!?\[.+\]\(.+\)/,           // 链接/图片
        /^\s*>\s/m,                // 引用
        /^\s*---\s*$/m,            // 分割线
        /\*\*|__/                  // 粗体/斜体
    ];
    return mdPatterns.some(p => p.test(text));
}
function detectCodeLang(text) {
    if (!text || text.trim().length === 0) return 'plaintext';
    const sample = text.slice(0, 3000);
    // 优先检查 shebang
    if (/^#!.*python/mi.test(sample)) return 'python';
    if (/^#!.*node/mi.test(sample)) return 'javascript';
    if (/^#!.*bash|^#!\/bin\/sh/mi.test(sample)) return 'bash';
    // HTML
    if (/^\s*<!DOCTYPE\s+html/i.test(sample) || /^\s*<[a-zA-Z]+[\s>]/m.test(sample) && /<\//m.test(sample)) return 'html';
    // Python（放在Markdown之前，避免#注释和__变量名被误判）
    if (/^\s*import\s+\w+|from\s+\w+\s+import|def\s+\w+\s*\(|class\s+\w+.*:|print\s*\(|if\s+.*:\s*$/m.test(sample)) return 'python';
    // JSON
    if (/^\s*(\{[\s\S]*\}|\[[\s\S]*\])\s*$/m.test(sample) && /"[\w]+"\s*:/m.test(sample)) return 'json';
    // CSS
    if (/^\s*(\.[\w-]+\s*\{|body\s*\{|@media|@import|color\s*:|padding\s*:|margin\s*:)/m.test(sample)) return 'css';
    // JavaScript
    if (/^\s*(function|const|let|var)\s+\w+|console\.|document\.|window\.|=>|import\s+.*from|export\s+default/m.test(sample)) return 'javascript';
    // C/C++
    if (/^\s*#include\s+|int\s+main\s*\(|cout\s*<<|printf\s*\(|std::/m.test(sample)) return 'cpp';
    // Java
    if (/^\s*public\s+class\s+|private\s+|protected\s+|System\.out\.println|import\s+java\./m.test(sample)) return 'java';
    // Go
    if (/^\s*package\s+main|import\s+\(|func\s+\w+\(|fmt\.Println|go\s+func/m.test(sample)) return 'go';
    // Rust
    if (/^\s*fn\s+main|let\s+\w+:|println!|use\s+std::|impl\s+/m.test(sample)) return 'rust';
    // SQL
    if (/^\s*SELECT\s+|INSERT\s+|UPDATE\s+|DELETE\s+|CREATE\s+TABLE|FROM\s+\w+\s+WHERE/mi.test(sample)) return 'sql';
    // YAML
    if (/^\s*---\s*$|^\s*\w+:\s/m.test(sample)) return 'yaml';
    // Bash
    if (/^\\s*#!\\/bin\\/(bash|sh)|^\\s*echo\\s|^\\s*cd\\s|^\\s*mkdir\\s|^\\s*git\\s/m.test(sample)) return 'bash';
    // Markdown（特征宽泛，放最后避免误匹配代码）
    if (isMarkdownLike(text)) return 'markdown';
    return 'plaintext';
}
function onLangChange() {
    const previewBtn = document.getElementById('btnPreview');
    if (previewBtn && previewBtn.classList.contains('mode-active')) {
        renderPreview();
    }
}
function renderPreview() {
    const markdownBody = document.getElementById('markdownBody');
    const editContent = document.getElementById('editContent');
    const lang = document.getElementById('langSelect').value;
    const raw = editContent.value;
    markdownBody.className = 'markdown-body';
    markdownBody.innerHTML = '';
    if (lang === 'auto') {
        const detected = detectCodeLang(raw);
        if (detected === 'markdown') renderMarkdownPreview(raw);
        else if (detected === 'plaintext') renderPlainPreview(raw);
        else renderCodePreview(raw, detected);
    } else if (lang === 'markdown') renderMarkdownPreview(raw);
    else if (lang === 'plaintext') renderPlainPreview(raw);
    else renderCodePreview(raw, lang);
}
function renderPlainPreview(raw) {
    const markdownBody = document.getElementById('markdownBody');
    const pre = document.createElement('pre');
    pre.style = 'background:#f8fafc;padding:16px;border-radius:8px;overflow-x:auto;white-space:pre-wrap;word-break:break-word;';
    pre.textContent = raw;
    markdownBody.appendChild(pre);
}
function renderMarkdownPreview(raw) {
    const markdownBody = document.getElementById('markdownBody');
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            highlight: function(code, lang) {
                if (lang && hljs.getLanguage(lang)) return hljs.highlight(code, { language: lang }).value;
                try { return hljs.highlightAuto(code).value; } catch(e) { return code; }
            },
            breaks: true, gfm: true
        });
        markdownBody.innerHTML = marked.parse(raw);
        markdownBody.querySelectorAll('pre code').forEach((block) => { hljs.highlightElement(block); });
    } else {
        renderPlainPreview(raw);
    }
}
function renderCodePreview(raw, lang) {
    const markdownBody = document.getElementById('markdownBody');
    const pre = document.createElement('pre');
    pre.style = 'background:#f8fafc;padding:0;border-radius:8px;overflow-x:auto;margin:0;';
    const code = document.createElement('code');
    code.className = (lang && lang !== 'auto' && lang !== 'plaintext') ? 'language-' + lang : '';
    code.textContent = raw;
    pre.appendChild(code);
    markdownBody.appendChild(pre);
    if (typeof hljs !== 'undefined') {
        try { hljs.highlightElement(code); } catch(e) {}
    }
}
function formatCode() {
    const ta = document.getElementById('editContent');
    const raw = ta.value;
    const lang = document.getElementById('langSelect').value;
    const detected = lang === 'auto' ? detectCodeLang(raw) : lang;
    if (detected === 'json') {
        try {
            const obj = JSON.parse(raw);
            ta.value = JSON.stringify(obj, null, 4);
            showToast('✅ JSON 格式化成功');
            updateCharCount();
            onLangChange();
            return;
        } catch(e) {
            showToast('❌ JSON 格式错误: ' + e.message);
            return;
        }
    }
    if (typeof beautify !== 'undefined' && detected === 'javascript') {
        try {
            ta.value = beautify.js_beautify(raw, { indent_size: 4 });
            showToast('✅ JS 格式化成功');
            updateCharCount();
            onLangChange();
            return;
        } catch(e) {}
    }
    if (typeof css_beautify !== 'undefined' && detected === 'css') {
        try {
            ta.value = css_beautify(raw, { indent_size: 4 });
            showToast('✅ CSS 格式化成功');
            updateCharCount();
            onLangChange();
            return;
        } catch(e) {}
    }
    if (typeof html_beautify !== 'undefined' && detected === 'html') {
        try {
            ta.value = html_beautify(raw, { indent_size: 4 });
            showToast('✅ HTML 格式化成功');
            updateCharCount();
            onLangChange();
            return;
        } catch(e) {}
    }
    showToast('ℹ️ 当前语言暂不支持自动格式化（支持 JSON/JS/CSS/HTML）');
}
function switchMode(mode) {
    const editorArea = document.getElementById('editorArea');
    const markdownBody = document.getElementById('markdownBody');
    const btnPreview = document.getElementById('btnPreview');
    const btnEdit = document.getElementById('btnEdit');
    if (mode === 'preview') {
        editorArea.classList.add('hidden');
        markdownBody.classList.remove('hidden');
        btnPreview.classList.add('mode-active');
        btnEdit.classList.remove('mode-active');
        renderPreview();
    } else {
        editorArea.classList.remove('hidden');
        markdownBody.classList.add('hidden');
        btnEdit.classList.add('mode-active');
        btnPreview.classList.remove('mode-active');
    }
}
document.addEventListener('DOMContentLoaded', function() {
    updateCharCount();
    {% if is_text %}
    const content = document.getElementById('editContent').value;
    const langSel = document.getElementById('langSelect');
    const detected = detectCodeLang(content);
    if (langSel) {
        for (let i = 0; i < langSel.options.length; i++) {
            if (langSel.options[i].value === detected) {
                langSel.selectedIndex = i;
                break;
            }
        }
    }
    const isMd = detected === 'markdown';
    switchMode(isMd ? 'preview' : 'edit');
    {% endif %}
});
</script>
</body>
</html>"""

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route('/')
def index():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM items WHERE type='text'")
    text_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM items WHERE type='file'")
    file_count = c.fetchone()[0]
    conn.close()
    return render_template_string(HOME_TEMPLATE, stats={'text_count': text_count, 'file_count': file_count})

@app.route('/api/check/<key>', methods=['GET'])
def check_key(key):
    """检查 key 是否已存在"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, content FROM items WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    if row:
        return jsonify({'exists': True, 'key': key})
    return jsonify({'exists': False, 'key': key})

@app.route('/api/save', methods=['POST'])
def save_text():
    data = request.get_json()
    content = data.get('content', '').strip()
    key = data.get('key', '').strip()
    password = data.get('password', '')
    expires = data.get('expires', '')
    overwrite = data.get('overwrite', False)
    if not content:
        return jsonify({'success': False, 'error': '内容不能为空'})
    if not key:
        key = generate_key()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM items WHERE key=?", (key,))
    existing = c.fetchone()
    if existing:
        if not overwrite:
            conn.close()
            return jsonify({'success': False, 'exists': True, 'error': '该链接已存在内容，是否覆盖？'})
        # 覆盖已有内容
        expires_at = None
        if expires:
            delta = {'1h': timedelta(hours=1), '1d': timedelta(days=1), 
                     '7d': timedelta(days=7), '30d': timedelta(days=30)}
            if expires in delta:
                expires_at = (datetime.now() + delta[expires]).isoformat()
        c.execute('UPDATE items SET content=?, password_hash=?, expires_at=? WHERE key=?',
                  (content, hash_password(password), expires_at, key))
        conn.commit()
        conn.close()
        url = f'http://{request.host}/{key}'
        qr_code = generate_qr_code(url)
        return jsonify({'success': True, 'key': key, 'url': url, 'has_password': bool(password), 'qr_code': qr_code, 'overwritten': True})
    expires_at = None
    if expires:
        delta = {'1h': timedelta(hours=1), '1d': timedelta(days=1), 
                 '7d': timedelta(days=7), '30d': timedelta(days=30)}
        if expires in delta:
            expires_at = (datetime.now() + delta[expires]).isoformat()
    c.execute('INSERT INTO items (key, type, content, password_hash, expires_at) VALUES (?, "text", ?, ?, ?)',
              (key, content, hash_password(password), expires_at))
    conn.commit()
    conn.close()
    
    url = f'http://{request.host}/{key}'
    qr_code = generate_qr_code(url)
    
    return jsonify({'success': True, 'key': key, 'url': url, 'has_password': bool(password), 'qr_code': qr_code})

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '没有选择文件'})
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'error': '文件名不能为空'})
    key = request.form.get('key', '').strip()
    password = request.form.get('password', '')
    expires = request.form.get('expires', '')
    if not key:
        key = generate_key()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM items WHERE key=?", (key,))
    if c.fetchone():
        conn.close()
        return jsonify({'success': False, 'error': '该链接已被使用'})
    filename = file.filename
    file_ext = os.path.splitext(filename)[1]
    file_key = secrets.token_hex(16)
    file_path = os.path.join(UPLOAD_DIR, file_key + file_ext)
    file.save(file_path)
    expires_at = None
    if expires:
        delta = {'1h': timedelta(hours=1), '1d': timedelta(days=1), 
                 '7d': timedelta(days=7), '30d': timedelta(days=30)}
        if expires in delta:
            expires_at = (datetime.now() + delta[expires]).isoformat()
    c.execute('INSERT INTO items (key, type, filename, file_path, password_hash, expires_at) VALUES (?, "file", ?, ?, ?, ?)',
              (key, filename, file_path, hash_password(password), expires_at))
    conn.commit()
    conn.close()
    
    url = f'http://{request.host}/{key}'
    qr_code = generate_qr_code(url)
    
    return jsonify({'success': True, 'key': key, 'url': url, 'has_password': bool(password), 'qr_code': qr_code})

@app.route('/<key>', methods=['GET', 'POST'])
def view_item(key):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM items WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    if not row:
        return render_template_string(VIEW_TEMPLATE, not_found=True)
    expires_at = row[7]
    if expires_at and datetime.now() > datetime.fromisoformat(expires_at):
        # 过期后自动删除记录和文件
        delete_item_by_key(key)
        return render_template_string(VIEW_TEMPLATE, expired=True)
    password_hash = row[6]
    if password_hash:
        if request.method == 'POST':
            input_password = request.form.get('password', '')
            if hash_password(input_password) != password_hash:
                return render_template_string(VIEW_TEMPLATE, need_password=True, error='密码错误')
        else:
            return render_template_string(VIEW_TEMPLATE, need_password=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE items SET access_count = access_count + 1 WHERE key=?", (key,))
    conn.commit()
    conn.close()
    item_type = row[2]
    access_count = row[9] if len(row) > 9 else 0
    if item_type == 'text':
        return render_template_string(VIEW_TEMPLATE, title=key, is_text=True, content=row[3], is_markdown=False, access_count=access_count)
    else:
        filename = row[4]
        file_path = row[5]
        file_size = os.path.getsize(file_path)
        size_str = f"{file_size/1024/1024:.2f} MB" if file_size > 1024*1024 else f"{file_size/1024:.2f} KB"
        # 检查是否是 Markdown 文件
        is_markdown = filename.lower().endswith('.md') or filename.lower().endswith('.markdown')
        if is_markdown:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    md_content = f.read()
                return render_template_string(VIEW_TEMPLATE, title=key, is_text=True, content=md_content, is_markdown=True, filename=filename, access_count=access_count)
            except:
                pass
        return render_template_string(VIEW_TEMPLATE, title=key, is_text=False, filename=filename, file_size=size_str, key=key, access_count=access_count)

@app.route('/d/<key>')
def download_file(key):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM items WHERE key=?", (key,))
    row = c.fetchone()
    conn.close()
    if not row:
        abort(404)
    if row[7] and datetime.now() > datetime.fromisoformat(row[7]):
        delete_item_by_key(key)
        abort(410)
    item_type = row[2]
    filename = row[4] or key
    file_path = row[5]
    if item_type == 'file':
        if not file_path or not os.path.exists(file_path):
            abort(404)
        return send_file(file_path, as_attachment=True, download_name=filename)
    else:
        # 文本类型：根据内容自动检测语言并设置扩展名
        content = row[3] or ''
        filename = get_file_extension(content, key)
        return send_file(io.BytesIO(content.encode('utf-8')), as_attachment=True, download_name=filename, mimetype='text/plain; charset=utf-8')

@app.route('/api/cleanup', methods=['POST'])
def api_cleanup():
    """手动触发清理过期文件"""
    count = cleanup_expired_items()
    return jsonify({'success': True, 'deleted': count})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=80, debug=False)
