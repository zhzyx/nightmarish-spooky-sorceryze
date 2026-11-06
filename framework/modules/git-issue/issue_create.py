"""Migration notice for installations with the legacy optional module path."""

if __name__ == "__main__":
    raise SystemExit(
        "The optional GitHub Issue adapter moved. From the installed workspace root, use "
        "customizations/platforms/work-management/github/git-issue/issue_create.py. "
        "Preview a new plan before selecting it for publication."
    )
