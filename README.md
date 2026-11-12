# 日本語でおｋ

Claude Code の応答が英語に切り替わったとき、日本語で書き直させる Stop hook です。

Claude Opus 5.5 を使っていると、日本語で指示していても、長い作業のあとや英語のツール出力を読んだ直後に、報告が英語で返ってくることがあります。CLAUDE.md に「日本語で応答する」と書いても防げなかったので、ターンの終わりに本文を機械で検査する hook を作りました。

## 仕組み

ターンの終わりに、そのターンで Claude が書いた本文の英字と日本語の文字数を数えます。英字が日本語の3倍を超えていたら終了を止めて、日本語で書き直すよう差し戻します。差し戻しは1ターンに1回までなので、書き直しがまた英語でもそこで終わります。

検査するのは次の3つです。

- 最後のツール呼び出しより後に書いた最終回答
- ツール呼び出しの間の途中報告のうち、複数行のものと長い段落
- デスクトップアプリの「次の一手」の箱（`wrap_up` ツール）のまとめ・質問・ボタン

コードブロック、インラインコード、URL、Markdown のリンクは数えないので、英語のコマンドや英文の下書きを見せる応答は差し戻されません。英字25文字未満の短い返事と、JSON だけの回答も対象外です。

## セットアップ

Claude Code にこのリポジトリの URL を渡して頼めば入ります。

> https://github.com/minorun365/claude-code-japanese-guard これ設定しといて

以下は、そのときに Claude Code が従う手順です。手で入れるときも同じです。

1. hook を置いて、実行権限を付けます。

   ```bash
   mkdir -p ~/.claude/hooks
   curl -fsSL https://raw.githubusercontent.com/minorun365/claude-code-japanese-guard/main/hooks/japanese-guard.py -o ~/.claude/hooks/japanese-guard.py
   chmod +x ~/.claude/hooks/japanese-guard.py
   ```

2. `~/.claude/settings.json` の `hooks.Stop` と `hooks.PreToolUse` の配列に、次を1件ずつ足します。既存の設定は残し、同じ `command` が登録済みならその配列には足しません。

   `hooks.Stop`：

   ```json
   { "hooks": [ { "type": "command", "command": "~/.claude/hooks/japanese-guard.py" } ] }
   ```

   `hooks.PreToolUse`（「次の一手」の箱を、画面に出る前に止めます）：

   ```json
   { "matcher": "mcp__.*__wrap_up", "hooks": [ { "type": "command", "command": "~/.claude/hooks/japanese-guard.py" } ] }
   ```

   matcher を `wrap_up` だけにすると完全一致として扱われ、実際のツール名に当たらないので、この形のまま使ってください。権限の都合で書き換えが止められたら、足す内容をユーザーに見せて、手で足してもらってください。

3. 設定ファイルが JSON として読めることと、hook がエラーなく動くことを確かめます。

   ```bash
   python3 -c "import json,os;json.load(open(os.path.expanduser('~/.claude/settings.json')));print('OK')"
   ```

   ```bash
   echo '{}' | ~/.claude/hooks/japanese-guard.py && echo OK
   ```

4. 新しく開いたセッションから有効になることを、ユーザーに伝えます。

Python 3 だけで動き、追加のパッケージは要りません。

## 環境変数

| 変数 | 既定 | 意味 |
|---|---|---|
| `JAPANESE_GUARD_MIN_LATIN` | `25` | 判定する最小の英字数 |
| `JAPANESE_GUARD_MIN_LATIN_MID` | `60` | 複数行の途中報告を判定する最小の英字数 |
| `JAPANESE_GUARD_MIN_LATIN_MID_LONG` | `250` | 1行の途中報告を判定する最小の英字数 |
| `JAPANESE_GUARD_RATIO` | `3` | 英語主体とみなす、日本語の文字数に対する英字の倍率 |
| `JAPANESE_GUARD_WAIT` | `3` | 最終回答が会話の記録へ書き込まれるのを待つ秒数 |
| `JAPANESE_GUARD_DISABLE` | なし | `1` で無効化（`claude -p` を使うスクリプト向け） |

## 過去のセッションで試す

会話の記録を渡すと、最後のターンで英語主体だった本文を表示します。

```bash
python3 ~/.claude/hooks/japanese-guard.py --check ~/.claude/projects/<プロジェクト>/<セッションID>.jsonl
```

## テスト

```bash
python3 tests/test_japanese_guard.py
```

## ライセンス

Apache License 2.0
