# claude-code-japanese-guard

Claude Code の応答が、いつの間にか英語に切り替わるのを止める Stop hook です。

日本語で指示していても、ツールを何度も呼ぶ長い作業のあとや、英語のツール出力を読んだ直後に、途中報告や最終報告が英語で返ってくることがあります。CLAUDE.md に「日本語で応答する」と書いても、この切り替わりは止まりませんでした。そこで、ターンの終わりに本文を機械で検査し、英語だったら日本語で書き直させる hook を作りました。

## 動き

1. Claude がターンを終えようとすると、Stop hook が会話の記録（transcript）を読みます
2. 最後のユーザー発言より後に Claude が書いた本文を集め、英字と日本語の文字数を数えます
3. 英語主体の本文があれば、終了を止めて「日本語で書き直して」と差し戻します
4. Claude が同じターンのうちに日本語で出し直します

差し戻しは1ターンに1回だけです。書き直しがまた英語でも、そこで終了させるので、差し戻しが続くことはありません。

次のものは数えません。英語のコマンドや英文の下書きを見せるのは正当な使い方だからです。

- コードブロック（```` ``` ````）とインラインコード
- URL・メールアドレス・Markdown のリンク
- 英字が25文字未満の短い本文（「OK」程度の返事）

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

2. **`~/.claude/settings.json` に Stop hook を登録する。** 既存の設定は消さず、`hooks.Stop` の配列に次の1件を足す。`hooks` や `Stop` が無ければ作る。同じ `command` がすでに登録されていれば、何もしない。

   ```json
   { "hooks": [ { "type": "command", "command": "~/.claude/hooks/japanese-guard.py" } ] }
   ```

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
| `JAPANESE_GUARD_RATIO` | `3` | 英字の数が日本語の文字数のこの倍を超えたら英語主体とみなす |

## 手元の記録で試す

過去のセッションの記録に当てると、最後のターンで英語主体だった本文を表示します。

```bash
python3 ~/.claude/hooks/japanese-guard.py --check ~/.claude/projects/<プロジェクト>/<セッションID>.jsonl
```

## テスト

```bash
python3 tests/test_japanese_guard.py
```

## ライセンス

Apache License 2.0
