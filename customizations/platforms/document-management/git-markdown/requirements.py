"""Persist one approved design proposal under its stable request identity."""

import re


def save_requirement(root, request_id, title, digest, summary, legacy_summary):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", request_id):
        raise ValueError("Invalid requirement identity")
    document = "design-docs/" + request_id + ".md"
    prefix = "# " + title + "\n\n<!-- gonggong-request:" + request_id + " -->\n\n"
    prefix += "需求整理：Yanshi / ClarifyFeature；原始输入摘要：`" + digest + "`。\n\n"
    path = root / document
    path.parent.mkdir(exist_ok=True)
    if path.is_symlink():
        raise ValueError("Preserve existing requirement original; cannot write through a symlink")
    content = prefix + summary
    if path.exists() and path.read_text(encoding="utf-8") not in (
        content,
        prefix + legacy_summary,
    ):
        raise ValueError("Preserve existing requirement original; cannot overwrite a different proposal")
    if not path.exists():
        with path.open("x", encoding="utf-8") as stream:
            stream.write(content)
    return document
