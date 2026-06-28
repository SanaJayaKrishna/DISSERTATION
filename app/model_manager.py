from pathlib import Path
from huggingface_hub import HfApi

LOCAL_MODEL_DIR = Path("saved_models")

ONLINE_MODELS = [
    "meta-llama/Llama-3-8B-Instruct",
    "meta-llama/Llama-3-70B-Instruct",
    "google/gemma-3-4b-it",
    "google/gemma-3-12b-it",
    "Qwen/Qwen2.5-7B-Instruct",
    "mistralai/Mistral-7B-Instruct-v0.3",
]

from huggingface_hub import HfApi

api = HfApi()
models = api.list_models(search="llama", limit=20)


def get_local_models():
    """
    Returns all locally available fine-tuned models.
    """

    if not LOCAL_MODEL_DIR.exists():
        return []

    return sorted(
        model.name
        for model in LOCAL_MODEL_DIR.iterdir()
        if model.is_dir()
    )

def get_all_models():

    models = []

    for model in get_local_models():
        models.append(
            {
                "type": "Fine-tuned",
                "name": model,
            }
        )

    for model in ONLINE_MODELS:
        models.append(
            {
                "type": "Online",
                "name": model,
            }
        )

    return models

def search_models(query):

    models = get_all_models()

    if not query:
        return models

    query = query.lower()

    return [
        model
        for model in models
        if query in model["name"].lower()
    ]


api = HfApi()
models = api.list_models(search="llama", limit=20)
