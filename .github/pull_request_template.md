# Summary

<!-- What does this change and why? -->

## Checklist
- [ ] `pytest -q` passes
- [ ] `reelshelf build --config <dir>/config.toml --mock` still builds
- [ ] No secrets, keys, or personal paths added (kept in gitignored `.env` / `config.toml`)
- [ ] Docs updated if behaviour/usage changed
- [ ] If adding a provider: registered in the `__init__.py` factory and fails soft on errors
