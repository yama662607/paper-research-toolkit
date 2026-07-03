---
name: paper-download-kyoto-u
description: Download scientific papers and save them directly to Zotero using Kyoto-U EZproxy. Triggers when the user asks to save, download, or import a paper/literature to Zotero using Kyoto University credentials.
---

# Kyoto-U Zotero Paper Downloader (Playwright MCP Version)

確定した1件の論文を、Open Access を優先しつつ、必要なら Kyoto-U EZproxy の**認証済みブラウザ**経由で PDF を取得し、Zotero Connector HTTP API でローカル Zotero に保存する。

**保存はブラウザのショートカットを使わず、Connector API の2段(`saveItems` → `saveAttachment`)で行う。**

> **改善版のポイント（v2）**: 旧版は PDF を Python urllib で直接 DL していたため、paywall / Cloudflare / EZproxy の PDF が取れなかった。v2 は **(1) OA を先に解決（Unpaywall）**、**(2) OA が無ければ認証済みブラウザ内で `fetch` して PDF バイトを取得** → ローカルファイルとして `--pdf-file` で添付する。これにより paywall 論文も自動保存できる。

---

## Prerequisites

1. **Zotero Desktop**: 起動していること（Connector は `http://127.0.0.1:23119`）。
2. **playwright-extension MCP**: Chrome/Arc の**ログイン済みブラウザ**に接続済み（EZproxy セッションを使うため）。
3. **`python3`** が使えること。
4. **Unpaywall email**（OA 解決用・API key ではなく連絡先メール）: `--email` か環境変数 `UNPAYWALL_EMAIL`。京大メールで可。

---

## 入力候補（探索スキルから受け取る）

- `article_title`（正式タイトル） / `article_url`（論文ページ URL） / `doi`（推奨） / `pdf_url`（あれば）。
- `paper_candidates` 形式で複数来たら、**DOI 確定済みのものだけ**を1件ずつ処理する。未確定・未選別は扱わない。

---

## Workflow（1件ごと）

### Step 0: OA を先に解決（EZproxy を使わずに済むなら最速・最確実）
DOI がある場合、まず OA PDF を探す:
```bash
python3 <skill-root>/scripts/resolve_oa_pdf.py --doi "${doi}" --email "${UNPAYWALL_EMAIL}"
```
- exit 0 かつ `pdf_url` が返れば → **Step 3A（OA 直 DL）へ**。
- exit 3（OA 無し）→ **Step 1（EZproxy 認証ブラウザ）へ**。

### Step 1: EZproxy URL を認証済みブラウザで開く
1. 論文 URL を Kyoto-U EZproxy 形式へ:
   `https://kyoto-u.idm.oclc.org/login?url=<original_paper_url>`
2. `playwright-extension` の `browser_tabs`（`action:"new"`）で開く。
3. 京大認証プロンプトが出たら、ユーザーにログイン完了を依頼し確認する（初回のみ）。

### Step 2: 論文ページで最終メタデータと PDF URL を確定
ページが安定したら取得:
- `article_url`（現在の URL）/ `article_title`（ページタイトル）/ `pdf_url`（`content/pdf` 等の直リンク、**EZproxy proxied ドメインのまま**）/ `doi`。

### Step 3B: 認証ブラウザ内で PDF を fetch（paywall/EZproxy 対応の本命）
`playwright-extension` の `browser_evaluate` を **論文ページ（proxied・同一オリジン）** で実行し、PDF バイトを base64 で取得する:
```js
async () => {
  const r = await fetch("${pdf_url}", { credentials: "include" });
  const buf = new Uint8Array(await r.arrayBuffer());
  let bin = ""; const CH = 0x8000;
  for (let i = 0; i < buf.length; i += CH) bin += String.fromCharCode.apply(null, buf.subarray(i, i + CH));
  return { status: r.status, contentType: r.headers.get("content-type"), b64: btoa(bin) };
}
```
- `status` が 200 かつ `contentType` に `pdf` を含むこと（HTML が返ったら paywall 突破失敗 → Step 4 の [保留]）。
- 返った `b64` を一時ファイルへ:
```bash
python3 -c 'import base64,sys; open(sys.argv[1],"wb").write(base64.b64decode(sys.argv[2]))' \
  /tmp/paper_${doi_or_hash}.pdf "${b64}"
```
- 保存（**ローカルファイル**を添付）:
```bash
python3 <skill-root>/scripts/save_to_zotero.py \
  --article-url "${article_url}" --article-title "${article_title}" \
  --pdf-file "/tmp/paper_${doi_or_hash}.pdf" --doi "${doi}"
```

### Step 3A: OA 直 DL（Step 0 で OA が見つかった場合のみ）
```bash
python3 <skill-root>/scripts/save_to_zotero.py \
  --article-url "${article_url}" --article-title "${article_title}" \
  --pdf-url "${oa_pdf_url}" --doi "${doi}"
```
- `save_to_zotero.py` が **exit code 2** を返したら（= urllib で PDF が取れず HTML 等が返った）、OA URL が実は保護されている → **Step 1〜3B（ブラウザ取得）へフォールバック**。

### Step 4: 検証・後始末・フォールバック
- `save_to_zotero.py` が `status=success`（`parent_key` あり）なら成功。tab を閉じ、Zotero key を報告。
- 取得に失敗した場合（ブラウザ fetch も HTML / status≠200、EZproxy 未ログイン等）は**リトライループに入らず**、`[保留] DOI + title + 理由` を保存ログに記録し、ユーザーへ報告。

---

## 補助ルール
- **重複回避**: 同一 title+DOI は1回だけ試行。既存は skip。
- DOI があれば必ず `--doi` を渡す（未検出は `--doi ""`）。
- `save_to_zotero.py` は **PDF 判定ガード**を持つ（先頭が `%PDF-` でなければ保存しない）。HTML/ログインページを PDF として保存する事故を防ぐ。
- exit code: `0`=成功 / `1`=Connector 等の失敗 / `2`=PDF が取れない（ブラウザ取得へ）。
- **礼儀**: バッチ保存時は publisher への連続アクセスに軽い sleep を入れる。
