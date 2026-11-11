# 日本語でおｋ

Claude Code の応答が、いつの間にか英語に切り替わるのを止める Stop hook です。

日本語で指示していても、ツールを何度も呼ぶ長い作業のあとや、英語のツール出力を読んだ直後に、途中報告や最終報告が英語で返ってくることがあります。CLAUDE.md に「日本語で応答する」と書いても、この切り替わりは止まりませんでした。そこで、ターンの終わりに本文を機械で検査し、英語だったら日本語で書き直させる hook を作りました。

## 動き

1. Claude がターンを終えようとすると、Stop hook が最後の応答の本文（hook の入力 `last_assistant_message`）と会話の記録（transcript）を読みます
2. そのターンの本文を取り出し、英字と日本語の文字数を数えます
3. 英語主体の本文があれば、終了を止めて「日本語で書き直して」と差し戻します
4. Claude が同じターンのうちに日本語で出し直します

検査するのは次の3つです。

- **最終回答**：最後のツール呼び出しより後に Claude が書いた本文
- **ツール呼び出しの間の途中報告**のうち、複数行で英字が60文字以上あるものと、1行でも英字が250文字以上ある長い段落。数行の途中報告は本文と同じ大きさで画面に出るためです。ツールを呼ぶ前の1行の前置きは画面で小さく出るだけなので見ません（差し戻すと、日本語の最終回答のあとに前置きだけを書き直す応答がもう1通出てしまいます）。thinking の表示を `updates` にしている場合、途中報告は thinking ブロックとして記録されるので、そちらも見ます
- **デスクトップアプリの「次の一手」の箱**（`wrap_up` ツール）に出る、まとめ・質問・ボタンの文言。箱が最終回答の代わりになるターンでは、本文がほとんど残らないためです

ツールを呼ぶ前の短い一言は検査しません。画面では実行ログの間に小さく出るだけで、英語が混ざっても読む側は困らないからです。

「次の一手」の箱は、PreToolUse hook としても登録すると、英語の箱が画面に出る前に止めて書き直させます。

差し戻しは1ターンに1回だけです。書き直しがまた英語でも、そこで終了させるので、差し戻しが続くことはありません。

次のものは数えません。英語のコマンドや英文の下書きを見せるのは正当な使い方だからです。

- コードブロック（```` ``` ````）とインラインコード
- URL・メールアドレス・Markdown のリンク
- 英字が25文字未満の短い本文（「OK」程度の返事）

最終回答が JSON だけ（` ```json ` のコードフェンスで囲んだものを含む）のときも差し戻しません。スクリプトが読む出力に説明文が加わると、JSON として読めなくなるためです。

## 入れ方

Claude Desktop（Claude Code）に、このリポジトリの URL を渡して頼むだけです。

> https://github.com/minorun365/claude-code-japanese-guard これ設定しといて

あとは Claude Code が下の手順で入れてくれます。

## Claude Code 向けの設定手順

ユーザーからこのリポジトリの設定を頼まれた Claude Code は、次の手順で入れてください。CLI で自分で入れる人も、同じ手順で入れられます。

1. **hook を置く。** `hooks/japanese-guard.py` を `~/.claude/hooks/japanese-guard.py` に保存し、実行権限を付ける。

   ```bash
   mkdir -p ~/.claude/hooks
   curl -fsSL https://raw.githubusercontent.com/minorun365/claude-code-japanese-guard/main/hooks/japanese-guard.py -o ~/.claude/hooks/japanese-guard.py
   chmod +x ~/.claude/hooks/japanese-guard.py
   ```

2. **`~/.claude/settings.json` に hook を2か所登録する。** 既存の設定は消さず、`hooks.Stop` と `hooks.PreToolUse` の配列にそれぞれ次の1件を足す。`hooks`・`Stop`・`PreToolUse` が無ければ作る。同じ `command` がすでに登録されていれば、その配列には足さない。

   `hooks.Stop` に足すもの：

   ```json
   { "hooks": [ { "type": "command", "command": "~/.claude/hooks/japanese-guard.py" } ] }
   ```

   `hooks.PreToolUse` に足すもの（デスクトップアプリの「次の一手」の箱を、表示前に止める）：

   ```json
   { "matcher": "mcp__.*__wrap_up", "hooks": [ { "type": "command", "command": "~/.claude/hooks/japanese-guard.py" } ] }
   ```

   `matcher` は `wrap_up` だけにしない。英数字と `_` だけの matcher は完全一致として扱われ、実際のツール名（`mcp__` で始まる名前）に当たらない。`.` や `*` を含めると正規表現として扱われる。

   書き換えたあと、ファイルが JSON として読めることを確かめる。

   ```bash
   python3 -c "import json,os;json.load(open(os.path.expanduser('~/.claude/settings.json')));print('OK')"
   ```

   自分の設定ファイルの書き換えが権限の都合で止められた場合は、無理に回避しない。足す内容をユーザーに示し、ユーザー自身で `settings.json` に足してもらう。

3. **動くことを確かめる。** 何も渡さずに実行してエラーにならないこと（何も出力されなければ正常）を確かめる。

   ```bash
   echo '{}' | ~/.claude/hooks/japanese-guard.py && echo OK
   ```

4. **ユーザーに伝える。** 入れたことと、設定が確実に読み込まれるのは新しく開いたセッションからであることを伝える。応答が英語になると、ターンの終わりに「日本語で書き直して」と差し戻されるようになる。

Python 3 だけで動きます。追加のパッケージは要りません。

## 判定の調整

環境変数で閾値を変えられます。

| 変数 | 既定 | 意味 |
|---|---|---|
| `JAPANESE_GUARD_MIN_LATIN` | `25` | 英字がこれ未満の本文は判定しない |
| `JAPANESE_GUARD_MIN_LATIN_MID` | `60` | ツール呼び出しの間の途中報告（複数行）は、英字がこれ以上あるときだけ判定する |
| `JAPANESE_GUARD_MIN_LATIN_MID_LONG` | `250` | 1行の途中報告は、英字がこれ以上ある長い段落のときだけ判定する |
| `JAPANESE_GUARD_RATIO` | `3` | 英字の数が日本語の文字数のこの倍を超えたら英語主体とみなす |
| `JAPANESE_GUARD_WAIT` | `3` | 最終回答が transcript へ書き込まれるのを待つ上限（秒）。Stop hook は書き込みより先に呼ばれることがあるため。`last_assistant_message` が英語なら待たずに差し戻す |
| `JAPANESE_GUARD_DISABLE` | なし | `1` にすると何もしない。`claude -p` で人が読まない出力を作るスクリプトから呼ぶとき向け |

## 手元の記録で試す

過去のセッションの記録に当てると、最後のターンで英語主体だった本文（途中報告と「次の一手」の箱を含む）を表示します。

```bash
python3 ~/.claude/hooks/japanese-guard.py --check ~/.claude/projects/<プロジェクト>/<セッションID>.jsonl
```

## テスト

```bash
python3 tests/test_japanese_guard.py
```

## ライセンス

Apache License 2.0
