import os
import datetime


DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")
CHANGELOG = os.path.join(DOCS_DIR, "CHANGELOG.md")
NEXT_STEPS = os.path.join(DOCS_DIR, "NEXT_STEPS.md")


def append_changelog(summary: str) -> None:
    os.makedirs(DOCS_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(CHANGELOG, "a", encoding="utf-8") as f:
        f.write(f"\n### [{ts}] 更新\n- {summary}\n")


def append_next_step(item: str) -> None:
    os.makedirs(DOCS_DIR, exist_ok=True)
    line = f"- {item}\n"
    if not os.path.exists(NEXT_STEPS):
        with open(NEXT_STEPS, "w", encoding="utf-8") as f:
            f.write("# 下一步计划（Backlog）\n\n")
    with open(NEXT_STEPS, "a", encoding="utf-8") as f:
        f.write(line)

