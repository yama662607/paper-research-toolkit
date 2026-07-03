# SETUP_FOR_AGENT — 論文調査ツールキット セットアップ手順

> **この文書はメンバーのコーディングエージェント（Claude Code / Codex / Antigravity）が読んで実行するための手順書です。**
> ターミナルでできる設定は全てここに沿って自動実行してください。**人手が要るのは `MANUAL_STEPS.md` の項目（API key と Chrome 拡張）だけ**です。
> 冪等（再実行しても壊れない）に、各ステップの最後に検証を入れてください。

対象: **京都大学メンバー**。EZproxy は Kyoto-U 固定（`kyoto-u.idm.oclc.org`）。

---

## 0. 前提ツールの導入（未導入なら入れる）

必要: `python3`, `git`, `node`(npx), `uv`(uvx)。

```bash
# 確認
for c in python3 git node npx uv uvx; do command -v "$c" >/dev/null && echo "OK: $c" || echo "MISSING: $c"; done
```
不足分の導入（環境に合わせて。macOS 例）:
```bash
# mise を使っている場合
mise use -g node@latest
mise use -g uv@latest
# または Homebrew
brew install node uv git   # python3 は macOS 同梱 or `brew install python`
```
> node/uv がどうしても入らない場合のみ手を止めてユーザーに相談。それ以外は自動で進める。

---

## 1. doi-mcp をローカルビルド（`npx github:` の起動遅延を回避）

`doi-mcp` は npm 未公開・要ビルド。`npx github:` だと初回取得が遅く MCP 起動 timeout で落ちるため、**一度ビルドして固定パスから起動**する。

```bash
DEST="$HOME/.paper-tools/doi-mcp"
mkdir -p "$HOME/.paper-tools"
if [ -d "$DEST/.git" ]; then git -C "$DEST" pull --ff-only; else git clone --depth 1 https://github.com/tfscharff/doi-mcp "$DEST"; fi
cd "$DEST" && npm install --no-audit --no-fund && npm run build
test -f "$DEST/dist/index.js" && echo "doi-mcp built: $DEST/dist/index.js"
# 起動 smoke test（0.2秒程度で initialize に応答すれば OK）
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"1"}}}' | node "$DEST/dist/index.js" | head -c 200; echo
```

---

## 2. MCP を登録する（**使っているエージェントの節だけ**実行）

登録する 4 サーバ:
| name | command | args |
|---|---|---|
| `arxiv-mcp` | `uvx` | `arxiv-mcp-server` |
| `semantic-scholar` | `uvx` | `--from git+https://github.com/FujishigeTemma/semantic-scholar-mcp semantic-scholar-mcp serve` |
| `crossref-mcp` | `npx` | `-y @botanicastudios/crossref-mcp` |
| `doi-mcp` | `node` | `$HOME/.paper-tools/doi-mcp/dist/index.js` |

### 2-A. Claude Code
```bash
claude mcp add arxiv-mcp -s user -- uvx arxiv-mcp-server
claude mcp add semantic-scholar -s user -- uvx --from git+https://github.com/FujishigeTemma/semantic-scholar-mcp semantic-scholar-mcp serve
claude mcp add crossref-mcp -s user -- npx -y @botanicastudios/crossref-mcp
claude mcp add doi-mcp -s user -- node "$HOME/.paper-tools/doi-mcp/dist/index.js"
claude mcp list   # 4つ表示されれば OK
```

### 2-B. Codex
`~/.codex/config.toml` に追記（既存の `[mcp_servers.*]` と重複しないこと）:
```toml
[mcp_servers.arxiv-mcp]
command = "uvx"
args = ["arxiv-mcp-server"]

[mcp_servers.semantic-scholar]
command = "uvx"
args = ["--from", "git+https://github.com/FujishigeTemma/semantic-scholar-mcp", "semantic-scholar-mcp", "serve"]

[mcp_servers.crossref-mcp]
command = "npx"
args = ["-y", "@botanicastudios/crossref-mcp"]

[mcp_servers.doi-mcp]
command = "node"
args = ["<HOME>/.paper-tools/doi-mcp/dist/index.js"]   # <HOME> を実パスに置換
```
> `startup_timeout_sec` が設定可能なら `semantic-scholar` は初回 build が重いので `60` 程度にしておくと安全。

### 2-C. Antigravity (agy)
`~/.gemini/config/mcp_config.json`（無ければ作成）の `mcpServers` に追記:
```json
{
  "mcpServers": {
    "arxiv-mcp": { "command": "uvx", "args": ["arxiv-mcp-server"] },
    "semantic-scholar": { "command": "uvx", "args": ["--from", "git+https://github.com/FujishigeTemma/semantic-scholar-mcp", "semantic-scholar-mcp", "serve"] },
    "crossref-mcp": { "command": "npx", "args": ["-y", "@botanicastudios/crossref-mcp"] },
    "doi-mcp": { "command": "node", "args": ["<HOME>/.paper-tools/doi-mcp/dist/index.js"] }
  }
}
```

---

## 3. Skills を配置

このパックの `skills/` を共通ディレクトリに置き、使っているエージェントの skill dir へリンク（native 未対応でも「調査時にこの SKILL.md を読む」で機能する）:
```bash
mkdir -p "$HOME/.paper-tools"
cp -R <このパック>/skills "$HOME/.paper-tools/skills"
# Claude Code
mkdir -p "$HOME/.claude/skills"
for d in "$HOME/.paper-tools/skills/"*/; do ln -sfn "$d" "$HOME/.claude/skills/$(basename "$d")"; done
# Antigravity（対応環境のみ）
mkdir -p "$HOME/.gemini/antigravity-cli/skills"
for d in "$HOME/.paper-tools/skills/"*/; do ln -sfn "$d" "$HOME/.gemini/antigravity-cli/skills/$(basename "$d")"; done
```
- 中核 skill = **`paper-research-workflow`**（探索→検証→選別→保存の判断役。まずこれを読む）。
- `paper-download-kyoto-u` は保存段（Zotero）。`ncbi-pmc-skill` は生物医学向け（任意）。`web-search-antigravity` は深掘り Web 検索（agy が要る・任意）。

---

## 4. 疎通確認（必須）

MCP が起動し応答することを、既知 DOI で確認する。エージェントから各 MCP tool を1回ずつ呼び、以下が返れば成功:
- `crossref-mcp` `getWorkByDOI("10.1103/PhysRevX.13.041043")` → title = "Enhanced Associative Memory..."
- `arxiv-mcp` `get_abstract` / `search_papers` が応答。
- `semantic-scholar` `search_paper` が応答（初回は build で数十秒かかることがある）。
- `doi-mcp` `verifyCitation` 相当が応答（ローカルビルド起動）。

OA 解決の疎通（Zotero 不要）:
```bash
python3 "$HOME/.paper-tools/skills/paper-download-kyoto-u/scripts/resolve_oa_pdf.py" \
  --doi 10.1103/PhysRevX.13.041043 --email "<あなたの京大メール>"
# is_oa:true と pdf_url が返れば OK
```

---

## 5. 完了条件
- `claude mcp list`（または各 config）に 4 サーバが登録され、疎通確認が通る。
- `resolve_oa_pdf.py` が OA URL を返す。
- 残りは `MANUAL_STEPS.md`（API key・Chrome 拡張・Zotero・EZproxy ログイン）を人手で。
