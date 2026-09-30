"""python3 tests/test_japanese_guard.py で実行する"""

import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "japanese-guard.py"


def user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def tool_result():
    return {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result", "content": "ok"}]}}


def assistant(text):
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": text}]}}


def tool_use():
    return {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "tool_use", "name": "Bash", "input": {}}]}}


def run(entries, stop_hook_active=False, last_message=None):
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    data = {"transcript_path": f.name, "stop_hook_active": stop_hook_active}
    if last_message is not None:
        data["last_assistant_message"] = last_message
    payload = json.dumps(data)
    out = subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True, text=True, check=True)
    return json.loads(out.stdout) if out.stdout.strip() else None


EN = "The build finished successfully and all tests passed, so I will publish the page now."
JA = "ビルドが通り、テストもすべて成功したので、ページを公開します。"

cases = [
    ("英語の本文は差し戻す", [user("公開して"), assistant(EN)], False, True),
    ("日本語の本文は通す", [user("公開して"), assistant(JA)], False, False),
    ("ツール前の途中の一言が英語でも、最終回答が日本語なら通す", [user("公開して"), assistant("Checking the build first."
        " Then I will run the whole test suite."), tool_use(), tool_result(), assistant(JA)], False, False),
    ("最後のツールより後の最終回答が英語なら差し戻す", [user("公開して"), assistant(JA), tool_use(), tool_result(),
        assistant(EN)], False, True),
    ("ツールを呼ばないターンで、英語の段落が混ざれば差し戻す", [user("公開して"), assistant(JA), assistant(EN)], False, True),
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
# 最終回答が hook の起動より遅れて書き込まれても、待ってから判定する
with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
    for e in [user("公開して"), tool_use(), tool_result()]:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
late = json.dumps(assistant(EN), ensure_ascii=False) + "\n"
threading.Timer(0.5, lambda: open(f.name, "a", encoding="utf-8").write(late)).start()
out = subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"transcript_path": f.name}),
                     capture_output=True, text=True, check=True)
ok = bool(out.stdout.strip()) and json.loads(out.stdout).get("decision") == "block"
failed += not ok
print(("✓ " if ok else "✗ ") + "最終回答の書き込みが遅れても、英語なら差し戻す")
# last_assistant_message だけに最終回答がある（transcript にまだ書き込まれていない）とき
import time
t0 = time.time()
r = run([user("公開して"), tool_use(), tool_result()], last_message=EN)
ok = bool(r and r.get("decision") == "block") and time.time() - t0 < 2
failed += not ok
print(("✓ " if ok else "✗ ") + "last_assistant_message が英語なら、transcript を待たずに差し戻す")
r = run([user("公開して"), assistant(JA)], last_message=JA)
ok = r is None
failed += not ok
print(("✓ " if ok else "✗ ") + "last_assistant_message が日本語なら通す")
r = run([user("公開して"), assistant(EN), assistant(JA)], last_message=JA)
ok = bool(r and r.get("decision") == "block")
failed += not ok
print(("✓ " if ok else "✗ ") + "last_assistant_message が日本語でも、分かれた前半が英語なら transcript 側で差し戻す")
sys.exit(1 if failed else 0)
