import os

DEFAULT_MODEL = "gpt-5.6"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


def model_name():
    return os.getenv("OPENAI_MODEL") or DEFAULT_MODEL


def change_key(state, key, source):
    if state["agent_settings"]["api_key"] != key:
        state["previous_response_id"] = None
        state["vector_store_id"] = None
        state["uploaded_names"] = []
        state["speech_cache"] = {}
    state["agent_settings"].update(api_key=key, source=source)
