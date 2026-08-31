"""The offline page backend: a real DOM, no browser, no network.

Pass 2 is specified as running against fixtures first with no model, then live (Spec 13.3). This is
the first half. It parses a fixture with lxml and holds field values in memory, which makes the
whole resolution and fill path deterministic and runnable in CI with no browser download — the
thing that lets the Spike A completion figure be a number rather than an anecdote.

Conditional fields are declared in the fixtures with `data-shown-when="<name>=<value>"`. A live page
implements the same behaviour in JavaScript this backend does not run, so the attribute restates it
declaratively and the driver has to re-enumerate after each interaction either way.
"""

from __future__ import annotations

from pathlib import Path

from lxml import html as lxml_html

from talentagent.ats.page import FormField

_VALUE_KINDS = frozenset({"text", "email", "tel", "url", "number", "date", "textarea", "select"})
"""Input types that carry a value the resolver can write into."""


class UnknownField(KeyError):
    """Raised when a fill targets a field the page does not have."""


class SubmitAttempted(AssertionError):
    """Raised if anything tries to activate the form's submit control.

    This backend cannot submit — there is no network and no handler. The exception exists so that a
    test can prove the attempt would have been caught rather than silently doing nothing (G3).
    """


class OfflineHtmlPage:
    """A fixture form, enumerable and fillable in memory."""

    def __init__(self, source: Path) -> None:
        """Parse the fixture at `source`."""
        self.source = source
        self._tree = lxml_html.fromstring(source.read_text())
        self._values: dict[str, str] = {}
        self._uploads: dict[str, Path] = {}
        self._submit_activated = False

    # -- enumeration ---------------------------------------------------------------------------

    def _label_for(self, element: lxml_html.HtmlElement) -> str | None:
        """Return the text of the `<label for>` bound to `element`, if there is one."""
        element_id = element.get("id")
        if not element_id:
            return None
        for label in self._tree.iter("label"):
            if label.get("for") == element_id:
                text = lxml_html.HtmlElement.text_content(label)
                return " ".join(str(text).split())
        return None

    def _is_visible(self, element: lxml_html.HtmlElement) -> bool:
        """Report whether `element` is currently shown.

        A field carrying `data-shown-when` is hidden until the field it names holds the value it
        names. That is the fixture's declaration of conditional behaviour.
        """
        condition: str | None = element.get("data-shown-when")
        if condition is None:
            return element.get("hidden") is None
        name, _, expected = condition.partition("=")
        return self._values.get(name) == expected

    def fields(self) -> tuple[FormField, ...]:
        """Return every control on the form, visible or not."""
        found: list[FormField] = []
        for element in self._tree.iter("input", "textarea", "select"):
            name = element.get("name")
            if not name:
                continue
            tag = element.tag
            kind = element.get("type", "text") if tag == "input" else tag
            if kind not in _VALUE_KINDS and kind != "file":
                continue
            options = tuple(
                option.get("value", "") for option in element.iter("option") if option.get("value")
            )
            found.append(
                FormField(
                    name=name,
                    kind=kind,
                    label=self._label_for(element),
                    aria=element.get("aria-label"),
                    options=options,
                    required=element.get("required") is not None,
                    visible=self._is_visible(element),
                )
            )
        return tuple(found)

    # -- interaction ---------------------------------------------------------------------------

    def _element(self, name: str) -> lxml_html.HtmlElement:
        """Return the element called `name`.

        Raises:
            UnknownField: if the page has no such field.
        """
        for element in self._tree.iter("input", "textarea", "select"):
            if element.get("name") == name:
                return element
        raise UnknownField(name)

    def fill(self, name: str, value: str) -> None:
        """Write `value` into the field called `name`.

        Raises:
            UnknownField: if the field does not exist.
            ValueError: if the field is a select and `value` is not one of its options, so a fill
                cannot invent a value the platform will reject.
        """
        element = self._element(name)
        options = [o.get("value", "") for o in element.iter("option") if o.get("value")]
        if element.tag == "select" and value not in options:
            raise ValueError(f"{value!r} is not an option for {name!r}; options are {options}")
        self._values[name] = value
        element.set("value", value)

    def upload(self, name: str, path: Path) -> None:
        """Attach the file at `path` to the field called `name`."""
        element = self._element(name)
        if element.get("type") != "file":
            raise ValueError(f"{name!r} is not a file control")
        self._uploads[name] = path
        self._values[name] = path.name
        element.set("value", path.name)

    def activate_submit(self) -> None:
        """Refuse to submit.

        Present so a test can assert the refusal, rather than relying on the absence of a method.
        """
        raise SubmitAttempted("Pass 2 has no submit path; submission is human-only (G3).")

    # -- output --------------------------------------------------------------------------------

    def screenshot(self, destination: Path) -> Path:
        """Write the filled DOM to `destination`.

        Offline this is the rendered HTML rather than an image. It serves the same purpose — a
        reviewer can open it and read every value that was written — and the Chromium backend
        produces a real image for the live runs.
        """
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(lxml_html.tostring(self._tree, pretty_print=True))
        return destination

    @property
    def submit_activated(self) -> bool:
        """Report whether the submit control was ever activated. Always false here."""
        return self._submit_activated

    @property
    def values(self) -> dict[str, str]:
        """Return everything written into the form, for assertions and for the capture."""
        return dict(self._values)

    @property
    def uploads(self) -> dict[str, Path]:
        """Return every file attached, keyed by field name."""
        return dict(self._uploads)
