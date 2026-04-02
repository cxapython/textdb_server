#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, hashlib, secrets, sqlite3, io, base64
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

# 首页模板（简化版）
HOME_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>TextDB - 在线文本与文件存储</title>
<style>
    /* 手机端适配 */
    @media (max-width: 768px) {
/* ========== iPhone 优化 ========== */
@media only screen and (max-width: 430px) {
/* ========== 基础样式（移动优先） ========== */
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    color: #333;
    line-height: 1.6;
}

.container {
    width: 100%;
    max-width: 100%;
    margin: 0 auto;
    padding: 15px 12px;
}

/* 超小屏手机（iPhone SE/mini 等） */
@media only screen and (max-width: 375px) {
    .container { padding: 12px 10px; }
    .header h1 { font-size: 1.6em; }
    .header p { font-size: 0.8em; }
    .tab { padding: 12px; font-size: 13px; }
    .content { padding: 15px 12px; }
    textarea { min-height: 150px; font-size: 15px; }
    .btn { padding: 14px; font-size: 15px; height: 48px; }
}

/* 小屏手机（iPhone 12/13/14/15/16/17 标准版） */
@media only screen and (min-width: 376px) and (max-width: 430px) {
    .container { padding: 15px 12px; }
    .header h1 { font-size: 1.8em; }
    .header p { font-size: 0.85em; }
    .tab { padding: 14px; font-size: 14px; }
    .content { padding: 18px 15px; }
    textarea { min-height: 180px; font-size: 16px; }
    .btn { padding: 16px; font-size: 16px; height: 52px; }
}

/* 大屏手机（iPhone Pro Max / Android 大屏） */
@media only screen and (min-width: 431px) and (max-width: 767px) {
    .container { padding: 20px 15px; }
    .header h1 { font-size: 2em; }
    .header p { font-size: 0.9em; }
    .row { grid-template-columns: 1fr 1fr; gap: 15px; }
    .tab { padding: 16px; font-size: 15px; }
    .content { padding: 25px 20px; }
}

/* 平板竖屏（iPad mini, iPad Air 竖屏） */
@media only screen and (min-width: 768px) and (max-width: 1024px) and (orientation: portrait) {
    .container { max-width: 90%; padding: 30px 20px; }
    .header h1 { font-size: 2.2em; }
    .row { grid-template-columns: 1fr 1fr; gap: 25px; }
    .tab { padding: 18px; font-size: 16px; }
    .content { padding: 35px 30px; }
    textarea { min-height: 280px; }
}

/* 平板横屏（iPad 横屏） */
@media only screen and (min-width: 768px) and (max-width: 1024px) and (orientation: landscape) {
    .container { max-width: 85%; padding: 25px 20px; }
    .header h1 { font-size: 2em; }
    .row { grid-template-columns: 1fr 1fr; gap: 20px; }
    .content { padding: 30px; }
}

/* 小桌面（笔记本 13-15寸） */
@media only screen and (min-width: 1025px) and (max-width: 1440px) {
    .container { max-width: 900px; padding: 40px 30px; }
    .header h1 { font-size: 2.5em; }
    .row { grid-template-columns: 1fr 1fr; gap: 25px; }
    .content { padding: 40px; }
}

/* 大桌面（外接显示器 24寸+） */
@media only screen and (min-width: 1441px) {
    .container { max-width: 1000px; padding: 50px 40px; }
    .header h1 { font-size: 3em; }
    .header p { font-size: 1.1em; }
    .card { box-shadow: 0 25px 80px rgba(0,0,0,0.35); }
    .row { grid-template-columns: 1fr 1fr; gap: 30px; }
    .content { padding: 45px; }
    textarea { min-height: 350px; font-size: 15px; }
}

/* 超宽屏（带鱼屏 21:9） */
@media only screen and (min-width: 1920px) {
    .container { max-width: 1200px; }
    .header h1 { font-size: 3.5em; }
}

/* ========== 特殊设备适配 ========== */

/* 折叠屏手机展开 */
@media only screen and (min-width: 700px) and (max-width: 900px) and (min-height: 1000px) {
    .container { max-width: 95%; }
    .row { grid-template-columns: 1fr 1fr; }
}

/* 横屏手机 */
@media only screen and (max-height: 500px) and (orientation: landscape) {
    .header { margin-bottom: 20px; }
    .header h1 { font-size: 1.5em; }
    textarea { min-height: 100px; }
    .tabs { flex-direction: row; }
    .tab { padding: 10px 15px; font-size: 13px; }
}

/* ========== iOS 特殊优化 ========== */
@supports (-webkit-touch-callout: none) {
    @media screen and (max-width: 430px) {
        input, select, textarea {
            font-size: 16px !important;
            -webkit-appearance: none;
            border-radius: 10px;
        }
        .btn {
            -webkit-tap-highlight-color: transparent;
        }
    }
}

/* ========== Android 优化 ========== */
@media screen and (-webkit-min-device-pixel-ratio: 2) and (max-width: 430px) {
    .btn, input, select, textarea {
        transform: translateZ(0);
    }
}

/* ========== 打印样式 ========== */
@media print {
    body {
        background: white !important;
        -webkit-print-color-adjust: exact;
    }
    .card {
        box-shadow: none;
        border: 1px solid #ddd;
    }
    .header {
        background: #667eea !important;
        -webkit-print-color-adjust: exact;
    }
    .tabs, .btn, .file-upload {
        display: none;
    }
    .content {
        padding: 20px;
    }
}

/* ========== 深色模式（系统级） ========== */
@media (prefers-color-scheme: dark) {
    @media only screen and (min-width: 1025px) {
        /* 桌面端深色模式 */
    }
}

/* ========== 减少动画（无障碍） ========== */
@media (prefers-reduced-motion: reduce) {
    * {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }
}

/* ========== 高对比度模式 ========== */
@media (prefers-contrast: high) {
    .btn, .tab.active {
        border: 2px solid currentColor;
    }
}
    /* iPhone 14/15/16/17 Pro Max 系列 */
    body { 
        padding: 15px 12px; 
        -webkit-text-size-adjust: 100%;
    }
    .container { 
        max-width: 100%; 
        padding: 0;
    }
    .header { 
        margin-bottom: 25px; 
        padding: 0 5px;
    }
    .header h1 { 
        font-size: 1.8em; 
        margin-bottom: 8px;
    }
    .header p { 
        font-size: 0.85em; 
        line-height: 1.4;
    }
    .stats { 
        font-size: 0.75em; 
        padding: 6px 12px;
        margin-top: 8px;
    }
    
    /* 卡片优化 */
    .card { 
        border-radius: 12px; 
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
    
    /* 标签页 */
    .tabs { 
        flex-direction: column;
    }
    .tab { 
        padding: 14px; 
        font-size: 15px;
        border-bottom: 1px solid #e0e0e0;
    }
    .tab.active {
        border-bottom: 3px solid #667eea;
    }
    
    /* 内容区 */
    .content { 
        padding: 18px 15px; 
    }
    
    /* 表单元素 */
    .row { 
        grid-template-columns: 1fr; 
        gap: 12px; 
    }
    .form-group { 
        margin-bottom: 15px; 
    }
    label { 
        font-size: 14px; 
        margin-bottom: 6px;
    }
    textarea { 
        min-height: 180px; 
        font-size: 16px; 
        padding: 12px;
        border-radius: 10px;
        -webkit-appearance: none;
    }
    input, select { 
        font-size: 16px; 
        padding: 14px 12px;
        height: 48px;
        border-radius: 10px;
        -webkit-appearance: none;
    }
    
    /* 按钮 */
    .btn { 
        padding: 16px; 
        font-size: 16px;
        height: 52px;
        border-radius: 10px;
        font-weight: 600;
        -webkit-tap-highlight-color: transparent;
    }
    
    /* 文件上传 */
    .file-upload { 
        padding: 35px 20px; 
        border-radius: 10px;
    }
    .file-upload p {
        font-size: 14px;
    }
    
    /* 结果提示 */
    .result { 
        padding: 18px; 
        margin-top: 18px;
    }
    .result h3 {
        font-size: 16px;
    }
    .result a {
        font-size: 13px;
        word-break: break-all;
    }
    
    /* 查看页面 */
    .code-container {
        border-radius: 10px;
        overflow: hidden;
    }
    .code-header {
        padding: 12px 15px;
        flex-direction: row;
        flex-wrap: wrap;
        gap: 10px;
    }
    .code-header span {
        font-size: 13px;
    }
    .copy-btn {
        padding: 8px 14px;
        font-size: 13px;
    }
    pre code {
        font-size: 12px;
        line-height: 1.5;
        padding: 15px;
    }
    
    /* 密码页面 */
    .password-form {
        padding: 40px 20px;
    }
    .password-form input {
        max-width: 100%;
        font-size: 16px;
    }
    .password-form button {
        width: 100%;
        height: 50px;
    }
    
    /* 文件下载页 */
    .file-info {
        padding: 40px 20px;
    }
    .file-info h2 {
        font-size: 1.2em;
        word-break: break-word;
    }
    .download-btn {
        width: 100%;
        padding: 16px;
        font-size: 16px;
        text-align: center;
    }
}

/* ========== iPad 优化 ========== */
@media only screen and (min-width: 768px) and (max-width: 1024px) {
    /* iPad Air/Pro 系列 */
    body {
        padding: 30px 20px;
    }
    .container {
        max-width: 95%;
    }
    .header h1 {
        font-size: 2.5em;
    }
    
    /* 标签页横向但更大 */
    .tab {
        padding: 18px;
        font-size: 17px;
    }
    
    /* 内容区更宽松 */
    .content {
        padding: 35px;
    }
    
    /* 两列布局但间距更大 */
    .row {
        gap: 25px;
    }
    
    /* 更大的触摸区域 */
    textarea {
        min-height: 250px;
        font-size: 16px;
    }
    input, select {
        padding: 16px;
        height: 52px;
        font-size: 16px;
    }
    .btn {
        padding: 18px;
        font-size: 17px;
        height: 56px;
    }
    
    /* 代码区 */
    pre code {
        font-size: 14px;
        padding: 20px;
    }
}

/* ========== iOS Safari 特殊优化 ========== */
@supports (-webkit-touch-callout: none) {
    /* iOS 设备通用 */
    input, textarea, select {
        -webkit-appearance: none;
        border-radius: 10px;
    }
    
    /* 防止 iOS 缩放 */
    @media screen and (max-width: 430px) {
        input, select, textarea {
            font-size: 16px !important;
        }
    }
    
    /* 平滑滚动 */
    .card, pre {
        -webkit-overflow-scrolling: touch;
    }
    
    /* 禁用双击缩放 */
    * {
        touch-action: manipulation;
    }
}

/* ========== 横屏模式 ========== */
@media only screen and (max-width: 896px) and (orientation: landscape) {
    /* iPhone 横屏 */
    .header h1 {
        font-size: 1.5em;
    }
    .tabs {
        flex-direction: row;
    }
    .tab {
        padding: 12px;
        font-size: 14px;
    }
    textarea {
        min-height: 120px;
    }
}
        body { padding: 20px 10px; }
        .container { max-width: 100%; }
        .header h1 { font-size: 2em; }
        .header p { font-size: 0.9em; }
        .stats { font-size: 0.8em; padding: 8px 15px; }
        .tabs { flex-direction: column; }
        .tab { padding: 15px; font-size: 14px; }
        .content { padding: 20px 15px; }
        .row { grid-template-columns: 1fr; gap: 15px; }
        textarea { min-height: 200px; font-size: 16px; }
        input, select { font-size: 16px; padding: 15px; }
        .btn { padding: 18px; font-size: 16px; }
        .file-upload { padding: 30px 20px; }
        .header { flex-direction: column; gap: 15px; padding: 20px; }
        .lang-selector select { width: 100%; }
        pre code { font-size: 13px; }
        .code-header { flex-direction: column; gap: 10px; }
        .password-form { padding: 40px 20px; }
        .password-form input { max-width: 100%; }
    }
body{font-family:-apple-system,sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;margin:0;padding:40px 20px}
.container{max-width:900px;margin:0 auto}
.header{text-align:center;color:white;margin-bottom:40px}
.header h1{font-size:3em;margin-bottom:10px}
.card{background:white;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,0.3)}
.tabs{display:flex;border-bottom:1px solid #e0e0e0}
.tab{flex:1;padding:20px;text-align:center;cursor:pointer;background:#f8f9fa;border:none;font-size:16px}
.tab.active{background:white;color:#667eea;border-bottom:3px solid #667eea}
.content{padding:30px}
.tab-content{display:none}
.tab-content.active{display:block}
textarea{width:100%;min-height:300px;padding:15px;border:2px solid #e0e0e0;border-radius:8px;font-family:monospace}
.form-group{margin-bottom:20px}
label{display:block;margin-bottom:8px;font-weight:500}
input,select{width:100%;padding:12px;border:2px solid #e0e0e0;border-radius:8px}
.row{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.btn{background:linear-gradient(135deg,#667eea,#764ba2);color:white;border:none;padding:15px;font-size:16px;border-radius:8px;cursor:pointer;width:100%}
.file-upload{border:3px dashed #ccc;border-radius:8px;padding:40px;text-align:center;cursor:pointer}
.file-upload input{display:none}
.result{margin-top:20px;padding:20px;background:#f0f4ff;border-radius:8px;display:none}
.result.show{display:block}
.stats{background:rgba(255,255,255,0.1);padding:10px 20px;border-radius:20px;display:inline-block;margin-top:10px;color:white}
</style>
</head>
<body>
<div class="container">
<div class="header"><h1>TextDB</h1><p>安全、简洁的在线文本与文件存储</p>
<div class="stats">已存储 {{ stats.text_count }} 个文本 | {{ stats.file_count }} 个文件</div></div>
<div class="card">
<div class="tabs">
<button class="tab active" onclick="switchTab('text')">文本存储</button>
<button class="tab" onclick="switchTab('file')">文件上传</button>
</div>
<div class="content">
<div id="text-tab" class="tab-content active">
<div class="form-group"><label>文本内容</label><textarea id="content" placeholder="在此输入文本内容..."></textarea></div>
<div class="row">
<div class="form-group"><label>自定义链接（可选）</label><input type="text" id="text-key" placeholder="留空自动生成"></div>
<div class="form-group"><label>访问密码（可选）</label><input type="password" id="text-password" placeholder="不设密码直接访问"></div>
</div>
<div class="form-group"><label>过期时间</label><select id="text-expires"><option value="">永不过期</option><option value="1h">1小时</option><option value="1d">1天</option><option value="7d">7天</option><option value="30d">30天</option></select></div>
<button class="btn" onclick="submitText()">保存文本</button>
</div>
<div id="file-tab" class="tab-content">
<div class="form-group"><label>选择文件</label><div class="file-upload" onclick="document.getElementById('file-input').click()"><input type="file" id="file-input" onchange="updateFileName()"><p id="file-name">点击选择文件（支持任意类型）</p></div></div>
<div class="row">
<div class="form-group"><label>自定义链接（可选）</label><input type="text" id="file-key" placeholder="留空自动生成"></div>
<div class="form-group"><label>访问密码（可选）</label><input type="password" id="file-password" placeholder="不设密码直接访问"></div>
</div>
<div class="form-group"><label>过期时间</label><select id="file-expires"><option value="">永不过期</option><option value="1h">1小时</option><option value="1d">1天</option><option value="7d">7天</option><option value="30d">30天</option></select></div>
<button class="btn" onclick="submitFile()">上传文件</button>
</div>
<div id="result" class="result"><h3>✅ 保存成功！</h3><p>访问链接：<a id="result-url" href="#" target="_blank"></a></p><p id="result-password"></p><div id="qr-section" style="margin-top:20px;text-align:center;display:none;"><p style="margin-bottom:10px;">📱 手机扫码访问</p><img id="qr-img" style="max-width:200px;border-radius:8px;box-shadow:0 4px 12px rgba(0,0,0,0.15);" src="" alt="二维码"><p style="font-size:12px;color:#666;margin-top:8px;">长按识别二维码</p></div></div>
</div></div></div>
<script>
function switchTab(tab){document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));document.querySelectorAll('.tab-content').forEach(t=>t.classList.remove('active'));event.target.classList.add('active');document.getElementById(tab+'-tab').classList.add('active');document.getElementById('result').classList.remove('show')}
function updateFileName(){const input=document.getElementById('file-input');const name=document.getElementById('file-name');if(input.files.length>0)name.textContent=input.files[0].name}
function submitText(){const content=document.getElementById('content').value;if(!content.trim()){alert('请输入文本内容');return}fetch('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({content:content,key:document.getElementById('text-key').value,password:document.getElementById('text-password').value,expires:document.getElementById('text-expires').value})}).then(r=>r.json()).then(data=>{if(data.success)showResult(data.url,data.has_password,data.qr_code);else alert(data.error||'保存失败')})}
function submitFile(){const input=document.getElementById('file-input');if(input.files.length===0){alert('请选择文件');return}const formData=new FormData();formData.append('file',input.files[0]);formData.append('key',document.getElementById('file-key').value);formData.append('password',document.getElementById('file-password').value);formData.append('expires',document.getElementById('file-expires').value);fetch('/api/upload',{method:'POST',body:formData}).then(r=>r.json()).then(data=>{if(data.success)showResult(data.url,data.has_password,data.qr_code);else alert(data.error||'上传失败')})}
function showResult(url,hasPassword,qrCode){document.getElementById('result-url').textContent=url;document.getElementById('result-url').href=url;document.getElementById('result-password').textContent=hasPassword?'🔒 已设置密码，访问时需要输入密码':'';if(qrCode){document.getElementById('qr-img').src=qrCode;document.getElementById('qr-section').style.display='block'}else{document.getElementById('qr-section').style.display='none'}document.getElementById('result').classList.add('show')}
</script>
</body></html>"""

# 带代码高亮的查看模板
VIEW_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<title>{{ title }} - TextDB</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/python.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/javascript.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/bash.min.js"></script>
<style>
    /* 手机端适配 */
    @media (max-width: 768px) {
/* ========== iPhone 优化 ========== */
@media only screen and (max-width: 430px) {
/* ========== 基础样式（移动优先） ========== */
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    min-height: 100vh;
    color: #333;
    line-height: 1.6;
}

.container {
    width: 100%;
    max-width: 100%;
    margin: 0 auto;
    padding: 15px 12px;
}

/* 超小屏手机（iPhone SE/mini 等） */
@media only screen and (max-width: 375px) {
    .container { padding: 12px 10px; }
    .header h1 { font-size: 1.6em; }
    .header p { font-size: 0.8em; }
    .tab { padding: 12px; font-size: 13px; }
    .content { padding: 15px 12px; }
    textarea { min-height: 150px; font-size: 15px; }
    .btn { padding: 14px; font-size: 15px; height: 48px; }
}

/* 小屏手机（iPhone 12/13/14/15/16/17 标准版） */
@media only screen and (min-width: 376px) and (max-width: 430px) {
    .container { padding: 15px 12px; }
    .header h1 { font-size: 1.8em; }
    .header p { font-size: 0.85em; }
    .tab { padding: 14px; font-size: 14px; }
    .content { padding: 18px 15px; }
    textarea { min-height: 180px; font-size: 16px; }
    .btn { padding: 16px; font-size: 16px; height: 52px; }
}

/* 大屏手机（iPhone Pro Max / Android 大屏） */
@media only screen and (min-width: 431px) and (max-width: 767px) {
    .container { padding: 20px 15px; }
    .header h1 { font-size: 2em; }
    .header p { font-size: 0.9em; }
    .row { grid-template-columns: 1fr 1fr; gap: 15px; }
    .tab { padding: 16px; font-size: 15px; }
    .content { padding: 25px 20px; }
}

/* 平板竖屏（iPad mini, iPad Air 竖屏） */
@media only screen and (min-width: 768px) and (max-width: 1024px) and (orientation: portrait) {
    .container { max-width: 90%; padding: 30px 20px; }
    .header h1 { font-size: 2.2em; }
    .row { grid-template-columns: 1fr 1fr; gap: 25px; }
    .tab { padding: 18px; font-size: 16px; }
    .content { padding: 35px 30px; }
    textarea { min-height: 280px; }
}

/* 平板横屏（iPad 横屏） */
@media only screen and (min-width: 768px) and (max-width: 1024px) and (orientation: landscape) {
    .container { max-width: 85%; padding: 25px 20px; }
    .header h1 { font-size: 2em; }
    .row { grid-template-columns: 1fr 1fr; gap: 20px; }
    .content { padding: 30px; }
}

/* 小桌面（笔记本 13-15寸） */
@media only screen and (min-width: 1025px) and (max-width: 1440px) {
    .container { max-width: 900px; padding: 40px 30px; }
    .header h1 { font-size: 2.5em; }
    .row { grid-template-columns: 1fr 1fr; gap: 25px; }
    .content { padding: 40px; }
}

/* 大桌面（外接显示器 24寸+） */
@media only screen and (min-width: 1441px) {
    .container { max-width: 1000px; padding: 50px 40px; }
    .header h1 { font-size: 3em; }
    .header p { font-size: 1.1em; }
    .card { box-shadow: 0 25px 80px rgba(0,0,0,0.35); }
    .row { grid-template-columns: 1fr 1fr; gap: 30px; }
    .content { padding: 45px; }
    textarea { min-height: 350px; font-size: 15px; }
}

/* 超宽屏（带鱼屏 21:9） */
@media only screen and (min-width: 1920px) {
    .container { max-width: 1200px; }
    .header h1 { font-size: 3.5em; }
}

/* ========== 特殊设备适配 ========== */

/* 折叠屏手机展开 */
@media only screen and (min-width: 700px) and (max-width: 900px) and (min-height: 1000px) {
    .container { max-width: 95%; }
    .row { grid-template-columns: 1fr 1fr; }
}

/* 横屏手机 */
@media only screen and (max-height: 500px) and (orientation: landscape) {
    .header { margin-bottom: 20px; }
    .header h1 { font-size: 1.5em; }
    textarea { min-height: 100px; }
    .tabs { flex-direction: row; }
    .tab { padding: 10px 15px; font-size: 13px; }
}

/* ========== iOS 特殊优化 ========== */
@supports (-webkit-touch-callout: none) {
    @media screen and (max-width: 430px) {
        input, select, textarea {
            font-size: 16px !important;
            -webkit-appearance: none;
            border-radius: 10px;
        }
        .btn {
            -webkit-tap-highlight-color: transparent;
        }
    }
}

/* ========== Android 优化 ========== */
@media screen and (-webkit-min-device-pixel-ratio: 2) and (max-width: 430px) {
    .btn, input, select, textarea {
        transform: translateZ(0);
    }
}

/* ========== 打印样式 ========== */
@media print {
    body {
        background: white !important;
        -webkit-print-color-adjust: exact;
    }
    .card {
        box-shadow: none;
        border: 1px solid #ddd;
    }
    .header {
        background: #667eea !important;
        -webkit-print-color-adjust: exact;
    }
    .tabs, .btn, .file-upload {
        display: none;
    }
    .content {
        padding: 20px;
    }
}

/* ========== 深色模式（系统级） ========== */
@media (prefers-color-scheme: dark) {
    @media only screen and (min-width: 1025px) {
        /* 桌面端深色模式 */
    }
}

/* ========== 减少动画（无障碍） ========== */
@media (prefers-reduced-motion: reduce) {
    * {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }
}

/* ========== 高对比度模式 ========== */
@media (prefers-contrast: high) {
    .btn, .tab.active {
        border: 2px solid currentColor;
    }
}
    /* iPhone 14/15/16/17 Pro Max 系列 */
    body { 
        padding: 15px 12px; 
        -webkit-text-size-adjust: 100%;
    }
    .container { 
        max-width: 100%; 
        padding: 0;
    }
    .header { 
        margin-bottom: 25px; 
        padding: 0 5px;
    }
    .header h1 { 
        font-size: 1.8em; 
        margin-bottom: 8px;
    }
    .header p { 
        font-size: 0.85em; 
        line-height: 1.4;
    }
    .stats { 
        font-size: 0.75em; 
        padding: 6px 12px;
        margin-top: 8px;
    }
    
    /* 卡片优化 */
    .card { 
        border-radius: 12px; 
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
    
    /* 标签页 */
    .tabs { 
        flex-direction: column;
    }
    .tab { 
        padding: 14px; 
        font-size: 15px;
        border-bottom: 1px solid #e0e0e0;
    }
    .tab.active {
        border-bottom: 3px solid #667eea;
    }
    
    /* 内容区 */
    .content { 
        padding: 18px 15px; 
    }
    
    /* 表单元素 */
    .row { 
        grid-template-columns: 1fr; 
        gap: 12px; 
    }
    .form-group { 
        margin-bottom: 15px; 
    }
    label { 
        font-size: 14px; 
        margin-bottom: 6px;
    }
    textarea { 
        min-height: 180px; 
        font-size: 16px; 
        padding: 12px;
        border-radius: 10px;
        -webkit-appearance: none;
    }
    input, select { 
        font-size: 16px; 
        padding: 14px 12px;
        height: 48px;
        border-radius: 10px;
        -webkit-appearance: none;
    }
    
    /* 按钮 */
    .btn { 
        padding: 16px; 
        font-size: 16px;
        height: 52px;
        border-radius: 10px;
        font-weight: 600;
        -webkit-tap-highlight-color: transparent;
    }
    
    /* 文件上传 */
    .file-upload { 
        padding: 35px 20px; 
        border-radius: 10px;
    }
    .file-upload p {
        font-size: 14px;
    }
    
    /* 结果提示 */
    .result { 
        padding: 18px; 
        margin-top: 18px;
    }
    .result h3 {
        font-size: 16px;
    }
    .result a {
        font-size: 13px;
        word-break: break-all;
    }
    
    /* 查看页面 */
    .code-container {
        border-radius: 10px;
        overflow: hidden;
    }
    .code-header {
        padding: 12px 15px;
        flex-direction: row;
        flex-wrap: wrap;
        gap: 10px;
    }
    .code-header span {
        font-size: 13px;
    }
    .copy-btn {
        padding: 8px 14px;
        font-size: 13px;
    }
    pre code {
        font-size: 12px;
        line-height: 1.5;
        padding: 15px;
    }
    
    /* 密码页面 */
    .password-form {
        padding: 40px 20px;
    }
    .password-form input {
        max-width: 100%;
        font-size: 16px;
    }
    .password-form button {
        width: 100%;
        height: 50px;
    }
    
    /* 文件下载页 */
    .file-info {
        padding: 40px 20px;
    }
    .file-info h2 {
        font-size: 1.2em;
        word-break: break-word;
    }
    .download-btn {
        width: 100%;
        padding: 16px;
        font-size: 16px;
        text-align: center;
    }
}

/* ========== iPad 优化 ========== */
@media only screen and (min-width: 768px) and (max-width: 1024px) {
    /* iPad Air/Pro 系列 */
    body {
        padding: 30px 20px;
    }
    .container {
        max-width: 95%;
    }
    .header h1 {
        font-size: 2.5em;
    }
    
    /* 标签页横向但更大 */
    .tab {
        padding: 18px;
        font-size: 17px;
    }
    
    /* 内容区更宽松 */
    .content {
        padding: 35px;
    }
    
    /* 两列布局但间距更大 */
    .row {
        gap: 25px;
    }
    
    /* 更大的触摸区域 */
    textarea {
        min-height: 250px;
        font-size: 16px;
    }
    input, select {
        padding: 16px;
        height: 52px;
        font-size: 16px;
    }
    .btn {
        padding: 18px;
        font-size: 17px;
        height: 56px;
    }
    
    /* 代码区 */
    pre code {
        font-size: 14px;
        padding: 20px;
    }
}

/* ========== iOS Safari 特殊优化 ========== */
@supports (-webkit-touch-callout: none) {
    /* iOS 设备通用 */
    input, textarea, select {
        -webkit-appearance: none;
        border-radius: 10px;
    }
    
    /* 防止 iOS 缩放 */
    @media screen and (max-width: 430px) {
        input, select, textarea {
            font-size: 16px !important;
        }
    }
    
    /* 平滑滚动 */
    .card, pre {
        -webkit-overflow-scrolling: touch;
    }
    
    /* 禁用双击缩放 */
    * {
        touch-action: manipulation;
    }
}

/* ========== 横屏模式 ========== */
@media only screen and (max-width: 896px) and (orientation: landscape) {
    /* iPhone 横屏 */
    .header h1 {
        font-size: 1.5em;
    }
    .tabs {
        flex-direction: row;
    }
    .tab {
        padding: 12px;
        font-size: 14px;
    }
    textarea {
        min-height: 120px;
    }
}
        body { padding: 20px 10px; }
        .container { max-width: 100%; }
        .header h1 { font-size: 2em; }
        .header p { font-size: 0.9em; }
        .stats { font-size: 0.8em; padding: 8px 15px; }
        .tabs { flex-direction: column; }
        .tab { padding: 15px; font-size: 14px; }
        .content { padding: 20px 15px; }
        .row { grid-template-columns: 1fr; gap: 15px; }
        textarea { min-height: 200px; font-size: 16px; }
        input, select { font-size: 16px; padding: 15px; }
        .btn { padding: 18px; font-size: 16px; }
        .file-upload { padding: 30px 20px; }
        .header { flex-direction: column; gap: 15px; padding: 20px; }
        .lang-selector select { width: 100%; }
        pre code { font-size: 13px; }
        .code-header { flex-direction: column; gap: 10px; }
        .password-form { padding: 40px 20px; }
        .password-form input { max-width: 100%; }
    }
body{font-family:-apple-system,sans-serif;background:linear-gradient(135deg,#667eea,#764ba2);min-height:100vh;margin:0;padding:40px 20px}
.container{max-width:1000px;margin:0 auto}
.card{background:white;border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,0.3);overflow:hidden}
.header{background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:30px;display:flex;justify-content:space-between;align-items:center}
.header h1{margin:0;font-size:1.5em}
.lang-selector select{padding:8px 15px;border-radius:6px;border:none;font-size:14px}
.content{padding:0}
.password-form{text-align:center;padding:60px 40px}
.password-form input{width:100%;max-width:300px;padding:15px;border:2px solid #e0e0e0;border-radius:8px;font-size:16px;margin-bottom:20px}
.password-form button{background:linear-gradient(135deg,#667eea,#764ba2);color:white;border:none;padding:15px 40px;font-size:16px;border-radius:8px;cursor:pointer}
.code-container{position:relative}
.code-header{background:#2d2d2d;color:#fff;padding:10px 20px;display:flex;justify-content:space-between;align-items:center;font-size:14px}
.copy-btn{background:#444;color:#fff;border:none;padding:5px 15px;border-radius:4px;cursor:pointer;font-size:12px}
.copy-btn:hover{background:#555}
pre{margin:0;border-radius:0}
pre code{font-family:'Fira Code',monospace;font-size:14px;line-height:1.6}
.file-info{text-align:center;padding:60px 40px}
.download-btn{display:inline-block;background:linear-gradient(135deg,#667eea,#764ba2);color:white;text-decoration:none;padding:15px 40px;border-radius:8px;margin-top:20px}
.error{text-align:center;padding:60px;color:#666}
</style>
</head>
<body>
<div class="container">
<div class="card">
{% if need_password %}
<div class="header"><h1>🔒 需要密码</h1></div>
<div class="content">
<form class="password-form" method="POST">
<p>此内容已设置密码保护</p>
<input type="password" name="password" placeholder="请输入访问密码" required><br>
<button type="submit">🔓 解锁</button>
{% if error %}<p style="color:#e74c3c;margin-top:20px;">{{ error }}</p>{% endif %}
</form>
</div>
{% elif expired %}
<div class="error"><h1>⏰ 内容已过期</h1><p>此内容已达到设定的过期时间</p></div>
{% elif not_found %}
<div class="error"><h1>❓ 内容不存在</h1><p>您访问的内容不存在或已被删除</p></div>
{% else %}
<div class="header">
<h1>{{ title }}</h1>
{% if is_text %}
<div class="lang-selector">
<select id="langSelect" onchange="changeLang()">
<option value="auto">🔍 自动检测</option>
<option value="python">🐍 Python</option>
<option value="javascript">📜 JavaScript</option>
<option value="bash">💻 Bash</option>
<option value="json">📋 JSON</option>
<option value="html">🌐 HTML</option>
<option value="css">🎨 CSS</option>
<option value="sql">🗄️ SQL</option>
<option value="plaintext">📝 纯文本</option>
</select>
</div>
{% endif %}
</div>
<div class="content">
{% if is_text %}
<div class="code-container">
<div class="code-header">
<span id="langLabel">代码</span>
<button class="copy-btn" onclick="copyCode()">📋 复制</button>
</div>
<pre><code id="codeBlock">{{ content | safe }}</code></pre>
</div>
{% else %}
<div class="file-info">
<h2>📁 {{ filename }}</h2>
<p>文件大小: {{ file_size }}</p>
<a href="/d/{{ key }}" class="download-btn">⬇️ 下载文件</a>
</div>
{% endif %}
</div>
{% endif %}
</div>
</div>
<script>
function detectLanguage(code){
if(/import\s+\w+|from\s+\w+\s+import|def\s+\w+\s*\(|class\s+\w+/.test(code))return'python';
if(/function\s+\w+|const\s+\w+|console\./.test(code))return'javascript';
if(/#\!\/bin\/bash|echo\s|cd\s/.test(code))return'bash';
if(/"\w+":\s*"/.test(code))return'json';
if(/<!DOCTYPE|<html|<div/.test(code))return'html';
if(/SELECT\s+|INSERT\s+|UPDATE\s+/i.test(code))return'sql';
return'plaintext'}
function highlightCode(){
const codeBlock=document.getElementById('codeBlock');
const langSelect=document.getElementById('langSelect');
const langLabel=document.getElementById('langLabel');
if(!codeBlock)return;
let lang=langSelect.value;
if(lang==='auto'){lang=detectLanguage(codeBlock.textContent);langSelect.value=lang}
codeBlock.className=lang==='plaintext'?'':'language-'+lang;
langLabel.textContent=langSelect.options[langSelect.selectedIndex].text.split(' ')[1];
if(lang!=='plaintext')hljs.highlightElement(codeBlock)}
function changeLang(){
const codeBlock=document.getElementById('codeBlock');
codeBlock.textContent=codeBlock.textContent;
highlightCode()}
function copyCode(){
const code=document.getElementById('codeBlock').textContent;
if(navigator.clipboard&&navigator.clipboard.writeText){
navigator.clipboard.writeText(code).then(()=>{
const btn=document.querySelector('.copy-btn');
btn.textContent='✅ 已复制';
setTimeout(()=>btn.textContent='📋 复制',2000);
}).catch(()=>copyFallback(code));
}else{
copyFallback(code);
}}
function copyFallback(text){
const textarea=document.createElement('textarea');
textarea.value=text;
textarea.style.position='fixed';
textarea.style.opacity='0';
document.body.appendChild(textarea);
textarea.select();
try{
document.execCommand('copy');
const btn=document.querySelector('.copy-btn');
btn.textContent='✅ 已复制';
setTimeout(()=>btn.textContent='📋 复制',2000);
}catch(err){
alert('复制失败，请手动选择复制');
}
document.body.removeChild(textarea);
}
document.addEventListener('DOMContentLoaded',highlightCode);
</script>
</body></html>"""

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

@app.route('/api/save', methods=['POST'])
def save_text():
    data = request.get_json()
    content = data.get('content', '').strip()
    key = data.get('key', '').strip()
    password = data.get('password', '')
    expires = data.get('expires', '')
    if not content:
        return jsonify({'success': False, 'error': '内容不能为空'})
    if not key:
        key = generate_key()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM items WHERE key=?", (key,))
    if c.fetchone():
        conn.close()
        return jsonify({'success': False, 'error': '该链接已被使用'})
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
    if item_type == 'text':
        return render_template_string(VIEW_TEMPLATE, title=key, is_text=True, content=row[3])
    else:
        file_size = os.path.getsize(row[5])
        size_str = f"{file_size/1024/1024:.2f} MB" if file_size > 1024*1024 else f"{file_size/1024:.2f} KB"
        return render_template_string(VIEW_TEMPLATE, title=key, is_text=False, filename=row[4], file_size=size_str, key=key)

@app.route('/d/<key>')
def download_file(key):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM items WHERE key=? AND type='file'", (key,))
    row = c.fetchone()
    conn.close()
    if not row or not os.path.exists(row[5]):
        abort(404)
    if row[7] and datetime.now() > datetime.fromisoformat(row[7]):
        abort(410)
    return send_file(row[5], as_attachment=True, download_name=row[4])

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=80, debug=False)
