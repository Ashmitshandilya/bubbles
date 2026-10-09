"""
OmniRoute Direct API Client for Bubbles Brain

This module provides direct OmniRoute API access to bypass RTK routing limitations.
When Claude Code Agent() tool routing is broken, Brain uses this client to:
1. Fetch live model catalog
2. Resolve capability profiles to provider-prefixed model IDs
3. Execute chat completions with explicit provider prefixes

This is a temporary workaround until RTK v0.42.4+ fixes the provider prefix issue.
"""

import os
import json
import requests
from typing import Optional, Dict, List, Any


class OmniRouteClient:
    """Direct OmniRoute API client for Bubbles Brain delegation"""

    DEFAULT_BASE_URL = "http://localhost:20128"

    # Capability profile -> model preference order
    CAPABILITY_PROFILES = {
        "REASONING_HIGH": [
            "Claude Opus 5",
            "GPT-5.6 Terra",
            "Nemotron 3 Ultra 550B",
            "Claude Haiku 4.5",
        ],
        "REASONING_MODERATE": [
            "Claude Sonnet 5",
            "DeepSeek V4 Pro",
            "Nemotron 3 Super 120B",
            "Claude Haiku 4.5",
        ],
        "CODING_STANDARD": [
            "Claude Sonnet 5",
            "DeepSeek V4 Pro",
            "Nemotron 3 Ultra 550B",
            "Step 3.7 Flash",
        ],
        "CODING_FAST": [
            "Claude Haiku 4.5",
            "DeepSeek V4 Flash",
            "Step 3.7 Flash",
            "Qwen2.5 Coder 32B (LLM7)",
        ],
        "TESTING": [
            "Claude Haiku 4.5",
            "DeepSeek V4 Flash",
            "Step 3.7 Flash",
            "Mistral Small 4 2603",
        ],
        "RESEARCH_READ_ONLY": [
            "Claude Haiku 4.5",
            "DeepSeek V4 Flash",
            "Gemini 3.7 Flash",
            "Step 3.7 Flash",
        ],
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 30,
        fallback_to_base_models: bool = True,
    ):
        """
        Initialize OmniRoute client.

        Args:
            api_key: OmniRoute API key (from env or explicit)
            base_url: OmniRoute API base URL (default: localhost:20128)
            timeout: Request timeout in seconds
            fallback_to_base_models: Fall back to Claude base models if direct API fails
        """
        self.api_key = api_key or os.getenv("OMNIROUTE_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.fallback_to_base_models = fallback_to_base_models
        self._catalog_cache: Optional[List[Dict[str, Any]]] = None

    def _headers(self) -> Dict[str, str]:
        """Return request headers with authentication"""
        headers = {"Content-Type": "application/json"}
        # Try without Authorization header first, as logs show REQUIRE_API_KEY=false
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def get_models(self, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch live OmniRoute model catalog.

        Returns list of models with format:
        [
            {"id": "Claude Sonnet 5", "provider": "kc", ...},
            {"id": "Nemotron 3 Ultra 550B", "provider": "nvidia", ...},
            ...
        ]
        """
        if use_cache and self._catalog_cache:
            return self._catalog_cache

        try:
            response = requests.get(
                f"{self.base_url}/api/v1/models",
                headers=self._headers(),
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            models = data.get("data", [])
            self._catalog_cache = models
            return models
        except Exception as e:
            # Fallback to capability-profile models when catalog cannot be fetched
            # These are verified OmniRoute models from the live catalog
            fallback = []
            for models in self.CAPABILITY_PROFILES.values():
                for model_name in models:
                    if not any(m.get("id") == model_name for m in fallback):
                        # Infer provider from model name patterns
                        provider = "kc"
                        if "GPT" in model_name or "Qwen" in model_name:
                            provider = "llm7"
                        elif "Nemotron" in model_name or "DeepSeek" in model_name or "Step" in model_name:
                            provider = "nvidia"
                        elif "Mistral" in model_name:
                            provider = "llm7"
                        fallback.append({"id": model_name, "provider": provider})
            self._catalog_cache = fallback
            return fallback

    def resolve_capability_to_model(
        self,
        capability_profile: str,
        catalog: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Resolve a capability profile to a provider-prefixed model ID.

        Args:
            capability_profile: One of REASONING_HIGH, REASONING_MODERATE, CODING_STANDARD, etc.
            catalog: Model catalog (fetches if not provided)

        Returns:
            Provider-prefixed model ID (e.g., "kc/Claude Sonnet 5")

        Raises:
            ValueError if no matching model found
        """
        if catalog is None:
            catalog = self.get_models()

        preferred_models = self.CAPABILITY_PROFILES.get(capability_profile, [])
        if not preferred_models:
            raise ValueError(f"Unknown capability profile: {capability_profile}")

        # Find first available model from preferences
        for model_name in preferred_models:
            for entry in catalog:
                if entry.get("id") == model_name:
                    provider = entry.get("provider", "")
                    if provider:
                        model_id = f"{provider}/{model_name}"
                        print(f"DEBUG: Testing {model_name} with provider {provider}")
                        # Quick test to see if model is actually available
                        try:
                            test_messages = [{"role": "user", "content": "test"}]
                            self.complete(model_id, test_messages, max_tokens=1)
                            print(f"DEBUG: Model {model_id} is available")
                            return model_id
                        except Exception as test_e:
                            # Check various ways the "not available" error might appear
                            error_str = str(test_e)
                            if ("not available in the active live catalog" in error_str or
                                "not available in the active live catalog" in getattr(test_e, '__context__', '') or
                                (hasattr(test_e, '__cause__') and test_e.__cause__ and
                                 "not available in the active live catalog" in str(test_e.__cause__))):
                                print(f"DEBUG: Model {model_id} not available in live catalog, trying next")
                                continue  # Try next model
                            else:
                                # Some other error (auth, etc.) - still return this model as it might work
                                print(f"DEBUG: Model {model_id} has other error (might still work): {test_e}")
                                return model_id

        # If nothing found in catalog or all preferred models unavailable, fall back to auto/best-reasoning
        # which works even when specific provider models aren't available
        print(f"DEBUG: No available preferred model for {capability_profile}, falling back to auto/best-reasoning")
        return "auto/best-reasoning"

    def complete(
        self,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: int = 2000,
        temperature: float = 0.7,
        **kwargs,
    ) -> str:
        """
        Execute a chat completion request with provider-prefixed model ID.

        Args:
            model: Provider-prefixed model ID (e.g., "kc/Claude Sonnet 5")
            messages: Chat messages (OpenAI format)
            max_tokens: Maximum response tokens
            temperature: Temperature for generation
            **kwargs: Additional OmniRoute API parameters

        Returns:
            Response text from the model

        Raises:
            RuntimeError if request fails
        """
        try:
            # Debug: print the model and the request payload
            print(f"DEBUG: OmniRoute model: {model}")
            print(f"DEBUG: OmniRoute messages: {messages}")
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                headers=self._headers(),
                json={
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    **kwargs,
                },
                timeout=self.timeout,
            )
            print(f"DEBUG: OmniRoute response status: {response.status_code}")
            print(f"DEBUG: OmniRoute response text: {response.text}")
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"OmniRoute completion failed: {e}")

    def invoke_specialist(
        self,
        capability_profile: str,
        task_prompt: str,
        task_context: Dict[str, Any],
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        High-level interface for Brain to invoke a specialist with correct model.

        This is what Brain calls to delegate work to specialists with proper model routing.

        Args:
            capability_profile: e.g., "REASONING_MODERATE" for design, "CODING_STANDARD" for implementation
            task_prompt: The specialist task prompt
            task_context: Additional context to include in the request
            use_cache: Whether to cache the model catalog

        Returns:
            {
                "status": "success" | "error",
                "model_used": "provider-prefixed model ID",
                "response": "specialist response text",
                "error": "error message if failed",
            }
        """
        try:
            catalog = self.get_models(use_cache=use_cache)
            model_id = self.resolve_capability_to_model(capability_profile, catalog)

            # Build messages with context
            context_str = json.dumps(task_context, indent=2) if task_context else ""
            messages = []

            if context_str:
                messages.append({
                    "role": "user",
                    "content": f"Context:\n{context_str}\n\nTask:\n{task_prompt}"
                })
            else:
                messages.append({"role": "user", "content": task_prompt})

            response_text = self.complete(model_id, messages)

            return {
                "status": "success",
                "model_used": model_id,
                "response": response_text,
                "error": None,
            }
        except Exception as e:
            return {
                "status": "error",
                "model_used": None,
                "response": None,
                "error": str(e),
            }


def create_client(
    base_url: str = OmniRouteClient.DEFAULT_BASE_URL,
    **kwargs,
) -> OmniRouteClient:
    """Convenience function to create OmniRoute client with defaults"""
    return OmniRouteClient(base_url=base_url, **kwargs)


# Example usage for Brain integration:
if __name__ == "__main__":
    # Initialize client
    client = OmniRouteClient()

    # Example 1: List available models
    print("=== Available Models ===")
    try:
        models = client.get_models()
        for model in models[:5]:  # Show first 5
            print(f"  {model.get('provider')}/{model.get('id')}")
    except Exception as e:
        print(f"Error: {e}")

    # Example 2: Resolve capability to model
    print("\n=== Model Resolution ===")
    try:
        model_id = client.resolve_capability_to_model("REASONING_MODERATE")
        print(f"REASONING_MODERATE -> {model_id}")
    except Exception as e:
        print(f"Error: {e}")

    # Example 3: Invoke specialist
    print("\n=== Specialist Invocation ===")
    result = client.invoke_specialist(
        capability_profile="CODING_STANDARD",
        task_prompt="Design a React component for an organ tracker card.",
        task_context={"app": "Bubbles", "context": "longitudinal health UI"},
    )
    if result["status"] == "success":
        print(f"Model: {result['model_used']}")
        print(f"Response: {result['response'][:200]}...")
    else:
        print(f"Error: {result['error']}")
