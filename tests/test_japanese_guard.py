"""python3 tests/test_japanese_guard.py で実行する"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "japanese-guard.py"


def user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def tool_result():
    return {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": "ok"}]}}


def assistant(text):
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def run(entries, stop_hook_active=False):
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    payload = json.dumps({"transcript_path": f.name, "stop_hook_active": stop_hook_active})
    out = subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True, text=True, check=True)
    return json.loads(out.stdout) if out.stdout.strip() else None


EN = "The build finished successfully and all tests passed, so I will publish the page now."
JA = "ビルドが通り、テストもすべて成功したので、ページを公開します。"

cases = [
    ("英語の本文は差し戻す", [user("公開して"), assistant(EN)], False, True),
    ("日本語の本文は通す", [user("公開して"), assistant(JA)], False, False),
    ("途中の一言報告が英語でも差し戻す", [user("公開して"), assistant("Checking the build first."
        " Then I will run the whole test suite."), tool_result(), assistant(JA)], False, True),
    ("コードブロックの英語は数えない", [user("手順は？"), assistant("次のコマンドを実行します。\n```bash\n"
        "npm install && npm run build && npm test -- --coverage --watchAll=false\n```")], False, False),
    ("前のターンの英語は対象外", [user("a"), assistant(EN), user("b"), assistant(JA)], False, False),
    ("2回目は通す（無限ループ防止）", [user("公開して"), assistant(EN)], True, False),
    ("短い英語は見逃す", [user("いい？"), assistant("OK, done.")], False, False),
]

failed = 0
for name, entries, active, expect_block in cases:
    result = run(entries, active)
    blocked = bool(result and result.get("decision") == "block")
    ok = blocked == expect_block
    failed += not ok
    print(("✓ " if ok else "✗ ") + name)
sys.exit(1 if failed else 0)
