# How to Release

## 1. Create the release branch

```shell
# Ensure you're on `main` and are up-to-date
git checkout main
git pull

# Create the release branch
git checkout -b release/vX.Y.Z
```

## 2. Update the changelog

Add a new section to the changelog, including all the unreleased changes.

```markdown
## [X.Y.Z] - YYYY-MM-DD
```

Commit the changes:

```shell
git add CHANGELOG.md
git commit -m "Add changelog section for X.Y.Z"
```

## 3. Bump the version

```shell
# Bump the version
bump2version [major|minor|patch]
```

### 4. Push the release branch

```shell
# Push the release branch
git push -u origin release/vX.Y.Z
```

### 5. Create pull request and merge

_Done in GitHub UI_.

### 6. Tag the release

```shell
# Ensure you're on `main` and are up-to-date
git checkout main
git pull

# Tag the release
git tag -s vX.Y.Z -m "Release vX.Y.Z"

# Push the tag
git push origin vX.Y.Z
```

### 7. Update the release in GitHub

Copy the changes from the changelog for the release into the release notes in GitHub.

### 7. Publish to PyPI

_This is done automatically using [publish.yaml](.github/workflows/publish.yaml)_
