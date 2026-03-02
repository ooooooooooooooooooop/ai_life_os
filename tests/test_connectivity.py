import sys
from pathlib import Path
import os

# Create a manual config for Interface 1 (Mistral)
# Use 127.0.0.1 to avoid IPv6 issues
config_1 = {
    "provider": "ollama",
    "base_url": "http://127.0.0.1:11434",
    "model_name": "mistral:latest"
}

# Clear proxy env vars for this process to avoid localhost routing issues
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)

# Create a manual config for Interface 2 (GPT-5.2)
# Note: This will likely fail without an API key, checking for env var or placeholder
config_2 = {
    "provider": "openai",
    "base_url": "https://api.openai.com/v1",
    "model_name": "gpt-5.2",
    "api_key": "sk-placeholder-test-key" # We valid API key existence
}

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.llm_adapter import create_llm_adapter, LLMResponse

def run_connectivity_check(name, config):
    print(f"\n[Testing Interface: {name}]")
    print(f"Config: {config}")
    try:
        adapter = create_llm_adapter(config)
        print(f"Adapter created: {adapter.__class__.__name__}")
        
        print("Sending test prompt: 'Hello'...")
        response = adapter.generate("Hello, are you online?", max_tokens=20)
        
        if response.success:
            print(f"✅ SUCCESS")
            print(f"Response: {response.content.strip()}")
            print(f"Model used: {response.model}")
        else:
            print(f"❌ FAILED")
            print(f"Error: {response.error}")
            
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {str(e)}")

if __name__ == "__main__":
    print("="*50)
    print("AI Life OS - Connectivity Test")
    print("="*50)
    
    # Test 1: Local Privacy
    run_connectivity_check("1. Local Privacy (Mistral 3)", config_1)
    
    # Test 2: The Brain (GPT-5.2)
    # Check if user has a real key in env, otherwise warn
    if os.environ.get("OPENAI_API_KEY"):
         config_2["api_key"] = os.environ.get("OPENAI_API_KEY")
    
    run_connectivity_check("2. The Brain (GPT-5.2/OpenAI) [Hardcoded]", config_2)
    
    # Test 3: Active Config from model.yaml
    print("\n" + "-"*30)
    print("Testing ACTIVE Config from model.yaml")
    from core.llm_adapter import load_model_config
    active_config = load_model_config()
    run_connectivity_check("3. Active Provider", active_config)
    
    print("\n" + "="*50)

    # Test 4: The Memory (Gemini 3 Pro)
    config_4 = {
        "provider": "openai",
        "base_url": "https://api.hotaruapi.top/v1",
        "model_name": "gemini-3-pro-preview",
        "api_key": os.environ.get("OPENAI_API_KEY", "sk-placeholder-key"),
        "temperature": 0.7,
        "max_tokens": 2000
    }
    run_connectivity_check("4. The Memory (Gemini 3 Pro)", config_4)
    
    # Test 5: Cost Efficient (DeepSeek V3.2)
    config_5 = {
        "provider": "openai",
        "base_url": "https://api.hotaruapi.top/v1",
        "model_name": "deepseek-ai/deepseek-v3.1",
        "api_key": os.environ.get("OPENAI_API_KEY", "sk-placeholder-key"),
        "temperature": 0.7,
        "max_tokens": 2000
    }
    run_connectivity_check("5. Cost Efficient (DeepSeek V3.1)", config_5)
    
    print("\n" + "="*50)
