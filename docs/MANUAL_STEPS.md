# MANUAL_STEPS — 人が手でやる作業（ターミナルで完結しないもの）

エージェントに任せられない、**ブラウザ操作・GUI ログイン・鍵の取得**だけをまとめました。所要 10〜15 分。

---

## 1. Semantic Scholar API key（推奨・rate limit 緩和）
1. https://www.semanticscholar.org/product/api → "Get an API Key" から申請（無料）。
2. 届いた key を環境変数に設定（**貼るところまでで OK。設定はエージェントに頼めます**）:
   ```bash
   export SEMANTIC_SCHOLAR_API_KEY="＜あなたのkey＞"   # ~/.zshrc 等に追記
   ```
> 無くても動くが、複数人・多数クエリだと 429 が出やすい。研究室配布なら取得推奨。

## 2. Unpaywall 用メール（key ではなく連絡先）
- 京大メールをそのまま使う。エージェントの `resolve_oa_pdf.py --email` か、`export UNPAYWALL_EMAIL="you@kyoto-u.ac.jp"` を設定。取得作業は不要。

## 3. Chrome / Arc の拡張（**ここが唯一のブラウザ手作業**）
論文の PDF をブラウザ経由で取る/Zotero に送るために 2 つ入れる:
1. **Playwright Extension**（`@playwright/mcp --extension` が接続する拡張）
   - Chrome ウェブストアで "Playwright MCP" 系の拡張を追加し、有効化。
   - `playwright-extension` MCP 初回接続時に「このタブを共有」を1回許可。
2. **Zotero Connector**（https://www.zotero.org/download/connectors）
   - Chrome/Arc に追加。ログイン不要（デスクトップ Zotero と連携）。

## 4. Zotero Desktop
1. インストール（エージェントに `brew install --cask zotero` を頼んでも可）。
2. **起動してアカウントにログイン**（同期したい場合）。
3. 起動中は Connector API が `http://127.0.0.1:23119` で待ち受ける（保存先）。

## 5. 京大 EZproxy の初回ログイン
- paywall 論文を保存する時、エージェントが EZproxy URL
  `https://kyoto-u.idm.oclc.org/login?url=...` を開きます。
- **初回だけ京大 SSO でログイン**（ECS-ID 等）。以降はブラウザセッションが効くので自動で通ります。

---

## これで完了
- 上記が済めば、あとはエージェントに「この DOI/タイトルの論文を調べて（必要なら）Zotero に保存して」と頼むだけ。
- OA 論文は EZproxy 不要で自動保存、paywall 論文は EZproxy 認証ブラウザ経由で自動取得されます。
- うまく取れない論文は保存ログに `[保留]` として残るので、その時だけ手動保存を検討してください。
