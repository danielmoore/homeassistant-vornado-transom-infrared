# AGENTS.md

A Home Assistant custom integration (`vornado_transom_infrared`, distributed through Home Assistant's Marketplace) that controls a Vornado Transom window fan over IR through an HA `infrared` emitter entity.

## Project

- `docs/design.md` describes the fan's behavior and the design decisions, and `docs/signals.md` the IR protocol and hardware findings. Read the relevant one before changing behavior.
- Keep pure logic (`codes.py`, `payloads.py`, `planner.py`, `state.py`) free of HA and I/O so it can be tested without HA. Inject the clock, sleep and send functions.

## Commands

```sh
uv sync
uv run ruff check
uv run ruff format --check
uv run ty check
uv run pytest
```

Run all of them before finishing a change. CI also runs hassfest and HACS validation.

After changing `strings.json`, make the same change in `translations/en.json`. Tests load translations from `translations/en.json`, and the two files are kept identical.

## Python

- The minimum version is Python 3.14. Don't add workarounds for older versions.
- `except TypeA, TypeB:` without parentheses is valid.
- Annotations are evaluated lazily (PEP 649). Don't quote forward references or add `from __future__ import annotations`.

## Code style

- Keep diffs strictly minimal: do only what was asked. Mention other issues you notice instead of fixing them.
- Prefer composition and dependency injection for wiring collaborators. Inheritance is the right tool for variants of one build sequence: a base method the subclasses extend via `super()`, in preference to flags or branches.
- Prefer a plain function over a class when the object holds no state that outlives the call.
- Avoid conditionals that select behavior. A parameter that changes what a function does (a mode string, a type discriminator, an optional collaborator) should become one type per variant, chosen at the call site.
- Prefer a neutral value (`b""`, `[]`, a no-op implementation) over an `if` on the common path.
- Don't collapse a fixed set of distinct cases into a data table plus a loop. Call the function once per case with its arguments at the call site. Build-a-list-and-iterate is for homogeneous data of unknown length.
- Put behavior on the type that owns the data. A module-level helper whose only parameter is one object belongs as a method on that object.
- Keep the inputs an object was constructed with as attributes, so downstream code reads them from the object instead of re-deriving them.
- Mark overrides with `@override`.
- Minimize coupling: functions take only the values they use, not the object containing them. Don't reach through collaborators (`a.b.c`). Depend on the narrowest interface needed.
- Use common interfaces instead of union types and `isinstance` checks that drive behavior.

## Comments

- Comments are only for a non-obvious "why" (constraints, surprises, workarounds), in one short line where possible. Never restate the code.
- Don't describe the current state of things ("today", "currently", "for now") or justify a change by referencing what the code looked like before. Comments about planned or deferred expansions of scope are fine.
- Don't add section or divider comments.
- Don't leave comments about a test's pass/fail state. A TODO marking a failing test that needs fixing is fine.

## Home Assistant

- Integrations at Platinum or Gold on the Integration Quality Scale (see their `manifest.json`) are good examples to follow.
- Don't add defensive checks for fields already validated by action schemas and entity selection filters. Add guards only when data bypasses those validators.
- When validation guarantees a key exists, use `data["key"]` instead of `.get("key")` so contract violations surface.
- Keep `try` blocks as small as possible, and don't catch exceptions from functions that aren't expected to raise them.
- Don't pass `str(err)` as a translation placeholder of a translated exception (`HomeAssistantError`, `ServiceValidationError`, `ConfigEntryNotReady`, `UpdateFailed`). Use specific errors that can be translated.
- Asserts that exist only to narrow types go behind `if TYPE_CHECKING:`.
- Register actions that change configuration or have security implications with `async_register_admin_service`.
- Constants used by more than one module go in `const.py`. A constant only one module uses stays in that module. Tests don't count as a user. Never import a constant from one platform module into another.

## Testing

- Always add or update tests alongside behavior changes.
- Prefer dependency injection over monkeypatching. Add optional parameters to the code under test where needed.
- Test behavior, not implementation: don't re-encode the logic under test.
- Strongly avoid computing expected values in tests. Hard-code them in the test or in an adjacent metadata file.
- Annotate all test function parameters, with concrete types (`HomeAssistant`, `MockConfigEntry`) over `Any`.
- Prefer `@pytest.mark.usefixtures` over arguments the test doesn't use.
- Don't branch in tests. Split them or parametrize instead.
- When tests share most of their code, merge them with `pytest.mark.parametrize`, naming cases with `pytest.param(..., id=...)`.
- Hard-coded `entity_id`s are fine. Use a constant if the same one repeats.

## Code review

- Start review comments with a one-sentence summary of the suggested fix.
- Don't comment on style, formatting or linting. Tooling handles those.
- Flag comments that over-explain straightforward code or read like AI commentary.
- A dependency bump should contain only the changes the bump requires.

## Git

- Commit messages: short imperative subject, with a body explaining why when it isn't obvious.
- Never amend, squash, rebase or force-push already-pushed commits without asking.
- A human must review, understand and be able to explain every change. Don't open issues or pull requests, or post comments, without that review.
