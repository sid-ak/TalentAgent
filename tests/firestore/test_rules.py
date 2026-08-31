"""Security rules assertions against the local Firestore emulator (Spec §11, ADR-0012).

Tests assert write ownership per component claim and verify that the `outcomes` collection is
strictly append-only (updates and deletes denied for all principals).
"""

import pytest
from talentagent.state.documents import (
    APPLICATIONS,
    ASSIGNMENT_RULES,
    EVIDENCE_GRAPH,
    HYPOTHESES,
    OUTCOMES,
    PACKAGES,
)

from tests.firestore.emulator import EmulatorClient, get_emulator_host

pytestmark = pytest.mark.network


@pytest.fixture
def emulator() -> EmulatorClient:
    """Return an EmulatorClient or skip the test if FIRESTORE_EMULATOR_HOST is unset."""
    host = get_emulator_host()
    if not host:
        pytest.skip(
            "FIRESTORE_EMULATOR_HOST is unset; rules tests run under firebase emulators:exec"
        )
    client = EmulatorClient(host=host)
    client.clear()
    return client


def test_write_ownership_per_collection(emulator: EmulatorClient) -> None:
    """Each collection permits writes only from its designated owner component."""
    # 1. applications (owner: pipeline)
    status_pipe, _ = emulator.create_document(
        APPLICATIONS, "app_1", {"state": "DISCOVERED"}, component="pipeline"
    )
    assert status_pipe == 200

    status_comp, _ = emulator.create_document(
        APPLICATIONS, "app_2", {"state": "DISCOVERED"}, component="composer"
    )
    assert status_comp == 403

    # 2. packages (owner: composer)
    status_comp_pkg, _ = emulator.create_document(
        PACKAGES, "pkg_1", {"posting_id": "job_1"}, component="composer"
    )
    assert status_comp_pkg == 200

    status_pipe_pkg, _ = emulator.create_document(
        PACKAGES, "pkg_2", {"posting_id": "job_2"}, component="pipeline"
    )
    assert status_pipe_pkg == 403

    # 3. evidence_graph (owner: evidence)
    status_ev, _ = emulator.create_document(
        EVIDENCE_GRAPH, "acc_1", {"claim": "A claim", "evidence": ["art_1"]}, component="evidence"
    )
    assert status_ev == 200

    status_ev_empty, _ = emulator.create_document(
        EVIDENCE_GRAPH, "acc_bad", {"claim": "A claim", "evidence": []}, component="evidence"
    )
    assert status_ev_empty == 403

    status_ev_other, _ = emulator.create_document(
        EVIDENCE_GRAPH, "acc_2", {"claim": "A claim", "evidence": ["art_1"]}, component="analyst"
    )
    assert status_ev_other == 403

    # 4. hypotheses & assignment_rules (owner: analyst)
    status_hyp, _ = emulator.create_document(
        HYPOTHESES, "hyp_1", {"statement": "A hypothesis"}, component="analyst"
    )
    assert status_hyp == 200

    status_hyp_bad, _ = emulator.create_document(
        HYPOTHESES, "hyp_2", {"statement": "A hypothesis"}, component="pipeline"
    )
    assert status_hyp_bad == 403

    status_rule, _ = emulator.create_document(
        ASSIGNMENT_RULES, "rule_1", {"strategy": "epsilon"}, component="analyst"
    )
    assert status_rule == 200

    status_rule_bad, _ = emulator.create_document(
        ASSIGNMENT_RULES, "rule_2", {"strategy": "epsilon"}, component="composer"
    )
    assert status_rule_bad == 403


def test_outcomes_append_only_rules(emulator: EmulatorClient) -> None:
    """Outcomes collection permits create for pipeline, but update and delete are refused."""
    # Create allowed for pipeline
    status_create, _ = emulator.create_document(
        OUTCOMES, "out_1", {"event": "screen_scheduled", "outcome": "pass"}, component="pipeline"
    )
    assert status_create == 200

    # Create denied for composer
    status_create_bad, _ = emulator.create_document(
        OUTCOMES, "out_2", {"event": "screen_scheduled"}, component="composer"
    )
    assert status_create_bad == 403

    # Update denied for pipeline
    status_update_pipe, _ = emulator.update_document(
        OUTCOMES, "out_1", {"outcome": "fail"}, component="pipeline"
    )
    assert status_update_pipe == 403

    # Update denied for analyst
    status_update_analyst, _ = emulator.update_document(
        OUTCOMES, "out_1", {"outcome": "fail"}, component="analyst"
    )
    assert status_update_analyst == 403

    # Delete denied for pipeline
    status_del_pipe, _ = emulator.delete_document(OUTCOMES, "out_1", component="pipeline")
    assert status_del_pipe == 403

    # Delete denied for analyst
    status_del_analyst, _ = emulator.delete_document(OUTCOMES, "out_1", component="analyst")
    assert status_del_analyst == 403
