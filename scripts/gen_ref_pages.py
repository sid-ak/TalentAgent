"""Generate a reference page for every module in the package, at build time.

Discovery rather than a hand-maintained list, so a module added in a later phase appears in the
reference without anyone remembering to add it. That is the whole reason this is a script and not a
`nav` section: the reference should describe the package as it is, not as it was when someone last
updated the docs.

The pages are virtual. Nothing is written into `docs/`, so there is no generated tree to keep out
of version control or to fall out of step with the source.
"""

from pathlib import Path

import mkdocs_gen_files

#: Where the reference is rooted in the built site.
REFERENCE = Path("reference")

#: The package to document. Tests are deliberately excluded: their docstrings state what behaviour
#: they pin, which is worth reading in the test file next to the assertion rather than in a
#: reference.
PACKAGE = "talentagent"


def main() -> None:
    """Write one reference page per module, plus the nav that ties them together."""
    nav = mkdocs_gen_files.Nav()
    root = Path(__file__).parent.parent

    for path in sorted((root / PACKAGE).rglob("*.py")):
        module_path = path.relative_to(root).with_suffix("")
        doc_path = path.relative_to(root).with_suffix(".md")
        parts = tuple(module_path.parts)

        if parts[-1] == "__init__":
            # A package's own docstring becomes its section index, so clicking a folder in the nav
            # lands on something rather than on the first module inside it.
            parts = parts[:-1]
            doc_path = doc_path.with_name("index.md")
        elif parts[-1] == "__main__":
            continue

        nav[parts] = doc_path.as_posix()
        with mkdocs_gen_files.open(REFERENCE / doc_path, "w") as page:
            page.write(f"::: {'.'.join(parts)}\n")

        # Point "edit this page" at the source file rather than at a page that does not exist.
        mkdocs_gen_files.set_edit_path(REFERENCE / doc_path, Path("..") / path.relative_to(root))

    with mkdocs_gen_files.open(REFERENCE / "SUMMARY.md", "w") as summary:
        summary.writelines(nav.build_literate_nav())


main()
