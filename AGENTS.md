# Publishing checks

- Each language homepage must contain exactly the latest 20 stories. Move older
  stories into its archive; keep all valid archived stories in the normal sitemap.
- After any publication or article change, run
  `python3 scripts/prepare_publish.py` before committing or deploying. This adds
  shared article metrics and regenerates complete language and recent-news sitemaps.
- Run `git diff --check` and verify that the intended new story appears in its
  language sitemap. A sitemap is not evidence that Google indexed the URL.
- `prepare_publish.py` also maintains the real author byline, publisher schema,
  correction links, RSS feeds and footer discovery. Verify visible authorship
  agrees with structured data. Do not invent publication times or reset dates
  for metadata-only changes.
- Validate alternate-language links only against actual translated pages and
  check reciprocal links. English-only stories do not require fabricated
  translations or hreflang alternatives.
- Before editorial publication, review material claims against the cited
  documents or reporting, check quotations and identify uncertainty. Link
  checks and schema validation are not factual verification.
- Before uploading to Cloudflare Pages, fetch the current `origin/main` and
  build the upload from that committed revision. Run
  `python3 scripts/update_sitemaps.py --check` in the revision's checkout
  using the same London publication date as the build. Pass the revision SHA to
  Wrangler and verify the deployed revision and its live language sitemaps.
- Keep the existing Google tag and its consent settings. Do not add another
  page-view configuration when changing article engagement measurement.
- Deploy a clean, committed snapshot. Do not include unrelated local app-policy
  changes or private audit reports in a website deployment.
