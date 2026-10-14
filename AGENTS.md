# Repository Guidelines

## Project Structure & Module Organization

The root launcher is `main.py`, backed by `aerodoc_gui.py`, a PySide6 desktop interface that runs one automation at a time and streams output into a pipeline view.

- `aerodoc/modules/`: the tested Airbus, Boeing, MXI, Toolbox, and platform support modules.
- `aerodoc_config.example.json`: GUI configuration template.
- `boeing_config.example.ini` and `mxi_config.example.ini`: optional direct execution templates.
- `downloads/`: local PDF output; `logs/`: runtime logs.

The old notebook based subprojects and the applicability module were removed. Keep new functionality in the consolidated root project and avoid creating parallel module folders.

## Build, Test, and Development Commands

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
python main.py
```

The GUI saves user configuration locally and runs browsers in the background. For syntax validation, run `python -m py_compile aerodoc_gui.py aerodoc/modules/*.py`. Direct module debugging requires running from `aerodoc/modules/` so local imports resolve.

## Coding Style & Naming Conventions

Use Python 3.10+ and four spaces per indentation level. Use `snake_case` for functions and variables, `UPPER_SNAKE_CASE` for constants, and descriptive Portuguese or domain specific names. Keep credentials and environment specific values outside source code.

## Testing Guidelines

There is no configured test framework or coverage threshold. Validate automation changes with a single PN and inspect the GUI pipeline, MFA status, logs, and downloaded PDF. Do not place real credentials, tokens, or private URLs in fixtures or examples.

## Commit & Pull Request Guidelines

Keep commits focused and describe the user visible change. Pull requests should identify the affected module, configuration changes, manual validation performed, and any required browser, network, or MFA setup. Include screenshots or log excerpts when they clarify a UI or workflow change.

## Security & Configuration Tips

Never commit passwords, service account files, tokens, private spreadsheet URLs, PDFs, logs, or browser profiles. Use the ignored local files `aerodoc_config.json`, `mxi_config.ini`, and `boeing_config.ini` only on the user’s machine. MFA and authenticated browser sessions must remain local and manual.
