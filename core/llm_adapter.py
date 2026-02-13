"""
LLM Adapter for AI Life OS.

Provides a unified interface for interacting with various LLM providers.
Supports: OpenAI API, Ollama (local), and extensible to other providers.
"""
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Protocol

import yaml

# 配置文件路径
CONFIG_DIR = Path(__file__).parent.parent / "config"
MODEL_CONFIG_PATH = CONFIG_DIR / "model.yaml"


@dataclass
class LLMResponse:
    """Structured response from LLM."""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None


class LLMProvider(Protocol):
    """Protocol defining the LLM provider interface."""

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> LLMResponse:
        """Generate text completion."""
        ...

    def get_model_name(self) -> str:
        """Return the model name."""
        ...


class BaseLLMAdapter(ABC):
    """Base class for LLM adapters."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model_name = config.get("model_name", "unknown")

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> LLMResponse:
        """Generate text completion."""
        pass

    def get_model_name(self) -> str:
        return self.model_name


class OpenAIAdapter(BaseLLMAdapter):
    """Adapter for OpenAI API (also compatible with other OpenAI-compatible APIs)."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_key = config.get("api_key") or os.environ.get("OPENAI_API_KEY")
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self.model_name = config.get("model_name", "gpt-4o-mini")

        if not self.api_key:
            raise ValueError(
                "OpenAI API key not found. Set OPENAI_API_KEY env var or "
                "add 'api_key' to config/model.yaml"
            )

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> LLMResponse:
        """Generate using OpenAI API."""
        try:
            import httpx
        except ImportError:
            return LLMResponse(
                content="",
                model=self.model_name,
                error="httpx not installed. Run: pip install httpx"
            )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                data = response.json()

                return LLMResponse(
                    content=data["choices"][0]["message"]["content"],
                    model=data.get("model", self.model_name),
                    usage=data.get("usage")
                )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                from core.exceptions import LLMAuthError
                raise LLMAuthError(
                    provider="openai",
                    model_name=self.model_name,
                    endpoint=self.base_url
                )
            elif e.response.status_code == 429:
                from core.exceptions import LLMRateLimitError
                raise LLMRateLimitError(
                    provider="openai",
                    model_name=self.model_name,
                    endpoint=self.base_url
                )
            else:
                from core.exceptions import LLMError
                # 尝试读取响应文本以获取更多错误细节
                try:
                   error_detail = e.response.text
                except Exception:
                    error_detail = "No details"

                raise LLMError(
                    message=f"HTTP 错误: {e.response.status_code} - {error_detail}",
                    provider="openai",
                    model_name=self.model_name,
                    endpoint=self.base_url
                )
        except httpx.ConnectError:
            from core.exceptions import LLMConnectionError
            raise LLMConnectionError(
                provider="openai",
                model_name=self.model_name,
                endpoint=self.base_url
            )
        except httpx.TimeoutException:
            from core.exceptions import LLMTimeoutError
            raise LLMTimeoutError(
                provider="openai",
                model_name=self.model_name,
                endpoint=self.base_url,
                timeout_seconds=60.0
            )
        except Exception as e:
            from core.exceptions import LLMError
            raise LLMError(
                message=f"请求失败: {str(e)}",
                provider="openai",
                model_name=self.model_name,
                endpoint=self.base_url
            )


class OllamaAdapter(BaseLLMAdapter):
    """Adapter for local Ollama models."""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url", "http://localhost:11434")
        self.model_name = config.get("model_name", "qwen2.5:7b")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> LLMResponse:
        """Generate using Ollama API."""
        try:
            import httpx
        except ImportError:
            return LLMResponse(
                content="",
                model=self.model_name,
                error="httpx not installed. Run: pip install httpx"
            )

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        payload = {
            "model": self.model_name,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                )
                response.raise_for_status()
                data = response.json()

                return LLMResponse(
                    content=data.get("response", ""),
                    model=data.get("model", self.model_name),
                    usage={
                        "prompt_tokens": data.get("prompt_eval_count", 0),
                        "completion_tokens": data.get("eval_count", 0)
                    }
                )
        except httpx.ConnectError:
            from core.exceptions import LLMConnectionError
            raise LLMConnectionError(
                provider="ollama",
                model_name=self.model_name,
                endpoint=self.base_url
            )
        except httpx.TimeoutException:
            from core.exceptions import LLMTimeoutError
            raise LLMTimeoutError(
                provider="ollama",
                model_name=self.model_name,
                endpoint=self.base_url,
                timeout_seconds=120.0
            )
        except Exception as e:
            from core.exceptions import LLMError
            raise LLMError(
                message=f"请求失败: {str(e)}",
                provider="ollama",
                model_name=self.model_name,
                endpoint=self.base_url
            )


class RuleBasedAdapter(BaseLLMAdapter):
    """
    Fallback adapter that uses rule-based logic instead of LLM.
    Used when no LLM is configured or as a degraded mode.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.model_name = "rule_based"

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> LLMResponse:
        """Return a placeholder response indicating rule-based mode."""
        return LLMResponse(
            content="[规则模式] 当前使用规则驱动，未启用 LLM。",
            model=self.model_name,
            usage={"prompt_tokens": 0, "completion_tokens": 0}
        )


MODEL_CONFIG_PATH = CONFIG_DIR / "model.yaml"
LOCAL_MODEL_CONFIG_PATH = CONFIG_DIR / "local_model.yaml"


def load_model_config(profile_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Load model configuration from YAML file.
    Priority: local_model.yaml > model.yaml

    Args:
        profile_name: Optional profile name. If None, uses active_profile from config.

    Returns:
        Configuration dict for the specified or active profile.

    Note:
        Supports ${ENV_VAR} syntax for environment variable expansion.
    """
    raw_config = {}

    # 1. Try local config (user's private keys)
    if LOCAL_MODEL_CONFIG_PATH.exists():
        with open(LOCAL_MODEL_CONFIG_PATH, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f) or {}
    # 2. Try default config
    elif MODEL_CONFIG_PATH.exists():
        with open(MODEL_CONFIG_PATH, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f) or {}

    # 支持新的 profiles 结构
    if "profiles" in raw_config:
        profiles = raw_config["profiles"]

        # [NEW] 强制本地模式 (Force Local Mode System)
        # 如果启用，忽略传入的 profile_name，强制使用 'simple_local'
        if raw_config.get("force_local_mode", False):
            print("[System] [WARN] 强制本地模式 (Force Local Mode) 已激活。")
            print(f"[System] Profile '{profile_name or 'default'}' 将重定向至 'simple_local'。")
            profile_name = "simple_local"

        active_profile = profile_name or raw_config.get("active_profile", "simple_local")

        if active_profile not in profiles:
            print(f"[警告] Profile '{active_profile}' 不存在，使用规则模式")
            return {"provider": "rule_based"}

        config = profiles[active_profile]
        return _expand_env_vars(config)

    # 兼容旧的扁平结构
    if raw_config:
        return _expand_env_vars(raw_config)

    return {"provider": "rule_based"}


def _expand_env_vars(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Expand ${VAR} placeholders in config values with environment variables.

    Args:
        config: Configuration dictionary with potential ${VAR} placeholders.

    Returns:
        Configuration with expanded environment variables.
    """
    import re

    result = {}
    pattern = re.compile(r'\$\{([^}]+)\}')

    for key, value in config.items():
        if isinstance(value, str):
            match = pattern.match(value)
            if match:
                env_var = match.group(1)
                env_value = os.environ.get(env_var)
                if env_value:
                    result[key] = env_value
                else:
                    # Specific guidance for file-based configuration
                    raise ValueError(
                        (
                            "配置未从简 (local_model.yaml): "
                            f"'{key}' 字段当前为占位符 '${{{env_var}}}'。\n"
                            "请打开 config/local_model.yaml，直接将 "
                            f"'${{{env_var}}}' 替换为您真实的 API 密钥字符串。"
                        )
                    )
            else:
                result[key] = value
        elif isinstance(value, dict):
            result[key] = _expand_env_vars(value)
        else:
            result[key] = value

    return result


def create_llm_adapter(
    config: Optional[Dict[str, Any]] = None,
    profile_name: Optional[str] = None,
) -> BaseLLMAdapter:
    """
    Factory function to create the appropriate LLM adapter.

    Args:
        config: Optional config dict. If None, loads from model.yaml.
        profile_name: Optional profile name. Only used when config is None.

    Returns:
        Configured LLM adapter instance.
    """
    if config is None:
        config = load_model_config(profile_name)

    provider = config.get("provider", "rule_based").lower()

    if provider == "openai":
        return OpenAIAdapter(config)

    elif provider == "ollama":
        return OllamaAdapter(config)

    elif provider == "rule_based":
        return RuleBasedAdapter(config)
    else:
        raise ValueError(
            "[配置错误] 未知的 LLM provider: "
            f"'{provider}' (Profile: {profile_name})。"
            "请检查 config/model.yaml 或 local_model.yaml。"
        )


# 单例模式：全局 LLM 实例注册表 (Profile Name -> Instance)
_llm_registry: Dict[str, BaseLLMAdapter] = {}
_default_profile: Optional[str] = None


def get_llm(profile_name: Optional[str] = None) -> BaseLLMAdapter:
    """
    Get or create an LLM adapter instance for the specified profile.

    If profile_name is None, uses the 'active_profile' from config (global default).
    If profile_name is provided, returns the specific instance for that profile.
    Instances are cached in _llm_registry.
    """
    global _llm_registry, _default_profile

    # Load config to determine default if not set
    if _default_profile is None:
        config = load_model_config()
        _default_profile = config.get("active_profile", "simple_local")

    target_profile = profile_name or _default_profile

    if target_profile not in _llm_registry:
        # Create new instance
        print(f"[System] Initializing LLM Profile: {target_profile}")
        config = load_model_config(target_profile)
        _llm_registry[target_profile] = create_llm_adapter(config, target_profile)

    return _llm_registry[target_profile]


def reset_llm() -> None:
    """Reset the global LLM registry (useful for testing or config changes)."""
    global _llm_registry, _default_profile
    _llm_registry = {}
    _default_profile = None
