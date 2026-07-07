# agent-tools — コーディングエージェント用の skill / MCP 集（京大メンバー配布用）

Claude Code / Codex / Antigravity 向けの skill・MCP を公開・配布するリポジトリ。今後 skill/mcp/plugin を随時追加していく。MIT ライセンス。

> **現在のバンドル: 論文調査(paper research)** — 論文の**探索 → 検証 → 選別 → 保存**を支援する skill / MCP 一式。ハルシネーション（実在しない DOI・誤った書誌）を DOI 一致検証で潰し、確定した論文だけを Zotero に保存する。

## 構成
```
skills/
  paper-research-workflow/   探索〜保存の判断役（まずこれ。純SKILL.md、環境依存なし）
  paper-download-kyoto-u/    Zotero 保存（v2: OA優先＋認証ブラウザ取得で paywall も対応）
  ncbi-pmc-skill/            PMC Open Access 確認（生物医学向け・任意）
  web-search-antigravity/    深掘りWeb検索（agy 必須・任意）
mcp/
  arxiv-mcp / semantic-scholar / crossref-mcp / doi-mcp の定義
docs/
  SETUP_FOR_AGENT.md   エージェントが実行する設定手順（ターミナル自動）
  MANUAL_STEPS.md      人手の作業（API key / Chrome 拡張 / Zotero / EZproxy）
```

## 使い方（役割分担）
- **探索**: `arxiv-mcp`（arXiv）/ `semantic-scholar`（関連・引用・重要度）/ `web-search-antigravity`（深掘り・任意）。
- **検証（ハルシネーション対策の核）**: `crossref-mcp`（DOI→正式書誌）/ `doi-mcp`（複数DB照合）。**DOI 一致を最優先、タイトルだけの曖昧一致は慎重に**。
- **選別**: `paper-research-workflow` の判断で、確定 1 件だけを保存へ。
- **保存**: `paper-download-kyoto-u`。OA は Unpaywall で解決して即DL、paywall は Kyoto-U EZproxy の認証ブラウザ経由で取得 → Zotero。

## セットアップ（2 ステップ）
新しい公開インストール導線は [install/README.md](install/README.md) にあります。
使いたいツールの install Markdown を全文コピーして、自分の AI Agent に渡してください。

従来の論文調査バンドルは以下の手順でもセットアップできます。

1. あなたのエージェント（Claude Code / Codex / Antigravity）に **`docs/SETUP_FOR_AGENT.md` を読んで実行**させる（uv/node 導入・doi-mcp ビルド・MCP 登録・skill 配置・疎通確認まで自動）。
2. **`docs/MANUAL_STEPS.md`** の人手作業（API key・Chrome 拡張・Zotero・EZproxy ログイン）を済ませる。

## 品質規律（paper-research-workflow に従う）
- **DOI 一致検証必須**。確認できないものは `[未確認]` に格下げ。
- **アクセスレベルを正直に**タグ付け（本文取得 / 要旨のみ / 書誌のみ）。要旨以下は定量・性能の根拠に使わない。
- **過大主張禁止**。「この論文がこの手法を使う」は必ず出典を添える。

## 注意（環境依存・京大固有）
- EZproxy は **Kyoto-U 固定**（京大メンバー専用）。
- paper-download は **Zotero Desktop 起動 + Chrome 拡張 + EZproxy ログイン**が前提（`MANUAL_STEPS.md`）。
- `web-search-antigravity` は Antigravity CLI（`agy`）とモデルクォータ依存のため**任意**。通常はエージェント内蔵の web 検索で代替可。

## v2 の改善（実走の教訓から）
- `doi-mcp` を **ローカルビルド起動**に（`npx github:` の起動遅延で MCP timeout する問題を解消）。
- paper-download の PDF 取得を **urllib 直DL → OA優先＋認証ブラウザ内 fetch（`--pdf-file`）** に刷新。**paywall / Cloudflare / EZproxy の PDF も自動保存**できるように。HTML/ログインページを PDF として誤保存しないガード付き。
