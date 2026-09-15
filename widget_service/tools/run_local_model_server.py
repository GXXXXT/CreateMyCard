"""用已有 .env 启动本地真实模型验证服务，不修改部署配置。"""

import argparse
import sys
from pathlib import Path

from dotenv import dotenv_values


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--env-file', type=Path, default=Path(__file__).resolve().parents[1] / '.env',
    )
    options = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    values = dotenv_values(options.env_file)
    overrides = {}
    for key, value in values.items():
        if key.startswith('WIDGET_SERVICE_') and value is not None:
            overrides[key.removeprefix('WIDGET_SERVICE_').lower()] = value
    for key in ('deepseek_api_key', 'deepseek_api_url', 'deepseek_http_model'):
        if not overrides.get(key):
            raise ValueError(f'本地真实模型配置缺少 {key}')
    overrides.update({
        'enable_a2ui_model_mock': 'false', 'enable_card_template': 'true',
        'enable_openai_fallback': 'false', 'openai_master_client': 'deepseek_platform',
        'enable_sensitive_log_fields': 'false', 'ai_widget_data_huashan_enable': 'false',
    })
    sys.path.insert(0, str(root / 'cloud'))
    from config.config_helper import ConfigHelper
    original = ConfigHelper._read_config

    def read_config(self, path):
        config = original(self, path)
        config.update(overrides)
        return config

    ConfigHelper._read_config = read_config
    from config import config as settings_module
    configured = {}
    for key, value in overrides.items():
        if key in settings_module.Settings.model_fields:
            configured[key] = value
    base = settings_module.Settings(**configured)
    settings = base.model_copy(update={
        'deepseek_api_url': overrides.get('deepseek_api_url'),
        'deepseek_http_model': overrides.get('deepseek_http_model'),
        'deepseek_http_max_tokens': int(overrides.get('deepseek_http_max_tokens', '8192')),
    })
    settings_module.get_settings = lambda: settings
    import uvicorn
    from fastapi.staticfiles import StaticFiles

    from custom.deepseek_http_client import DeepSeekHttpClient
    from custom.model_runtime import ModelExecutionRuntime
    from start_websocket_server import create_app

    def runtime():
        return ModelExecutionRuntime(
            settings, deepseek_platform_transport=DeepSeekHttpClient(settings),
        )

    print('本地真实模型模式：模型模拟关闭，模板检索开启，使用 .env 中的 HTTPS 模型。', flush=True)
    app = create_app(model_runtime_factory=runtime)
    artifact_dir = settings.WORKSPACE_ROOT / 'mock_obs'
    artifact_dir.mkdir(parents=True, exist_ok=True)
    app.mount('/api/v1/artifacts', StaticFiles(directory=artifact_dir), name='local-artifacts')
    uvicorn.run(app, host=settings.server_host, port=settings.server_port)


if __name__ == '__main__':
    main()
