"""Public agent identity and per-question address policy shared with the UI."""
import re

WAKE_POLICY = {
    'agent_name': '니즈',
    'wake_aliases': ['니즈', '니즈야', '니즈님'],
    'require_wake_name': True,
}


def calls_agent(text: str, policy: dict = WAKE_POLICY) -> bool:
    if not policy['require_wake_name']:
        return True
    aliases = {' '.join(alias.split()) for alias in [policy['agent_name'], *policy['wake_aliases']] if alias.strip()}
    names = '|'.join(re.escape(alias) for alias in sorted(aliases, key=len, reverse=True))
    return bool(re.match(r'''^[\s"'“‘]*(?:''' + names + r')(?=$|[\s,，.!?。！？:：~～])', ' '.join(text.split())))


def addressed_question(question: str) -> str:
    return f"{WAKE_POLICY['agent_name']}, {question}"
