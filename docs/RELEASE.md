# Release Process

Use this process for every public version. Tags identify the exact Git commit; GitHub Releases make that version visible and understandable to users.

## Checklist

1. Update all version surfaces listed in `AGENTS.md`.
2. Move completed release notes from `[Unreleased]` into a dated `## [x.y.z] - YYYY-MM-DD` changelog section.
3. Run backend and frontend verification.
4. Commit the release changes.
5. Create an annotated tag:
   ```bash
   git tag -a vx.y.z -m "Release x.y.z"
   ```
6. Push the branch and tag:
   ```bash
   git push origin main --follow-tags
   ```
7. Create or update the GitHub Release from the tag:
   ```bash
   VERSION=x.y.z
   NOTES=$(awk -v version="$VERSION" 'index($0, "## [" version "] - ") == 1 {flag=1; next} flag && /^## \\[/{exit} flag {print}' CHANGELOG.md | sed '1{/^$/d;}')
   gh release create "v$VERSION" --title "The AI Counsel v$VERSION" --notes "$NOTES" --latest
   ```

If the release already exists, use:

```bash
gh release edit "v$VERSION" --title "The AI Counsel v$VERSION" --notes "$NOTES" --latest
```

## Rules

- Use GitHub Releases for every user-facing version, not tags alone.
- Mark stable releases as `--latest`.
- Use `--prerelease` only for versions users should not treat as current.
- Release notes should come from the matching `CHANGELOG.md` section.
- Do not push a release tag before the version surfaces and changelog are committed.
