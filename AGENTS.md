# Publishing checks

- Each language homepage must contain exactly the latest 20 stories. Move older
  stories into its archive; keep all valid archived stories in the normal sitemap.
- After any publication or article change, run
  `python3 scripts/prepare_publish.py` before committing or deploying. This adds
  shared article metrics and regenerates complete language and recent-news sitemaps.
- Run `git diff --check` and verify that the intended new story appears in its
  language sitemap. A sitemap is not evidence that Google indexed the URL.
- Keep the existing Google tag and its consent settings. Do not add another
  page-view configuration when changing article engagement measurement.
- Deploy a clean, committed snapshot. Do not include unrelated local app-policy
  changes or private audit reports in a website deployment.
