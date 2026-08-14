# Geneweaver Documentation

[![Static Badge](https://img.shields.io/badge/license-apache--2.0-97CA00?style=for-the-badge)](https://github.com/TheJacksonLaboratory/geneweaver/blob/main/LICENSE)
[![Built with Material for MkDocs](https://img.shields.io/badge/Material_for_MkDocs-526CFE?style=for-the-badge&logo=MaterialForMkDocs&logoColor=white)](https://squidfunk.github.io/mkdocs-material/)

[![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/TheJacksonLaboratory/geneweaver/docs-pull_requests.yml?branch=main&event=push&style=for-the-badge&label=MkDocs%20Build)](https://github.com/TheJacksonLaboratory/geneweaver/actions/workflows/docs-pull_requests.yml)

This directory contains the central documentation site for the GeneWeaver project.
Geneweaver is a web-based software tool for the integration of functional genomics data.
The Geneweaver web application is available at [Geneweaver.org](https://geneweaver.org).

The documentation is built using [MkDocs](https://www.mkdocs.org/) and
[Material for MkDocs](https://squidfunk.github.io/mkdocs-material/),
and is hosted on [GitHub Pages](https://pages.github.com/).

!!! note "This used to be its own repository"

    The docs previously lived in `TheJacksonLaboratory/geneweaver-docs`, which is
    being archived. The site is now built and published from this monorepo by
    `.github/workflows/docs-release.yml`. The old site remains served read-only at
    its original URL but no longer receives updates.

## Getting Started

The docs live in the [GeneWeaver monorepo](https://github.com/TheJacksonLaboratory/geneweaver),
alongside the API, UI, packages, and legacy application:

```bash
git clone git@github.com:TheJacksonLaboratory/geneweaver.git
cd geneweaver
```

Dependencies are managed with [uv](https://docs.astral.sh/uv/). The documentation
toolchain is in its own dependency group, so you do not need the rest of the
project's dependencies to work on the docs:

```bash
uv sync --only-group docs
```

To preview the site locally with live reload at http://localhost:8000/:

```bash
uv run --only-group docs mkdocs serve
```

To build the site the way CI does — `--strict` turns broken links and pages
missing from the nav into errors, so run this before opening a pull request:

```bash
uv run --only-group docs mkdocs build --strict
```

## Layout

* `mkdocs.yml` — site configuration and navigation, at the repository root.
* `docs/` — the site sources. Pages added here must be added to the `nav` in
  `mkdocs.yml`, or the strict build will fail.
* `docs/assets/` — images and other static files. Reference them relative to the
  page, for example `../assets/images/example.png`.

Some directories under `docs/` are internal engineering notes rather than user
documentation — `ci-cd/`, `tools/`, `ui/`, and this README. They are listed under
`exclude_docs` in `mkdocs.yml` and are deliberately not published.

## Contributing

If you notice any errors or omissions in the documentation, please feel free to submit a
pull request with your changes. We welcome contributions from the community!

Pull requests that touch `docs/`, `mkdocs.yml`, or the docs workflows run a strict
MkDocs build via `.github/workflows/docs-pull_requests.yml`. Merges to `main` publish
the site via `.github/workflows/docs-release.yml`.
