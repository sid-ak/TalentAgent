"""What a form looks like to the resolver, independent of what is rendering it.

Pass 2 is specified as running against fixtures first with no model, and then live (Spec 13.3). That
only works if the resolution and fill logic does not know which of the two it is driving, so both
backends satisfy one protocol: an offline HTML page for the deterministic suite, and Chromium for
the live run.

The protocol has no method that submits. That is not an omission to be tidied up later — it is G3
expressed as an absence, and issue #14's driver keeps it that way.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class FormField:
    """One control on a form, as the resolver sees it.

    Attributes:
        name: The platform's own identifier for the field, and the most stable identity available.
        label: The text of the `<label for>` bound to it, if there is one.
        aria: Its `aria-label`, which is sometimes the only label Ashby gives a control.
        kind: The input kind, deciding which fill primitive applies.
        options: Permitted values for a select or radio group, so a fill cannot invent one.
        required: Whether the platform marks it required.
        visible: Whether it is currently shown. Conditional fields start hidden.
    """

    name: str
    kind: str
    label: str | None = None
    aria: str | None = None
    options: tuple[str, ...] = ()
    required: bool = False
    visible: bool = True

    @property
    def is_upload(self) -> bool:
        """Report whether this control takes a file rather than a value."""
        return self.kind == "file"


@dataclass
class FilledValue:
    """A value written into a field, retained so the capture can report what was actually put where.

    Attributes:
        name: The field it went into.
        value: What was written. For an upload this is the file's path.
        source: Where it came from — a package path, or `fallback` for a model-answered field.
    """

    name: str
    value: str
    source: str


@runtime_checkable
class Page(Protocol):
    """A form that can be enumerated and filled, but never submitted."""

    def fields(self) -> tuple[FormField, ...]:
        """Return every control on the form, including ones that are not currently visible."""
        ...

    def fill(self, name: str, value: str) -> None:
        """Write `value` into the field called `name`."""
        ...

    def upload(self, name: str, path: Path) -> None:
        """Attach the file at `path` to the field called `name`."""
        ...

    def screenshot(self, destination: Path) -> Path:
        """Render the completed form to `destination` and return the path."""
        ...

    @property
    def submit_activated(self) -> bool:
        """Report whether the form's submit control was ever activated. Must stay false (G3)."""
        ...


@dataclass
class FillLog:
    """What a run did to a page, in the order it did it."""

    values: list[FilledValue] = field(default_factory=list)

    def record(self, name: str, value: str, source: str) -> None:
        """Note that `value` was written into `name` from `source`."""
        self.values.append(FilledValue(name=name, value=value, source=source))
