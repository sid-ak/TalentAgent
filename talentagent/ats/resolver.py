"""Resolving a form's fields against a field map and a package.

The resolver never raises on a miss. A field it cannot fill produces a typed result naming the
field and the reason, because the completion figure the Spike A gate is measured against is built
from those reasons — and a silent skip would inflate it.
"""

from __future__ import annotations

from dataclasses import dataclass

from talentagent.ats.fieldmap import FieldMap, MissReason
from talentagent.ats.package import ApplicationPackage
from talentagent.ats.page import FormField


@dataclass(frozen=True)
class Resolved:
    """A field the map resolved to a value.

    Attributes:
        field: The control.
        value: What to write, already stringified for the fill primitive.
        path: The package path it came from, retained so the capture can show provenance.
    """

    field: FormField
    value: str
    path: str

    @property
    def name(self) -> str:
        """Return the field's name."""
        return self.field.name


@dataclass(frozen=True)
class Missed:
    """A field the map did not resolve, and why.

    Attributes:
        field: The control.
        reason: Which kind of miss this is; they are counted separately.
        detail: What a reviewer needs to understand it without opening the map.
    """

    field: FormField
    reason: MissReason
    detail: str = ""

    @property
    def name(self) -> str:
        """Return the field's name."""
        return self.field.name

    @property
    def eligible_for_fallback(self) -> bool:
        """Report whether the bounded model fallback may touch this field.

        Only a field no rule matched is eligible. A field the map recognised and declined — a
        demographic question, say — stays declined, and one that is merely invisible or has no
        value in the package is not a question the model can answer either.
        """
        return self.reason is MissReason.NO_RULE


@dataclass(frozen=True)
class Resolution:
    """Everything the resolver concluded about one form."""

    resolved: tuple[Resolved, ...]
    missed: tuple[Missed, ...]

    @property
    def total(self) -> int:
        """Return how many fields were considered."""
        return len(self.resolved) + len(self.missed)

    def misses_by_reason(self, reason: MissReason) -> tuple[Missed, ...]:
        """Return the misses of one kind."""
        return tuple(m for m in self.missed if m.reason is reason)

    @property
    def fallback_candidates(self) -> tuple[Missed, ...]:
        """Return the misses the bounded model fallback is permitted to attempt."""
        return tuple(m for m in self.missed if m.eligible_for_fallback)


def _stringify(value: object) -> str:
    """Render a package value as the string a form field takes."""
    return str(value)


def resolve(
    fields: tuple[FormField, ...],
    field_map: FieldMap,
    package: ApplicationPackage,
    *,
    include_hidden: bool = False,
) -> Resolution:
    """Resolve every field on a form against the map and the package.

    Args:
        fields: The controls enumerated from the page.
        field_map: The platform's map.
        package: The composed package supplying values.
        include_hidden: Whether to attempt fields that are not currently visible. False during a
            pass, because a conditional field must be revealed by an earlier answer first.

    Returns:
        A Resolution carrying one entry per field, resolved or missed.
    """
    resolved: list[Resolved] = []
    missed: list[Missed] = []

    for form_field in fields:
        if not form_field.visible and not include_hidden:
            missed.append(
                Missed(form_field, MissReason.NOT_VISIBLE, "hidden until an earlier answer")
            )
            continue

        rule = field_map.rule_for(form_field.name, form_field.label, form_field.aria)
        if rule is None:
            missed.append(
                Missed(form_field, MissReason.NO_RULE, "no rule in the map matched this field")
            )
            continue
        if rule.unmapped:
            missed.append(
                Missed(
                    form_field,
                    MissReason.DECLARED_UNMAPPED,
                    rule.note or "the map declines this field deliberately",
                )
            )
            continue

        assert rule.path is not None
        value = package.resolve_path(rule.path)
        if value is None or value == "":
            missed.append(
                Missed(form_field, MissReason.NO_VALUE, f"package has no value at {rule.path}")
            )
            continue
        resolved.append(Resolved(form_field, _stringify(value), rule.path))

    return Resolution(resolved=tuple(resolved), missed=tuple(missed))
