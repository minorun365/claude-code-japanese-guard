"""python3 tests/test_japanese_guard.py で実行する"""

import json
import os
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


def thinking(text, display="updates"):
    return {"type": "assistant", "thinkingDisplay": display,
            "message": {"role": "assistant", "content": [{"type": "thinking", "thinking": text}]}}


def wrap_up(recap, ask=None, actions=None):
    inp = {"recap": recap}
    if ask:
        inp["ask"] = ask
    if actions is not None:
        inp["actions"] = actions
    return {"type": "assistant", "message": {"role": "assistant", "content": [
        {"type": "tool_use", "name": "mcp__ccd_turn__wrap_up", "input": inp}]}}


def pre_tool_use(tool_name, tool_input):
    payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": tool_input})
    out = subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True, text=True, check=True)
    return json.loads(out.stdout) if out.stdout.strip() else None


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
EN_MID = ("I have finished reading the configuration files.\n"
          "Next I will update the build script, run the tests again, and report the results once everything passes.")
EN_ONE_LINE = "Register the page in the index after the existing entry, then publish it and check the build log."
JA_MID = "設定ファイルを読み終えました。次はビルドスクリプトを直して、テストを流し直します。"

cases = [
    ("英語の本文は差し戻す", [user("公開して"), assistant(EN)], False, True),
    ("日本語の本文は通す", [user("公開して"), assistant(JA)], False, False),
    ("ツール前の途中の一言が英語でも、最終回答が日本語なら通す", [user("公開して"), assistant("Checking the build first."
        " Then I will run the whole test suite."), tool_use(), tool_result(), assistant(JA)], False, False),
    ("ツール前の1行の前置きが英字60字を超えても、最終回答が日本語なら通す", [user("公開して"), assistant(EN_ONE_LINE),
        tool_use(), tool_result(), assistant(JA)], False, False),
    ("最後のツールより後の最終回答が英語なら差し戻す", [user("公開して"), assistant(JA), tool_use(), tool_result(),
        assistant(EN)], False, True),
    ("ツールを呼ばないターンで、英語の段落が混ざれば差し戻す", [user("公開して"), assistant(JA), assistant(EN)], False, True),
    ("コードブロックの英語は数えない", [user("手順は？"), assistant("次のコマンドを実行します。\n```bash\n"
        "npm install && npm run build && npm test -- --coverage --watchAll=false\n```")], False, False),
    ("Markdown のリンクは表示する文字も数えない", [user("資料は？"),
        assistant("参照: [Apple Developer Documentation](https://developer.apple.com/documentation/)")], False, False),
    ("前のターンの英語は対象外", [user("a"), assistant(EN), user("b"), assistant(JA)], False, False),
    ("2回目は通す（無限ループ防止）", [user("公開して"), assistant(EN)], True, False),
    ("短い英語は見逃す", [user("いい？"), assistant("OK, done.")], False, False),
    ("ツール間の長い途中報告が英語なら差し戻す", [user("公開して"), assistant(EN_MID), tool_use(), tool_result(),
        assistant(JA)], False, True),
    ("updates 表示の thinking に書いた途中報告が英語なら差し戻す", [user("公開して"), thinking(EN_MID), tool_use(),
        tool_result(), assistant(JA)], False, True),
    ("updates 表示の thinking でも日本語なら通す", [user("公開して"), thinking(JA_MID), tool_use(), tool_result(),
        assistant(JA)], False, False),
    ("updates 以外の thinking は数えない", [user("公開して"), thinking(EN_MID, display="summarized"), tool_use(),
        tool_result(), assistant(JA)], False, False),
    ("次の一手の箱が英語なら差し戻す", [user("公開して"), wrap_up(EN, "Should I publish it now?"), tool_result(),
        assistant("No response requested.")], False, True),
    ("次の一手の箱が日本語なら通す", [user("公開して"), wrap_up(JA, "公開しますか？",
        [{"label": "公開する"}]), tool_result(), assistant("（応答なし）")], False, False),
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
# 最終回答が JSON だけなら、機械が読む出力として通す
JSON_OUT = json.dumps({"status": "ok", "items": [{"title": "Weekly build report", "summary": EN}]})
for name, msg, expect_block in [
    ("最終回答が JSON だけなら通す", JSON_OUT, False),
    ("コードフェンスで囲んだ JSON も通す", "```json\n" + JSON_OUT + "\n```", False),
    ("JSON の前に英語の説明が付いていれば差し戻す", EN + "\n" + JSON_OUT, True),
    ("{ で始まっても JSON として読めなければ差し戻す", "{" + EN, True),
]:
    r = run([user("一覧を JSON で"), tool_use(), tool_result()], last_message=msg)
    ok = bool(r and r.get("decision") == "block") == expect_block
    failed += not ok
    print(("✓ " if ok else "✗ ") + name)
# JAPANESE_GUARD_DISABLE=1 なら何もしない
with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
    for e in [user("公開して"), assistant(EN)]:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
env = {**os.environ, "JAPANESE_GUARD_DISABLE": "1"}
out = subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"transcript_path": f.name,
                     "last_assistant_message": EN}), capture_output=True, text=True, check=True, env=env)
ok = not out.stdout.strip()
failed += not ok
print(("✓ " if ok else "✗ ") + "JAPANESE_GUARD_DISABLE=1 なら英語でも通す")
# PreToolUse：次の一手の箱は、画面に出る前に止める
checks = [
    ("PreToolUse：英語の箱は deny する", "mcp__ccd_turn__wrap_up",
     {"recap": EN, "ask": "Publish now?", "actions": [{"label": "Publish", "message": "Yes, go ahead."}]}, True),
    ("PreToolUse：ボタンが JSON 文字列で渡っても読む", "mcp__ccd_turn__wrap_up",
     {"recap": "公開の準備ができました。", "actions": json.dumps([{"label": "Go", "message": EN}])}, True),
    ("PreToolUse：日本語の箱は通す", "mcp__ccd_turn__wrap_up",
     {"recap": JA, "ask": "公開しますか？", "actions": [{"label": "公開する"}]}, False),
    ("PreToolUse：ほかのツールは見ない", "Bash", {"command": EN}, False),
]
for name, tool, inp, expect_deny in checks:
    r = pre_tool_use(tool, inp)
    denied = bool(r and r.get("hookSpecificOutput", {}).get("permissionDecision") == "deny")
    ok = denied == expect_deny
    failed += not ok
    print(("✓ " if ok else "✗ ") + name)
sys.exit(1 if failed else 0)
