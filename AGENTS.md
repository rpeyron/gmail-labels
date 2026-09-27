# AGENTS.md

Guidance for AI agents (and contributors) working on this repository.

## Project

Gmail Label Manager — a Vite + React + TypeScript app for safely previewing and applying Gmail label operations. 

## Requirements

- **Functional** (what the product must do): [doc/requirements-functional.md](.github/requirements-functional.md)
- **Technical** (stack, architecture, commands, tests): [doc/requirements-technical.md](.github/requirements-technical.md)

Functional requirements own behavior; technical requirements own implementation constraints. When the two or the code disagree, flag it rather than silently choosing one.


## Definition of done

- `npm run build` and `npm test` pass.
- Update tests alongside behavior changes (only when asked for behaviour changes, not only to make tests pass).
- Requirements files and README updated if behavior changed.
- Never leave a edit failed, solve it before continuing.
