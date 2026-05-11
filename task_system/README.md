# 在线任务提交系统

一个轻量级的在线任务提交与审核系统，教师发布任务，学生在线提交，教师审核反馈。

## 功能

- **教师端**
  - 创建、编辑、关闭/开放、删除任务
  - 设置任务截止日期
  - 查看所有学生提交
  - 对提交进行审核（通过 / 需修改）并给出评语
  - 修改登录密码

- **学生端**
  - 查看所有开放任务
  - 提交文字内容或上传文件（支持多种格式，最大 50MB）
  - 查看自己的提交记录和教师评审结果

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

```bash
python3 app.py
```

服务默认运行在 `http://localhost:5000`。

### 3. 登录使用

- **教师默认账号**: `teacher` / `admin123`（首次使用后请修改密码）
- **学生入口**: 输入姓名即可

## 技术栈

- **后端**: Python / Flask
- **数据库**: SQLite（无需额外安装）
- **前端**: 原生 HTML/CSS，响应式设计，支持移动端

## 文件结构

```
task_system/
├── app.py              # Flask 应用主程序
├── requirements.txt    # Python 依赖
├── tasks.db            # SQLite 数据库（自动创建）
├── uploads/            # 上传文件存储目录
├── static/
│   └── style.css       # 样式表
└── templates/
    ├── base.html               # 基础模板
    ├── index.html              # 首页
    ├── login.html              # 教师登录
    ├── student_login.html      # 学生入口
    ├── teacher_dashboard.html  # 教师任务管理
    ├── create_task.html        # 创建任务
    ├── view_submissions.html   # 查看提交（教师）
    ├── teacher_settings.html   # 修改密码
    ├── student_tasks.html      # 任务列表（学生）
    ├── submit_task.html        # 提交任务
    └── my_submissions.html     # 我的提交记录
```

## 部署建议

生产环境中建议：

1. 修改 `app.py` 中的 `SECRET_KEY` 或通过环境变量 `SECRET_KEY` 设置
2. 使用 Gunicorn 等 WSGI 服务器运行：
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:5000 app:app
   ```
3. 首次登录后修改默认教师密码
