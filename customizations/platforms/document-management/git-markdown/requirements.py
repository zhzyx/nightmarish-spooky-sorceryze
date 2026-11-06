"""Persist one approved design proposal under its stable request identity."""

import re


def save_requirement(root, request_id, design, digest):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", request_id):
        raise ValueError("Invalid requirement identity")
    document = "design-docs/" + request_id + ".md"
    content = "# " + design["title"] + "\n\n<!-- gonggong-request:" + request_id + " -->\n\n"
    content += "需求整理：Yanshi / ClarifyFeature；原始输入摘要：`" + digest + "`。\n\n" + design["goal"] + "\n"
    for heading, key in [("范围", "scope"), ("验收条件", "acceptance"), ("待确认", "questions")]:
        content += "\n## " + heading + "\n\n" + "\n".join("- " + x for x in design[key]) + "\n"
    path = root / document
    path.parent.mkdir(exist_ok=True)
    if path.is_symlink() or (path.exists() and path.read_text(encoding="utf-8") != content):
        raise ValueError("Preserve existing requirement original; cannot overwrite a different proposal")
    if not path.exists():
        with path.open("x", encoding="utf-8") as stream:
            stream.write(content)
    return document
