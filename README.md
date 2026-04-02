# TextDB - 在线文本与文件存储平台

一个安全、简洁、支持多端访问的在线文本与文件存储服务，类似 textdb.online 和 webnote.cc。

## ✨ 功能特性

### 核心功能
- 📝 **文本存储** - 支持任意文本内容，代码自动语法高亮
- 📁 **文件上传** - 支持任意类型文件上传和下载
- 🔒 **密码保护** - 可选设置访问密码
- ⏰ **过期时间** - 支持 1小时/1天/7天/30天/永不过期
- 📱 **二维码分享** - 自动生成二维码，手机扫码访问

### 代码高亮
- 🔍 自动检测语言（Python/JavaScript/Bash/JSON/HTML/CSS/SQL）
- 🎨 支持手动切换语言
- 📋 一键复制代码
- 🌙 GitHub Dark 主题

### 多端适配
- 📱 iPhone（SE/mini/标准版/Pro/Pro Max）
- 📱 Android 手机（小屏/大屏）
- 📱 折叠屏设备
- 📱 横屏/竖屏自动适配
- 💻 iPad（竖屏/横屏）
- 💻 笔记本（13-15寸）
- 🖥️ 桌面显示器（24寸+）
- 🖥️ 超宽屏（带鱼屏 21:9）

## 🚀 快速开始

### 安装依赖
```bash
pip3 install flask qrcode[pil]
```

### 启动服务
```bash
# 直接运行
python3 app.py

# 或使用 PM2 守护进程
pm2 start app.py --name textdb --interpreter python3
pm2 save
```

### 访问地址
```
http://localhost:80
```

## 📡 API 接口

### 保存文本
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"content":"文本内容","key":"自定义链接","password":"密码","expires":"7d"}' \
  http://localhost/api/save
```

### 上传文件
```bash
curl -X POST -F "file=@document.pdf" \
  -F "key=自定义链接" -F "password=密码" -F "expires=30d" \
  http://localhost/api/upload
```

### 响应格式
```json
{
  "success": true,
  "key": "custom-key",
  "url": "http://localhost/custom-key",
  "has_password": true,
  "qr_code": "data:image/png;base64,..."
}
```

## 📁 项目结构

```
textdb/
├── app.py              # 主程序（Flask）
├── server.py           # 简化版 HTTP 服务
├── data/               # 数据存储
│   ├── textdb.db       # SQLite 数据库
│   └── uploads/        # 上传文件存储
├── responsive.css      # 响应式样式
├── ios.css            # iOS 设备优化
├── mobile.css         # 移动端样式
└── README.md          # 项目说明
```

## 🔧 配置说明

### 环境变量
```bash
# 可选：修改端口（默认 80）
export PORT=8080
```

### 数据库
- 类型：SQLite
- 路径：`data/textdb.db`
- 自动创建表结构

### 文件存储
- 上传路径：`data/uploads/`
- 文件重命名存储（防冲突）
- 原文件名保存在数据库

## 🛡️ 安全特性

- ✅ 密码 SHA256 哈希存储
- ✅ 可选过期时间自动清理
- ✅ 访问次数统计
- ✅ 缓存控制（防缓存泄露）

## 📱 浏览器兼容性

- ✅ Safari (iOS/macOS)
- ✅ Chrome (Android/Desktop)
- ✅ Firefox
- ✅ Edge
- ✅ 微信内置浏览器

## 📝 更新日志

### v1.0.0 (2026-04-02)
- ✨ 初始版本发布
- ✨ 支持文本/文件存储
- ✨ 密码保护功能
- ✨ 二维码分享
- ✨ 代码语法高亮
- ✨ 完整多端适配

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

---

**在线演示**: http://150.158.96.110/