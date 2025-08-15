from typing import Dict, Any

TEMPLATES: Dict[str, Dict[str, Any]] = {
    "vllm-llama-3.1-8b": {
        "gpu_class": "24GB",
        "hourly_rate_cents": 99,
        "container": "ghcr.io/vllm/vllm-openai:latest",
        "port": 8000,
        "instance_type": "t3.micro"  # change to g5.xlarge later
    },
    "comfyui": {
        "gpu_class": "24GB",
        "hourly_rate_cents": 99,
        "container": "ghcr.io/comfyanonymous/comfyui:latest",
        "port": 8188,
        "instance_type": "t3.micro"  # change later
    },
}
