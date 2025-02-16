# Lanzou-cli

一个简单易用的蓝奏云命令行工具，提供类 Unix 风格的文件管理体验。

## 功能特点

- 支持文件上传和管理
- 支持目录创建和导航
- 命令行界面，操作便捷
- 类 Ubuntu 的命令风格
- 支持登录状态保存

## 安装使用

1. 克隆仓库：

    ```bash
    git clone https://github.com/your_username/your_repo.git
    cd your_repo
    ```

2. 安装依赖：

    ```bash
    pip install -r requirements.txt
    ```

3. 配置账号：

    ```bash
    cp config.example.py config.py
    # 编辑 config.py，填入你的蓝奏云账号、密码和 蓝奏云UID（可从浏览器开发者工具中获取）
    ```

4. 运行程序：

    ```bash
    python lanzou_web.py
    ```

## 可用命令

- `pwd` - 显示当前目录
- `ls` - 列出目录内容
- `cd <目录名>` - 进入目录
- `cd ..` - 返回上级目录
- `mkdir <目录名>` - 创建目录
- `rmdir <目录名>` - 删除目录
- `upload <文件路径>` - 上传文件
- `rm <文件名>` - 删除文件
- `help` - 显示帮助信息
- `exit` - 退出程序

## 注意事项

1. 首次使用需要配置账号密码
2. 上传文件大小限制为 100MB（免费用户）
3. 程序会自动保存登录状态到 cookie.json

## 致谢

本项目参考了 [AList](https://github.com/alist-org/alist) 的蓝奏云存储实现。
