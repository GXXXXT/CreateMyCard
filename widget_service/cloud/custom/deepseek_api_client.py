# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""OpenAI 兼容 HTTP 模型客户端，用于本地直连 DeepSeek 服务。"""

import time
from typing import Any

import httpx

from app.logger import json_for_log, logger
from config.config import Settings
from custom.model_transport import ModelTransportError
from models.generation import ModelRequestContext

_MODULE = "[DeepSeek API]"


class DeepSeekAPIClient:
    """通过 OpenAI 兼容 chat/completions 接口生成完整模型文本。"""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self._owns_http_client = http_client is None
        self.http_client = http_client or httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=settings.model_max_concurrency,
                max_keepalive_connections=settings.model_max_concurrency,
            ),
            timeout=settings.model_request_timeout_seconds,
            trust_env=False,
        )

    async def aclose(self) -> None:
        """关闭当前客户端自行创建的连接池。"""
        if self._owns_http_client:
            await self.http_client.aclose()

    async def generate(
        self,
        messages: list[dict[str, str]],
        request_context: ModelRequestContext | None = None,
    ) -> str:
        """发送一次非流式 chat 请求并返回回复文本。"""
        del request_context
        self._validate_configuration()
        body = self._build_body(messages)
        started_at = time.perf_counter()
        try:
            response = await self.http_client.post(
                self._chat_completions_url(),
                json=body,
                headers=self._build_headers(),
            )
            response.raise_for_status()
            data = response.json()
        except httpx.TimeoutException as exc:
            logger.error(
                f"{_MODULE} request_timeout "
                f"timeout_seconds={self.settings.model_request_timeout_seconds} "
                f"exception={exc!r}"
            )
            raise ModelTransportError(
                "DeepSeek API request timed out",
                code="MODEL_REQUEST_TIMEOUT",
            ) from exc
        except httpx.ConnectError as exc:
            logger.error(f"{_MODULE} connection_error exception={exc!r}")
            raise ModelTransportError("DeepSeek API connection failed") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            logger.error(
                f"{_MODULE} http_error status_code={status} "
                f"response_preview={json_for_log(exc.response.text[:500])}"
            )
            raise ModelTransportError(
                f"DeepSeek API HTTP request failed: {status}",
                code=f"HTTP_{status}",
            ) from exc
        except Exception as exc:
            logger.error(
                f"{_MODULE} request_failed exception_type={type(exc).__name__} exception={exc!r}"
            )
            raise ModelTransportError("DeepSeek API request failed") from exc

        content = self._extract_content(data)
        self._log_response(started_at, body, data, content)
        return content

    def _validate_configuration(self) -> None:
        if not self.settings.deepseek_api_auth_key.strip():
            raise ModelTransportError(
                "DeepSeek API auth key is not configured; "
                "set deepseek_api_auth_key in config or the "
                "DEEPSEEK_API_AUTH_KEY environment variable"
            )
        if not self.settings.deepseek_api_base_url.strip():
            raise ModelTransportError("DeepSeek API base URL is not configured")

    def _chat_completions_url(self) -> str:
        return f"{self.settings.deepseek_api_base_url.rstrip('/')}/chat/completions"

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.deepseek_api_auth_key}",
            "Content-Type": "application/json",
        }

    def _build_body(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.settings.deepseek_api_model,
            "messages": [dict(message) for message in messages],
            "stream": False,
            "temperature": self.settings.deepseek_temperature,
            "top_p": self.settings.deepseek_top_p,
        }
        if self.settings.deepseek_api_max_tokens > 0:
            body["max_tokens"] = self.settings.deepseek_api_max_tokens
        return body

    @staticmethod
    def _extract_content(data: Any) -> str:
        choices = data.get("choices") if isinstance(data, dict) else None
        if not isinstance(choices, list) or not choices:
            logger.error(f"{_MODULE} unexpected_response response={json_for_log(data)}")
            raise ModelTransportError(
                "DeepSeek API returned unexpected response",
                code="MODEL_EMPTY_OUTPUT",
            )
        choice = choices[0] if isinstance(choices[0], dict) else {}
        message = choice.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise ModelTransportError(
                "DeepSeek API returned empty content",
                code="MODEL_EMPTY_OUTPUT",
            )
        return content

    def _log_response(
        self,
        started_at: float,
        body: dict[str, Any],
        data: Any,
        content: str,
    ) -> None:
        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        usage = data.get("usage") if isinstance(data, dict) else None
        usage = usage if isinstance(usage, dict) else {}
        logger.info(
            f"{_MODULE} response_received model={body.get('model')} "
            f"duration_ms={duration_ms}ms "
            f"input_tokens={usage.get('prompt_tokens')} "
            f"completion_tokens={usage.get('completion_tokens')} "
            f"finish_reason={self._finish_reason(data)} "
            f"output_length={len(content)} "
            f"output_preview={json_for_log(content[:500])}"
        )

    @staticmethod
    def _finish_reason(data: Any) -> object:
        choices = data.get("choices") if isinstance(data, dict) else None
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            return choices[0].get("finish_reason")
        return None
