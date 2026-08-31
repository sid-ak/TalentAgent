"""Where a composed package is read from and a capture pointer is written back.

The durable store is Firestore, and its collections, rules, and emulator harness are issue #4. What
Phase 1 needs is the boundary, so the form worker is written against a protocol rather than against
whichever backend exists — and the local backend is a real implementation used by the fixture runs
and the gate, not a stub.

The single-writer invariant applies here: `packages` is written by the composer and by nothing else
(Spec 2.2). The form worker's write is the capture pointer on an existing package, which is why the
protocol exposes that as its own narrow method rather than a general update.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol, runtime_checkable

from talentagent.ats.package import ApplicationPackage


class PackageNotFound(KeyError):
    """Raised when no package exists for an application."""


@runtime_checkable
class PackageStore(Protocol):
    """Reads composed packages and records where their captures went."""

    def load(self, application_id: str) -> ApplicationPackage:
        """Return the composed package for `application_id`."""
        ...

    def record_capture(self, application_id: str, artifact: str, completion: float) -> None:
        """Note where the run artifact for `application_id` was retained, and how complete it is."""
        ...


class LocalPackageStore:
    """A filesystem-backed store, used by the fixture runs and the Spike A gate.

    Not a stub. It is the backend that makes the whole apply path runnable offline, which is what
    keeps the suite deterministic and free of API calls.
    """

    def __init__(self, root: Path) -> None:
        """Read and write packages under `root`."""
        self.root = root

    def _path(self, application_id: str) -> Path:
        """Return where `application_id`'s package lives."""
        return self.root / f"{application_id}.json"

    def save(self, application_id: str, package: ApplicationPackage) -> None:
        """Write a composed package. Stands in for the composer until issue #24."""
        self.root.mkdir(parents=True, exist_ok=True)
        self._path(application_id).write_text(package.model_dump_json(indent=2))

    def load(self, application_id: str) -> ApplicationPackage:
        """Return the composed package for `application_id`.

        Raises:
            PackageNotFound: if nothing has been composed for it.
        """
        path = self._path(application_id)
        if not path.exists():
            raise PackageNotFound(application_id)
        return ApplicationPackage.model_validate_json(path.read_text())

    def record_capture(self, application_id: str, artifact: str, completion: float) -> None:
        """Note where the run artifact went, so the review UI can link to it."""
        self.root.mkdir(parents=True, exist_ok=True)
        pointer = self.root / f"{application_id}.capture.json"
        pointer.write_text(
            json.dumps({"artifact": artifact, "completion": completion}, indent=2, sort_keys=True)
        )
