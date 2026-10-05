# 本地 AI

双击 `一键部署本地AI.exe`，或在网站右上角打开“本地 AI”并点击“自动识别并启动”。

部署不需要 Python、LM Studio、显卡或管理员权限，使用官方 llama.cpp Windows x64 CPU 便携运行时和官方 Qwen2.5 1.5B Instruct Q4_K_M 模型。

完整资源包内置约 1.12 GB 模型与 CPU 运行时，首次部署可离线完成；请预留至少 4 GB 空闲磁盘，建议 8 GB 或更多内存。资源缺失或损坏时才需要联网重新下载。

运行时保存在 `local-ai/runtime`，模型保存在 `local-ai/models`；官方元数据和 SHA256 验证结果保存在 `local-ai/verified-install.json`。

下载进度与错误显示在部署窗口及网站面板，同时记录在 `自动部署/logs/ai-state.json`；下载失败可以重新点击，最多尝试三次，其中一次尝试本机 `127.0.0.1:7897` 代理。

下载完成后脚本验证 SHA256、加载模型、检查健康端点并发起实际聊天请求，全部成功后才报告就绪；文件留在本地后可断网重启使用。

本地服务只监听回环地址，默认端口为 `18090`，占用时自动选择其他可用端口并写入 `local-ai/server.json`。网站也会识别已有 `127.0.0.1:1234` 的 LM Studio 模型；历史资料不发送给远程推理接口。

开发机器已完成实际模型加载与事件问答测试，模型字节与官方 SHA256 一致。目标电脑速度取决于 CPU 和内存；中文朗读使用目标系统已安装的中文语音。

来源：[llama.cpp](https://github.com/ggml-org/llama.cpp/releases)、[官方 Qwen 模型](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF)。
