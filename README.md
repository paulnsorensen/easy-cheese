# easy-cheese

A minimal GitHub CLI agent skill repository for experimenting with `gh skill`.

This repository uses the skill discovery conventions documented by `gh skill`:

- `skills/<name>/SKILL.md` for a top-level skill
- `skills/<scope>/<name>/SKILL.md` for a namespaced, hierarchical skill

## Skills

| Skill path | Display name | Purpose |
| --- | --- | --- |
| `skills/foo/SKILL.md` | `foo` | Defines the basic foo/bar/baz variable pattern. |
| `skills/foo/bar/SKILL.md` | `foo/bar` | Shows a hierarchical skill under the `foo` scope for `bar`. |
| `skills/foo/baz/SKILL.md` | `foo/baz` | Shows a second hierarchical skill under the `foo` scope for `baz`. |

## Preview or install

Preview a skill before installing it:

```sh
gh skill preview paulnsorensen/easy-cheese foo
gh skill preview paulnsorensen/easy-cheese skills/foo/bar
gh skill preview paulnsorensen/easy-cheese skills/foo/baz
```

Install a skill:

```sh
gh skill install paulnsorensen/easy-cheese foo
gh skill install paulnsorensen/easy-cheese skills/foo/bar
gh skill install paulnsorensen/easy-cheese skills/foo/baz
```

Use exact paths for hierarchical skills so the intended namespace is explicit.

## Validate for publishing

When using a GitHub CLI version that includes `gh skill`, validate locally with:

```sh
gh skill publish --dry-run
```

Publishing expects each `SKILL.md` to include YAML frontmatter with at least `name` and `description`, and the `name` must match its directory name.
