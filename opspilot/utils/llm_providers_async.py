"""Modern async LLM provider system with httpx for better performance.

This is the next-generation async implementation. The sync version is kept
for backward compatibility during migration.
"""

import asyncio
import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx
import structlog

from opspilot.settings import get_settings
from opspilot.exceptions import (
    LLMError,
    LLMTimeoutError,
    LLMResponseError,
    LLMRateLimitError,
    LLMParseError,
)

logger = structlog.get_logger(__name__)


@dataclass
class CircuitBreaker:
    """Circuit breaker for provider failure protection."""
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    is_open: bool = False
    threshold: int = 5
    timeout_seconds: int = 60

    def record_failure(self):
        """Record a failure and potentially open the circuit."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        if self.failure_count >= self.threshold:
            self.is_open = True
            logger.warning(
                "circuit_breaker_opened",
                failure_count=self.failure_count,
                threshold=self.threshold
            )

    def record_success(self):
        """Record success and reset the circuit."""
        if self.is_open:
            logger.info("circuit_breaker_closed")
        self.failure_count = 0
        self.is_open = False
        self.last_failure_time = None

    def can_attempt(self) -> bool:
        """Check if we can attempt a call."""
        if not self.is_open:
            return True

        if self.last_failure_time:
            elapsed = datetime.now() - self.last_failure_time
            if elapsed > timedelta(seconds=self.timeout_seconds):
                logger.info("circuit_breaker_half_open", elapsed_seconds=elapsed.total_seconds())
                return True

        return False


@dataclass
class ProviderStats:
    """Statistics for a provider."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_latency_ms: float = 0
    circuit_breaker: CircuitBreaker = field(default_factory=CircuitBreaker)

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.successful_calls / self.total_calls

    @property
    def avg_latency_ms(self) -> float:
        if self.successful_calls == 0:
            return 0.0
        return self.total_latency_ms / self.successful_calls


class AsyncLLMProvider:
    """Base class for async LLM providers."""

    def __init__(self, timeout: int | None = None):
        settings = get_settings()
        self.timeout = timeout or settings.llm_timeout
        self.stats = ProviderStats()
        self.logger = logger.bind(provider=self.__class__.__name__)

    async def is_available(self) -> bool:
        """Check if provider is available."""
        raise NotImplementedError

    async def call(self, prompt: str) -> str:
        """Call the LLM with a prompt."""
        raise NotImplementedError

    async def call_with_retry(
        self,
        prompt: str,
        max_retries: int | None = None,
        initial_delay: float = 1.0,
    ) -> str:
        """Call with automatic retry and exponential backoff."""
        settings = get_settings()
        max_retries = max_retries or settings.llm_max_retries

        if not self.stats.circuit_breaker.can_attempt():
            raise LLMError(
                f"{self.__class__.__name__} circuit breaker is open",
                "Too many recent failures"
            )

        last_error = None
        delay = initial_delay

        for attempt in range(max_retries + 1):
            try:
                start_time = time.time()
                result = await self.call(prompt)
                elapsed_ms = (time.time() - start_time) * 1000

                self.stats.total_calls += 1
                self.stats.successful_calls += 1
                self.stats.total_latency_ms += elapsed_ms
                self.stats.circuit_breaker.record_success()

                self.logger.info(
                    "llm_call_success",
                    attempt=attempt + 1,
                    latency_ms=round(elapsed_ms, 2)
                )

                return result

            except Exception as e:
                last_error = e
                self.stats.total_calls += 1
                self.stats.failed_calls += 1
                self.stats.circuit_breaker.record_failure()

                self.logger.warning(
                    "llm_call_failed",
                    attempt=attempt + 1,
                    error=str(e),
                    error_type=type(e).__name__
                )

                if "rate limit" in str(e).lower() or "429" in str(e):
                    raise LLMRateLimitError(self.__class__.__name__)

                if attempt < max_retries:
                    await asyncio.sleep(delay)
                    delay *= 2.0

        raise LLMError(
            f"{self.__class__.__name__} failed after {max_retries + 1} attempts",
            str(last_error)
        )

    def parse_json(self, raw: str) -> dict:
        """Parse JSON from LLM output."""
        # Try parsing as-is
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Remove markdown code blocks
        content = raw
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end > start:
                content = content[start:end].strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Extract JSON object
        start_idx = raw.find('{')
        end_idx = raw.rfind('}')
        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            json_str = raw[start_idx:end_idx + 1]
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

        raise LLMParseError(raw)


class AsyncOllamaProvider(AsyncLLMProvider):
    """Async Ollama provider (uses subprocess, not truly async but non-blocking)."""

    def __init__(self, model: str | None = None, timeout: int | None = None):
        super().__init__(timeout)
        settings = get_settings()
        self.model = model or settings.ollama_model

    def _resolve_ollama_path(self) -> Optional[str]:
        """Resolve Ollama binary path."""
        ollama_path = shutil.which("ollama")
        if ollama_path:
            return ollama_path

        # Windows fallback
        fallback = Path.home() / "AppData/Local/Programs/Ollama/ollama.exe"
        if fallback.exists():
            return str(fallback)

        return None

    async def is_available(self) -> bool:
        """Check if Ollama is available."""
        try:
            ollama_path = self._resolve_ollama_path()
            if not ollama_path:
                return False

            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    [ollama_path, "list"],
                    capture_output=True,
                    timeout=5,
                    check=True
                )
            )
            return result.returncode == 0
        except Exception:
            return False

    async def call(self, prompt: str) -> str:
        """Call Ollama LLM."""
        ollama_path = self._resolve_ollama_path()
        if not ollama_path:
            raise LLMError("Ollama not found", "Binary not in PATH")

        try:
            loop = asyncio.get_event_loop()
            process = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    [ollama_path, "run", self.model],
                    input=prompt,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=self.timeout
                )
            )

            if process.returncode != 0:
                raise LLMResponseError("Ollama", process.stderr.strip())

            return process.stdout.strip()

        except subprocess.TimeoutExpired:
            raise LLMTimeoutError("Ollama", self.timeout)


class AsyncOpenRouterProvider(AsyncLLMProvider):
    """Async OpenRouter provider."""

    def __init__(self, model: str | None = None, timeout: int | None = None):
        super().__init__(timeout)
        settings = get_settings()
        self.model = model or settings.openrouter_model
        self.api_key = settings.openrouter_api_key
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    async def is_available(self) -> bool:
        """Check if API key is configured."""
        return self.api_key is not None and len(self.api_key) > 0

    async def call(self, prompt: str) -> str:
        """Call OpenRouter API."""
        if not self.api_key:
            raise LLMError("OpenRouter API key not set", "Set OPENROUTER_API_KEY")

        settings = get_settings()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/opspilot",
            "X-Title": "OpsPilot"
        }

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.base_url,
                    headers=headers,
                    json=payload
                )

                if response.status_code == 429:
                    raise LLMRateLimitError("OpenRouter")

                if not response.is_success:
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("error", {}).get("message", response.text)
                    except Exception:
                        error_msg = response.text or f"HTTP {response.status_code}"
                    raise LLMResponseError("OpenRouter", error_msg)

                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    raise LLMResponseError("OpenRouter", "Empty choices")
                content = choices[0].get("message", {}).get("content")
                if not content:
                    raise LLMResponseError("OpenRouter", "Missing content")
                return content

        except httpx.TimeoutException:
            raise LLMTimeoutError("OpenRouter", self.timeout)
        except httpx.RequestError as e:
            raise LLMError("OpenRouter API call failed", str(e))


class AsyncGeminiProvider(AsyncLLMProvider):
    """Async Google Gemini provider."""

    def __init__(self, model: str | None = None, timeout: int | None = None):
        super().__init__(timeout)
        settings = get_settings()
        self.model = model or settings.gemini_model
        self.api_key = settings.google_api_key

    async def is_available(self) -> bool:
        """Check if API key is configured."""
        return self.api_key is not None and len(self.api_key) > 0

    async def call(self, prompt: str) -> str:
        """Call Google Gemini API."""
        if not self.api_key:
            raise LLMError("Google API key not set", "Set GOOGLE_API_KEY")

        settings = get_settings()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": settings.llm_temperature,
                "maxOutputTokens": settings.llm_max_tokens
            }
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code == 429:
                    raise LLMRateLimitError("Gemini")

                if not response.is_success:
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("error", {}).get("message", response.text)
                    except Exception:
                        error_msg = response.text or f"HTTP {response.status_code}"
                    raise LLMResponseError("Gemini", error_msg)

                data = response.json()
                candidates = data.get("candidates", [])
                if not candidates:
                    raise LLMResponseError("Gemini", "Empty candidates")
                parts = candidates[0].get("content", {}).get("parts", [])
                if not parts:
                    raise LLMResponseError("Gemini", "Empty parts")
                return parts[0].get("text", "")

        except httpx.TimeoutException:
            raise LLMTimeoutError("Gemini", self.timeout)
        except httpx.RequestError as e:
            raise LLMError("Gemini API call failed", str(e))


class AsyncLLMRouter:
    """Smart async LLM router with parallel attempts and automatic fallback."""

    def __init__(self, prefer_local: bool | None = None):
        settings = get_settings()
        self.prefer_local = prefer_local if prefer_local is not None else settings.prefer_local
        self.providers = self._initialize_providers()
        self.last_successful_provider: Optional[AsyncLLMProvider] = None
        self.logger = logger.bind(component="llm_router")

    def _initialize_providers(self) -> list[AsyncLLMProvider]:
        """Initialize providers in priority order."""
        if self.prefer_local:
            return [
                AsyncOllamaProvider(),
                AsyncGeminiProvider(),
                AsyncOpenRouterProvider(),
            ]
        else:
            return [
                AsyncGeminiProvider(),
                AsyncOpenRouterProvider(),
                AsyncOllamaProvider(),
            ]

    async def get_available_providers(self) -> list[str]:
        """Get list of available provider names."""
        available = []
        checks = [provider.is_available() for provider in self.providers]
        results = await asyncio.gather(*checks, return_exceptions=True)
        
        for provider, is_avail in zip(self.providers, results):
            if isinstance(is_avail, bool) and is_avail:
                if provider.stats.circuit_breaker.can_attempt():
                    available.append(provider.__class__.__name__)
        
        return available

    async def call(self, prompt: str, timeout: int | None = None) -> str:
        """
        Call LLM with automatic fallback.
        
        Strategy: Try last successful provider first, then try all others.
        """
        settings = get_settings()
        timeout = timeout or settings.llm_timeout
        errors = []

        # Try last successful provider first
        if self.last_successful_provider:
            if self.last_successful_provider.stats.circuit_breaker.can_attempt():
                try:
                    self.last_successful_provider.timeout = timeout
                    result = await self.last_successful_provider.call_with_retry(prompt)
                    return result
                except Exception as e:
                    errors.append(f"{self.last_successful_provider.__class__.__name__}: {e}")

        # Try all providers sequentially
        for provider in self.providers:
            if not await provider.is_available():
                errors.append(f"{provider.__class__.__name__}: Not available")
                continue

            if not provider.stats.circuit_breaker.can_attempt():
                errors.append(f"{provider.__class__.__name__}: Circuit breaker open")
                continue

            try:
                provider.timeout = timeout
                result = await provider.call_with_retry(prompt)
                self.last_successful_provider = provider
                return result

            except LLMRateLimitError as e:
                errors.append(f"{provider.__class__.__name__}: Rate limited")
                continue
            except Exception as e:
                errors.append(f"{provider.__class__.__name__}: {e}")
                continue

        # All providers failed
        error_summary = "\n".join(errors)
        self.logger.error("all_providers_failed", errors=errors)
        raise LLMError("All LLM providers failed", error_summary)

    def get_provider_stats(self) -> dict[str, dict]:
        """Get statistics for all providers."""
        stats = {}
        for provider in self.providers:
            name = provider.__class__.__name__
            stats[name] = {
                "total_calls": provider.stats.total_calls,
                "success_rate": provider.stats.success_rate,
                "avg_latency_ms": provider.stats.avg_latency_ms,
                "circuit_open": provider.stats.circuit_breaker.is_open,
            }
        return stats


# Global async router instance
_global_async_router: Optional[AsyncLLMRouter] = None


def get_async_llm_router(prefer_local: bool | None = None) -> AsyncLLMRouter:
    """Get global async LLM router instance."""
    global _global_async_router
    if _global_async_router is None:
        _global_async_router = AsyncLLMRouter(prefer_local=prefer_local)
    return _global_async_router


def reset_async_llm_router():
    """Reset the global async LLM router."""
    global _global_async_router
    _global_async_router = None
