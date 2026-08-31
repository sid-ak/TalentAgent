"""Pins the inbox transition table and the model's inability to invent a state (Spec Appendix B)."""

from __future__ import annotations

from typing import Any

import pytest
from talentagent.models.client import ModelClient, Tier
from talentagent.pipeline.inbox import (
    ApplicationState,
    MessageLabel,
    next_state,
    read_inbox,
)


def _client(response: dict[str, Any]) -> ModelClient:
    """Return a client whose transport answers every call with `response`."""
    return ModelClient(transport=lambda _call: response, record=False, golden_root=None)


class _Recorder:
    """A transport that answers with a fixed response and remembers the call it was given."""

    def __init__(self, response: dict[str, Any]) -> None:
        """Store the response to return and prepare to capture one call."""
        self.response = response
        self.calls: list[Any] = []

    def __call__(self, call: Any) -> dict[str, Any]:
        """Record `call` and return the fixed response."""
        self.calls.append(call)
        return self.response


def test_a_rejection_moves_an_application_from_any_state() -> None:
    """Appendix B allows the rejection transition from every state, and the table must agree."""
    for state in ApplicationState:
        assert next_state(state, MessageLabel.REJECTION) is ApplicationState.REJECTED


def test_no_message_can_ever_produce_ghosted() -> None:
    """`GHOSTED` is derived from elapsed time, so no label may transition into it (Appendix B).

    An application already ghosted and left there is not a transition into `GHOSTED`, so the
    property is about arriving, not about staying.
    """
    for label in MessageLabel:
        for state in ApplicationState:
            if state is ApplicationState.GHOSTED:
                continue
            assert next_state(state, label) is not ApplicationState.GHOSTED


def test_a_label_with_no_transition_leaves_the_state_alone() -> None:
    """An unanticipated message must not move an application rather than guessing where to."""
    assert next_state(ApplicationState.SUBMITTED, MessageLabel.OFFER) is ApplicationState.SUBMITTED
    assert next_state(ApplicationState.ACKED, MessageLabel.IRRELEVANT) is ApplicationState.ACKED


def test_a_label_outside_the_closed_set_cannot_invent_a_state() -> None:
    """A model returning an unknown label is absorbed as irrelevant, not treated as a new class."""
    transport = _Recorder({"messages": [{"index": 0, "label": "promoted_to_ceo"}]})
    client = ModelClient(transport=transport, record=True, golden_root=None)
    reading = read_inbox(["congratulations"], client, ApplicationState.ACKED)
    assert reading.messages[0].label is MessageLabel.IRRELEVANT
    assert reading.final_state is ApplicationState.ACKED


def test_the_batch_is_one_call_and_the_text_stays_out_of_the_prompt() -> None:
    """Triage batches to protect the tier-1 allowance, and message text is data only (G7)."""
    transport = _Recorder({"messages": []})
    client = ModelClient(transport=transport, record=True, golden_root=None)
    bodies = ["zebra-alpha-marker", "quokka-beta-marker", "narwhal-gamma-marker"]
    read_inbox(bodies, client, ApplicationState.SUBMITTED)

    assert len(transport.calls) == 1, "a batch must cost one call, not one per message"
    call = transport.calls[0]
    assert call.tier is Tier.ONE
    for body in bodies:
        assert body not in call.prompt, "message text must travel as data, never as instruction"
    assert len(call.data["messages"]) == 3


def test_the_state_machine_walks_messages_in_order() -> None:
    """State is carried between messages, so a sequence lands where the table says it should."""
    transport = _Recorder(
        {
            "messages": [
                {"index": 0, "label": "acknowledgement"},
                {"index": 1, "label": "recruiter_contact"},
                {"index": 2, "label": "interview_scheduled"},
                {"index": 3, "label": "offer"},
            ]
        }
    )
    client = ModelClient(transport=transport, record=True, golden_root=None)
    reading = read_inbox(["a", "b", "c", "d"], client, ApplicationState.SUBMITTED)

    assert [m.state_after for m in reading.messages] == [
        ApplicationState.ACKED,
        ApplicationState.SCREEN,
        ApplicationState.ONSITE,
        ApplicationState.OFFER,
    ]
    assert reading.final_state is ApplicationState.OFFER
    assert all(m.moved for m in reading.messages)


def test_no_model_means_no_reading_rather_than_a_guess() -> None:
    """Without a model the system reports it read nothing, instead of inferring from keywords."""
    reading = read_inbox(["Unfortunately we will not be moving forward"], None)
    assert reading.used_model is False
    assert reading.messages == []


@pytest.mark.parametrize("label", list(MessageLabel))
def test_every_label_is_handled_by_the_table(label: MessageLabel) -> None:
    """Every member of the closed set resolves to a state, so none can raise at runtime."""
    assert isinstance(next_state(ApplicationState.ACKED, label), ApplicationState)
