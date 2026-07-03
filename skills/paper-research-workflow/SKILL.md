---
name: paper-research-workflow
description: Literature research workflow for finding, screening, verifying, and preparing academic papers before saving them. Use when the user asks to discover papers, compare candidate papers, validate DOI/publication metadata, check PDF availability, or connect discovery tools such as arxiv-mcp, semantic-scholar-mcp, crossref-mcp, doi-mcp, ncbi-pmc-skill, web-search-antigravity, and paper-download-kyoto-u.
---

# Paper Research Workflow

## Core Rule

Separate discovery, verification, selection, and saving.

Do not modify third-party MCPs or skills. Use them as evidence sources. Put workflow decisions in this skill and leave `paper-download-kyoto-u` focused on saving a confirmed paper to Zotero.

## Tool Roles

Use `arxiv-mcp` for arXiv-first fields such as computer science, physics, mathematics, statistics, and preprints. Prefer it when the user wants arXiv IDs, abstracts, versions, or direct PDF links.

Use `semantic-scholar-mcp` for paper discovery, citation context, related papers, author networks, and impact screening. Prefer it when ranking candidates or expanding from a seed paper.

Use `crossref-mcp` for canonical publication metadata: DOI, title, author list, venue, publisher, year, and bibliographic normalization. Prefer it when title/DOI accuracy matters.

Use `doi-mcp` for DOI-centered verification across academic databases. Prefer it before citation output or before saving when there is a risk of hallucinated or mismatched DOI metadata.

Use `ncbi-pmc-skill` for biomedical and life-science papers where PMC Open Access availability matters. Prefer it when the user asks for PubMed/PMC papers, full text, OA files, or biomedical literature.

Use `web-search-antigravity` only when database-style tools are insufficient: unclear topics, broad web discovery, publisher pages, institutional pages, or recent web-only context.

Use `paper-download-kyoto-u` only after one paper is selected and enough metadata exists to save it. Pass a single confirmed candidate, not an unscreened list.

## Workflow

1. Clarify the research intent

Identify topic, field, date range, paper type, and whether the user wants breadth, key papers, recent papers, or downloadable PDFs.

2. Discover candidates

Start with the most structured source. For arXiv-heavy fields use `arxiv-mcp`; for general academic discovery use `semantic-scholar-mcp`; for biomedical discovery include `ncbi-pmc-skill`; for broad or ambiguous topics use `web-search-antigravity`.

3. Normalize metadata

For promising candidates, verify title, DOI, authors, year, venue, and URL with `crossref-mcp` and/or `doi-mcp`. Treat title-only matches as provisional unless author/year also agree.

4. Screen and rank

Rank by relevance to the user's question, publication quality, recency, citation context, method fit, and availability. Explain why a paper is included or excluded.

5. Check access and PDF availability

Prefer direct PDF links from arXiv or PMC OA when available. For publisher pages, distinguish a landing page URL from an actual PDF URL. If no PDF is confirmed, mark the paper as metadata-only before handing it off.

6. Prepare downloader input

For each selected paper, produce a compact candidate object with:

```json
{
  "article_title": "...",
  "title": "...",
  "doi": "...",
  "url": "...",
  "pdf_url": "...",
  "source": "arxiv|semantic-scholar|crossref|doi|pmc|web",
  "metadata": {
    "authors": ["..."],
    "year": 2026,
    "venue": "...",
    "abstract": "..."
  },
  "evidence": [
    {
      "source": "...",
      "claim": "What this source confirms"
    }
  ],
  "save_readiness": "ready|metadata-only|needs-human-check"
}
```

Include both `article_title` and `title` when connecting to tools that may expect either key.

7. Save only confirmed selections

Invoke `paper-download-kyoto-u` only for papers with `save_readiness=ready` or when the user explicitly accepts a `metadata-only` save. After saving, check that the saved title/DOI matches the selected candidate.

## Matching Policy

Prefer DOI matches over title matches.

Accept title-only matches only when normalized title, first author, and year are consistent. Normalize case, punctuation, whitespace, Unicode variants, and subtitle punctuation, but do not merge papers with different DOIs unless there is clear evidence they are the same work.

Flag ambiguous cases when the same or similar title maps to different DOIs, venues, versions, or years.

## Recommended Outputs

For a search request, return a short ranked table with title, year, source, DOI/arXiv/PMCID, PDF status, and reason to read.

For a download preparation request, return candidate JSON objects and clearly state which ones are ready for `paper-download-kyoto-u`.

For a literature review request, separate "must read", "supporting", and "background" papers, then identify which are save-ready.
