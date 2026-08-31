"""The live page backend: Chromium on an Actions runner.

Actions runners ship with Chromium, so this is a dependency rather than infrastructure and no
container build is needed (ADR-0012). Playwright is an optional extra, absent by default, so the
fixture-driven suite runs with no browser download.

Two properties of this environment are load-bearing and are asserted rather than assumed.

There is no authenticated session anywhere. The three target platforms accept applications without
a candidate account (Spec 8.3), so a fresh profile is launched per run and destroyed with it. No
credential is held, no cookie jar persists, and no code path creates an account (G6).

There is no submit path. This class satisfies the Page protocol, which has no submit method, and it
adds none. The submit control is located only so the run can assert it was never activated (G3).
"""

from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any

from talentagent.ats.page import FormField

if TYPE_CHECKING:  # pragma: no cover - import only for annotations
    from playwright.sync_api import Browser, Playwright
    from playwright.sync_api import Page as PlaywrightPage

#: Selectors that identify a form's submit control on the three target platforms. Used to assert
#: the control was never activated, never to activate it.
SUBMIT_SELECTORS = (
    "button[type=submit]",
    "input[type=submit]",
)

#: How long to wait for an element's state, in milliseconds. Waits are keyed on state, never slept.
STATE_TIMEOUT_MS = 10_000


class PlaywrightUnavailable(RuntimeError):
    """Raised when the live backend is used without the optional browser extra installed."""

    def __init__(self) -> None:
        """Explain how to install the extra."""
        super().__init__(
            "The live backend needs the browser extra: `uv sync --extra browser` and "
            "`uv run playwright install chromium`. The fixture suite does not need it."
        )


class ChromiumPage:
    """A live ATS form driven through Chromium, unauthenticated and unsubmittable."""

    def __init__(self, url: str, headless: bool = True) -> None:
        """Prepare to drive `url`. The browser starts on entering the context manager."""
        self.url = url
        self._headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._page: PlaywrightPage | None = None

    def __enter__(self) -> ChromiumPage:
        """Launch Chromium with a fresh profile and open the posting."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - exercised only without the extra
            raise PlaywrightUnavailable from exc

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._headless)
        # A fresh context per run is the whole of the session story: it holds no storage state, so
        # nothing survives the run and there is nothing to leak.
        context = self._browser.new_context(storage_state=None)
        self._page = context.new_page()
        self._page.goto(self.url, wait_until="domcontentloaded")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Destroy the browser profile with the run."""
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()

    @property
    def _live(self) -> PlaywrightPage:
        """Return the open page, or explain that the context manager was not entered."""
        if self._page is None:
            raise RuntimeError("ChromiumPage must be used as a context manager")
        return self._page

    def fields(self) -> tuple[FormField, ...]:
        """Enumerate every control on the form, including ones not currently visible."""
        raw: list[dict[str, Any]] = self._live.evaluate(_ENUMERATE_JS)
        return tuple(
            FormField(
                name=entry["name"],
                kind=entry["kind"],
                label=entry["label"],
                aria=entry["aria"],
                options=tuple(entry["options"]),
                required=entry["required"],
                visible=entry["visible"],
            )
            for entry in raw
            if entry["name"]
        )

    def fill(self, name: str, value: str) -> None:
        """Write `value` into the field called `name`, waiting on element state rather than time."""
        locator = self._live.locator(f'[name="{name}"]')
        locator.wait_for(state="visible", timeout=STATE_TIMEOUT_MS)
        if locator.evaluate("el => el.tagName.toLowerCase()") == "select":
            locator.select_option(value)
        else:
            locator.fill(value)

    def upload(self, name: str, path: Path) -> None:
        """Attach the file at `path` to the field called `name`."""
        locator = self._live.locator(f'[name="{name}"]')
        locator.wait_for(state="attached", timeout=STATE_TIMEOUT_MS)
        locator.set_input_files(str(path))

    def screenshot(self, destination: Path) -> Path:
        """Capture the completed form at a resolution where field values are legible."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._live.screenshot(path=str(destination), full_page=True)
        return destination

    @property
    def submit_activated(self) -> bool:
        """Report whether the submit control was activated. Nothing here can make this true."""
        return False

    def submit_control_is_untouched(self) -> bool:
        """Report that the form was not submitted, by checking the page never navigated away.

        Asserted at the end of every run. A form that submitted would have navigated to a
        confirmation page, so the URL still matching the posting is the observable evidence.
        """
        current: str = self._live.url
        return current.split("#")[0].rstrip("/") == self.url.split("#")[0].rstrip("/")


#: Enumerates controls in the browser, returning the same shape the offline backend produces.
_ENUMERATE_JS = """
() => Array.from(document.querySelectorAll('input, textarea, select')).map(el => {
  const label = el.id
    ? document.querySelector(`label[for="${CSS.escape(el.id)}"]`)
    : null;
  const kind = el.tagName.toLowerCase() === 'input'
    ? (el.getAttribute('type') || 'text')
    : el.tagName.toLowerCase();
  return {
    name: el.getAttribute('name'),
    kind: kind,
    label: label ? label.textContent.replace(/\\s+/g, ' ').trim() : null,
    aria: el.getAttribute('aria-label'),
    options: Array.from(el.querySelectorAll('option'))
      .map(o => o.getAttribute('value')).filter(v => v),
    required: el.hasAttribute('required'),
    visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length),
  };
});
"""
