# Capturing and refreshing ATS fixtures

Spike A is the highest-risk work in the project, and it cannot be developed against live forms.
Every iteration would be a live request against a real employer's posting, and no two runs would be
comparable. These fixtures are what make Pass 2 deterministic and the 90% completion criterion
measurable rather than anecdotal.

## What is here today

Twelve forms, four per platform, plus one manifest per platform enumerating every field and the
package path it should resolve to.

| Variant | Why it exists |
|---|---|
| `plain.html` | The standard fields every posting on the platform shares. Where field maps succeed. |
| `file-upload.html` | The platform's own attachment control, which differs per platform. |
| `custom-questions.html` | Employer-authored questions. Where a map is supposed to fail visibly rather than guess. |
| `conditional.html` | Fields that appear only after an earlier answer, so the driver must re-enumerate. |

These are structural reproductions, authored against each platform's documented and observable field
naming conventions, not captures of any real employer's posting. That distinction is deliberate and
it has a cost: they are faithful to the naming schemes a field map keys on, which is what the
resolver is tested against, but they cannot surprise us the way a real page can. Replacing them with
real anonymised captures is worthwhile, and the procedure below is how.

The custom-question and conditional variants carry the property that actually matters. On all three
platforms, employer-authored questions are named by an index or an opaque identifier — Greenhouse's
`answers_attributes[n]`, Lever's `cards[<uuid>][fieldN]`, Ashby's bare UUIDs — and carry no
information a map could key on in advance. That is not a gap in the fixtures; it is the condition
ADR-0008 designed the bounded fallback for.

## Refreshing a fixture from a live page

1. `Save Page As… > Web Page, Complete` in a browser on a real posting: pulls the DOM and its
   assets so the form renders with the network disabled.
2. Delete every script, tracking pixel, and analytics tag: fixtures must render offline and must
   not attempt an outbound request when opened.
3. Replace all employer-identifying and personal content — company name, role, recruiter, any
   pre-filled value. The repository is public (Architecture 6.4), so nothing identifying may land.
4. Preserve exactly: every `name` attribute, every `<label for>` pairing, every `aria-label`, and
   the input types. These are what the field map keys on, so a fixture that tidies them is testing
   something the live page will not do.
5. Declare conditional behaviour with `data-shown-when="<field name>=<value>"` on both the field and
   its label. The offline backend reads this to reveal fields the way a live page does; a real
   capture will have the behaviour in stripped-out JavaScript, so it has to be restated.
6. Add the fields to that platform's `manifest.yaml`, giving each either a `path` or `unmapped: true`.
   A field in the fixture and absent from the manifest fails the manifest-coverage test.
7. Run `uv run pytest tests/ats -q` and check the completion figure did not move unexpectedly.

## The anonymisation check

`tests/fixtures/test_fixture_hygiene.py` scans the whole fixture tree for personal data on every
run: real-looking email addresses, phone numbers, and a denylist of identifying terms. It is a test
rather than a pre-commit hook so that it cannot be skipped.
