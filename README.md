# Kindle Highlights --- Obsidian Vault

One Markdown note per book, with Obsidian-friendly YAML metadata and
thematic tags.

## Structure

-   `Books/` --- one note per book
-   `Index.md` --- links to all books
-   `Templates/Book Highlights.md` --- template for future books
-   `.gitignore` --- excludes machine-specific Obsidian files

## Git workflow

``` bash
git init
git add .
git commit -m "Initial Kindle highlights"
git branch -M main
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```

For later changes:

``` bash
git add .
git commit -m "Add new Kindle highlights"
git push
```

Dates, locations, and page numbers from Kindle are intentionally
omitted. Bookmarks are omitted; highlights and Kindle notes are retained
when present.
