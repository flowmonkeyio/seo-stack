# content-stack SEO Quality Baseline

Reviewed against Google Search Central and Agent Skills guidance in May 2026.
Use this baseline for every skill that creates, edits, audits, links, marks up,
publishes, or refreshes content.

## People-First Bar

- Optimize for the reader's goal first. SEO work is acceptable only when it
  helps search engines understand helpful content.
- Require original value: first-hand experience, original analysis, useful
  comparisons, source synthesis, examples, data, or clear decisions. Do not
  ship pages that mostly rewrite search results or competitor pages.
- Do not create large batches of thin pages for search manipulation. If a bulk
  procedure cannot explain the unique reader value of each topic, return
  `DONE_WITH_CONCERNS` or `BLOCKED`.
- Do not change dates, titles, or freshness signals to look current unless the
  page has materially changed.
- Do not promise rankings, traffic, rich results, or AI citations.

References:
- Google helpful content: https://developers.google.com/search/docs/fundamentals/creating-helpful-content
- Google Search Essentials: https://developers.google.com/search/docs/essentials
- Google spam policies: https://developers.google.com/search/docs/essentials/spam-policies

## Source and EEAT Bar

- Make authorship, review ownership, and "who created this" visible when the
  page type expects it.
- For YMYL, regulated, financial, legal, gambling, health, or safety-adjacent
  content, require stronger evidence, current sources, and explicit compliance
  disclosure before publishing.
- Use citations for load-bearing claims, statistics, legal/regulatory claims,
  product claims, and comparisons. Do not cite a page just because it ranks.
- Mark source confidence: primary source, official/vendor source, expert
  source, independent review, community/anecdotal, or weak.
- Briefs must maintain a claim-to-source ledger. For each source record the
  source role, claim role, credibility rationale, recency requirement,
  conflict notes, and whether the source is primary or secondary.
- YMYL, regulated, legal, financial, health, gambling, product-review, and
  compliance-heavy pages require an accountable reviewer: reviewer identity,
  credentials or review basis, reviewed_at, and signoff state. If no qualified
  reviewer is available, stop before publish.

## Titles and Descriptions

- Titles should be unique, concise, descriptive, and aligned with the visible
  H1. Use the query language naturally; do not stuff repeated keyword variants.
- Character windows are heuristics only. Do not score a title or meta
  description as failing solely because it misses a fixed length.
- Meta descriptions should be unique, page-specific, human-readable summaries
  or useful page facts. Avoid keyword lists.

References:
- Title links: https://developers.google.com/search/docs/appearance/title-link
- Snippets/meta descriptions: https://developers.google.com/search/docs/appearance/snippet

## Content Structure

- The outline should satisfy the reader's intent, not a target word count.
  Word counts are editorial scope estimates, not Google ranking rules.
- Avoid generic intros, throat-clearing, and formulaic transitions.
- Each section should carry a clear claim, evidence or example, and reader
  payoff. Remove sections that exist only to cover a keyword variant.
- Keep commercial/review content decision-useful: comparison criteria,
  tradeoffs, evidence, pros/cons, and who each option fits.

Reference:
- Review guidance: https://developers.google.com/search/docs/specialty/ecommerce/write-high-quality-reviews

## Images and Alt Text

- Images must support the page, not decorate it. Place them near relevant text.
- Decorative images should be marked decorative by the publish target or use
  empty alt text where the target supports it.
- Filenames should be short and descriptive when the publisher controls them.
- Alt text should be useful, contextual, and accessibility-friendly. It may use
  a relevant keyword naturally, but never as keyword stuffing.
- Performance matters: modern formats, dimensions to avoid layout shift, and
  reasonable file sizes.

Reference:
- Image SEO: https://developers.google.com/search/docs/appearance/google-images

## Structured Data

- Emit structured data only for content visible to users and truly represented
  on the page.
- Prefer fewer complete, accurate schemas over many weak or partial schemas.
- Use JSON-LD where the target supports it.
- Do not emit `FAQPage` by default. As of May 7, 2026, FAQ rich results no
  longer appear in Google Search and Google is dropping related reports/tests;
  only emit FAQ-like markup when a project explicitly needs it for a non-Google
  consumer and record that it has no Google rich-result expectation.
- Do not emit HowTo for Google rich-result targeting. Treat it as deprecated
  for this product unless a project-specific non-Google consumer requires it.
- Product, Review, and AggregateRating require visible, real product/review
  content and supporting evidence. Never mark up fake or inferred reviews.
- Treat Google rich-result fields as policy-driven recommendations unless the
  current validator marks them required for the selected type. Do not describe
  truncation heuristics as hard Google limits.

References:
- Structured data policies: https://developers.google.com/search/docs/appearance/structured-data/sd-policies
- FAQ structured data: https://developers.google.com/search/docs/appearance/structured-data/faqpage

## Internal Links and Crawlability

- Links must be crawlable, relevant, and useful to readers. Do not insert links
  only to manipulate anchor text.
- Prefer descriptive anchors that match the destination's topic without exact
  match stuffing.
- Qualify outbound paid, affiliate, sponsored, or user-generated links with
  the appropriate `rel` values before publishing.
- Protect canonical URLs, redirects, robots/noindex, and schema from publish
  target drift.
- Never work around a competitor's blocked robots/crawl policy. If a sitemap or
  robots rule blocks discovery, use operator-supplied URLs or licensed exports.
- Publishing preview must pass indexability, canonical, robots/noindex,
  hreflang when applicable, public image URLs, structured-data parity, and
  sitemap/lastmod checks before a live write.

## Monitoring and Refresh

- Use GSC data as directional, query/page-level evidence. Distinguish
  opportunity from diagnosis: low CTR suggests title/snippet testing; ranking
  overlap suggests cannibalization; crawl verdicts suggest technical triage.
- Prefer final Search Console data. If fresh/incomplete data is used, record
  the incomplete date boundary and confidence downgrade. Segment material
  decisions by country/device and brand/non-brand where those dimensions matter.
- Refresh content because facts, intent, products, compliance, or performance
  changed. Do not refresh merely to make the site look active.
- Preserve prior versions and explain what materially changed.
- Do not update `dateModified`, `last_refreshed_at`, or visible freshness
  language for cosmetic-only edits.
