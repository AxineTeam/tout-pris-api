from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone
from pydantic_ai import Agent, RunContext


@dataclass
class AssistantContext:
    language: str


agent = Agent(
    settings.ASSISTANT_MODEL,
    deps_type=AssistantContext,
    defer_model_check=True,
    instructions=(
        "Tu es l'assistant de Tout Pris, une application avec laquelle un foyer prépare les "
        "bagages de ses voyages. Tu aides un membre du foyer à tenir ses voyages, ses kits et "
        "ses objets à jour. Réponds dans la langue du dernier message de l'utilisateur, et "
        "n'invente jamais une donnée du foyer : si tu ne l'as pas, demande-la."
    ),
)


@agent.instructions
def state_the_current_day_and_interface_language(ctx: RunContext[AssistantContext]) -> str:
    return (
        f"La date du jour est {timezone.localdate().isoformat()}. "
        f"La langue de l'interface est « {ctx.deps.language} » : "
        "réponds dans cette langue quand le message est trop court pour en déduire une."
    )
