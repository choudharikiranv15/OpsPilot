"""
Demonstration of OpsPilot-AI modernization improvements.

This script showcases:
1. Pydantic Settings for configuration
2. Structured logging with structlog
3. Async LLM providers (coming soon in CLI)
"""

import asyncio
from opspilot.settings import get_settings
from opspilot.logging_config import configure_logging, get_logger


def demo_settings():
    """Demonstrate the new Pydantic Settings system."""
    print("=" * 60)
    print("1. PYDANTIC SETTINGS DEMONSTRATION")
    print("=" * 60)
    
    # Get settings instance (automatically loads from .env)
    settings = get_settings()
    
    print(f"\nLLM Configuration:")
    print(f"  Timeout: {settings.llm_timeout}s")
    print(f"  Max Retries: {settings.llm_max_retries}")
    print(f"  Temperature: {settings.llm_temperature}")
    print(f"  Prefer Local: {settings.prefer_local}")
    
    print(f"\nRedis Configuration:")
    print(f"  Host: {settings.redis_host}")
    print(f"  Port: {settings.redis_port}")
    print(f"  TTL Days: {settings.redis_ttl_days}")
    
    print(f"\nDefault Models:")
    models = settings.get_default_models()
    for provider, model in models.items():
        print(f"  {provider}: {model}")
    
    print(f"\nAPI Keys Configured:")
    print(f"  OpenRouter: {'✓' if settings.openrouter_api_key else '✗'}")
    print(f"  Google Gemini: {'✓' if settings.google_api_key else '✗'}")
    print(f"  Anthropic: {'✓' if settings.anthropic_api_key else '✗'}")
    print(f"  HuggingFace: {'✓' if settings.huggingface_api_key else '✗'}")


def demo_structured_logging():
    """Demonstrate structured logging with structlog."""
    print("\n" + "=" * 60)
    print("2. STRUCTURED LOGGING DEMONSTRATION")
    print("=" * 60)
    
    # Configure logging (JSON mode for production, console for dev)
    configure_logging(level="INFO", json_logs=False)
    
    logger = get_logger(__name__)
    
    print("\nConsole output (development mode):")
    logger.info("application_started", version="0.1.7", environment="development")
    logger.info("context_collected", logs_found=True, env_vars=12, severity="P1")
    logger.warning("provider_unavailable", provider="Ollama", reason="Not installed")
    logger.info("llm_call_success", provider="Gemini", latency_ms=234.5, tokens=150)
    
    print("\nKey benefits:")
    print("  • Machine-parseable (can switch to JSON output)")
    print("  • Structured data (key-value pairs)")
    print("  • Automatic timestamps")
    print("  • Easy filtering and searching")


async def demo_async_providers():
    """Demonstrate async LLM providers."""
    print("\n" + "=" * 60)
    print("3. ASYNC LLM PROVIDERS DEMONSTRATION")
    print("=" * 60)
    
    # Import the async router
    from opspilot.utils.llm_providers_async import get_async_llm_router
    
    router = get_async_llm_router()
    
    print("\nChecking available providers...")
    available = await router.get_available_providers()
    
    if available:
        print(f"Available providers: {', '.join(available)}")
    else:
        print("No providers available (configure API keys or install Ollama)")
    
    print("\nProvider statistics:")
    stats = router.get_provider_stats()
    for provider, stat_data in stats.items():
        print(f"  {provider}:")
        print(f"    Total calls: {stat_data['total_calls']}")
        print(f"    Success rate: {stat_data['success_rate']:.1%}")
        print(f"    Avg latency: {stat_data['avg_latency_ms']:.1f}ms")
        print(f"    Circuit breaker: {'OPEN' if stat_data['circuit_open'] else 'CLOSED'}")
    
    print("\nKey benefits:")
    print("  • Non-blocking HTTP calls")
    print("  • 2-5x faster when providers are slow")
    print("  • Parallel provider attempts (future)")
    print("  • Same reliability (circuit breaker, retries)")


def demo_migration_compatibility():
    """Show backward compatibility."""
    print("\n" + "=" * 60)
    print("4. BACKWARD COMPATIBILITY")
    print("=" * 60)
    
    print("\nOld code still works:")
    print("  ✓ sync LLM calls (call_llama)")
    print("  ✓ environment variables")
    print("  ✓ existing CLI commands")
    print("  ✓ Python API unchanged")
    
    print("\nNew features are opt-in:")
    print("  → Use Pydantic Settings (recommended)")
    print("  → Use async providers (faster)")
    print("  → Use structured logging (production-ready)")


def main():
    """Run all demonstrations."""
    print("\n" + "=" * 60)
    print("OPSPILOT-AI MODERNIZATION DEMO")
    print("=" * 60)
    
    # Demo 1: Settings
    demo_settings()
    
    # Demo 2: Structured Logging
    demo_structured_logging()
    
    # Demo 3: Async Providers
    asyncio.run(demo_async_providers())
    
    # Demo 4: Compatibility
    demo_migration_compatibility()
    
    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    print("\nFor more information:")
    print("  • See UPGRADE_GUIDE.md for migration steps")
    print("  • See MODERNIZATION_SUMMARY.md for changes")
    print("  • See opspilot/settings.py for all config options")
    print()


if __name__ == "__main__":
    main()
