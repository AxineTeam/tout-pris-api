from django.utils import timezone
from pydantic_ai.models.test import TestModel

from assistant.agent import AssistantContext, agent


def run(prompt, language="en-us"):
    with agent.override(model=TestModel(custom_output_text="ok")):
        return agent.run_sync(prompt, deps=AssistantContext(language=language))


def instructions_of(result):
    return "\n".join(
        message.instructions for message in result.all_messages() if message.kind == "request"
    )


def test_the_agent_answers_without_a_provider_key_or_a_network():
    assert run("bonjour").output == "ok"


def test_the_agent_is_told_the_current_day():
    assert timezone.localdate().isoformat() in instructions_of(run("quel jour sommes-nous ?"))


def test_the_agent_is_told_the_language_to_fall_back_on():
    assert "« fr »" in instructions_of(run("ok", language="fr"))
