from app.models.user import User
from app.plugins.registry import PluginRegistry

JAIN_SYSTEM_PROMPT_BASE = """You are Jain, an AI assistant that helps users through a set of skills provided by plugins.

Your personality: friendly, concise, practical. You speak in short sentences unless the user asks for detail.

When a user request matches one of your available skills, use the appropriate tool to fulfill it. When asked to find real-world data (locations, listings, status), always use tools — never make up data.

When helping a user create or configure something, you can either:
1. Gather information conversationally by asking one question at a time, or
2. Present a form if the plugin provides one and the user prefers that.

Ask the user which they prefer if it's not obvious from context.
"""


def build_system_prompt(registry: PluginRegistry, user: User | None = None) -> str:
    parts = [JAIN_SYSTEM_PROMPT_BASE]

    # Phase 2B: inject the user's global auth state. The platform gates
    # auth-required tools at the executor level, so Jain just needs to know
    # whether the user is signed in for conversational framing.
    if user is not None:
        parts.append(
            f"\n\n[user signed in as {user.email} ({user.name})]"
        )
    else:
        parts.append(
            "\n\n[user not authenticated — if they ask for something that requires signing in, "
            "the platform will refuse the tool call automatically and prompt them to sign in. "
            "You don't need to check auth state yourself.]"
        )

    skills = registry.skill_descriptions()
    if skills:
        parts.append("\n\nAvailable skills:")
        for skill_key, description in sorted(skills.items()):
            parts.append(f"\n- {skill_key}: {description}")

    return "".join(parts)
