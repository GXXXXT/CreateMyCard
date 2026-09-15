本地真实模型验证
================

在 widget_service 目录运行：

```powershell
.venv/Scripts/python.exe tools/run_local_model_server.py
```

启动器读取现有 `.env` 中的 WIDGET_SERVICE_* 配置，强制关闭模型模拟、开启模板检索。
使用已有 HTTPS 模型客户端，通过运行时工厂注入服务器；不改部署默认配置，不在代码中保存密钥。
缺少真实模型地址、模型名或密钥时启动失败，不回退到模型模拟。
数据查询仍沿用 `.env` 的 IDS 配置；当前本地验证使用示例数据，模型请求是真实请求。

端侧“Compact DSL 卡片批量用例”页面点击“Q053 / Q059 模型验证（仅两条）”。
该入口通过 WebSocket 发送原始输入，再下载服务器刚生成的产物进行渲染，不读取模板画廊结果。
服务器同时在 `/api/v1/artifacts` 提供本地生成文件；`.env` 的 ARTIFACT_BASE_URL 应指向此路径。
设备通过 HDC 将 tcp:8855 转发到电脑后，可使用默认的 127.0.0.1:8855 地址。

检索核对：服务日志中的 template_retrieval、selected_templates_generated 可确认走了模板路径。
Q053 应为完整双耳 WideFull，Q059 应为 MusicFull 与两个 CompactAction。
实际模板选择不预设、不注入给模型；输入缺字段、模型选错或编译失败会按正式链路处理并显示错误。
