import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.llm_adapter import create_llm_adapter

def test_connection():
    print("Testing LLM Connection...")
    try:
        adapter = create_llm_adapter()
        print(f"Provider: {type(adapter).__name__}")
        print(f"Model: {adapter.model_name}")
        if hasattr(adapter, 'base_url'):
            print(f"Endpoint: {adapter.base_url}")

        response = adapter.generate(
            prompt="Hello, are you working?",
            max_tokens=10
        )

        if response.success:
            print("\n[SUCCESS] Connection verified!")
            print(f"Response: {response.content}")
        else:
            print(f"\n[FAILURE] Logic Error: {response.error}")

    except Exception as e:
        print(f"\n[CRITICAL FAILURE] Exception: {type(e).__name__}")
        print(str(e))
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_connection()
