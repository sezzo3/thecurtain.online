/**
 * thecurtain.online language worker (Cloudflare Pages, advanced mode).
 *
 * This file is `_worker.js` at the project root: it runs for every request
 * and serves the static site through the ASSETS binding.
 *
 * Rules (decided by the site owner, 2026-11-06):
 * - Canonical host: www.thecurtain.online always 301-redirects to
 *   thecurtain.online (path and query preserved), so ranking signals are
 *   not split between two copies of every page. AdSense is untouched:
 *   ads.txt and the ad script live on the apex host and page content
 *   does not change.
 * - A manual language choice always wins: it is stored in a `curtain-lang`
 *   cookie (1 year). Dropdown links carry ?lang=<code>; this worker
 *   stores the choice and redirects to the clean URL (no query string).
 * - Visiting any /tr/, /de/ or /es/ page also stores that language.
 * - Homepage only, first visit only: a visitor with no cookie who arrives
 *   from Turkey / Germany / Austria / Switzerland / Spain or
 *   Spanish-speaking Latin America is redirected to that language's
 *   homepage (TR -> /tr/, DE/AT/CH -> /de/, ES + Spanish-speaking
 *   Latin America -> /es/). Everywhere else English by default.
 * - Bots are never redirected. Browser language is never read.
 */

const LANG_COUNTRIES = {
  tr: ['TR'],
  de: ['DE', 'AT', 'CH'],
  es: ['ES', 'MX', 'AR', 'CO', 'CL', 'PE', 'VE', 'EC', 'GT', 'CU', 'BO',
       'DO', 'HN', 'PY', 'SV', 'NI', 'CR', 'PA', 'UY', 'PR', 'GQ'],
};

// Static redirects previously in _redirects (a _worker.js takes over
// routing, so _redirects is no longer applied -- keep them here).
const STATIC_REDIRECTS = {
  '/ads/ad-every-empire-falls-1200x300.png': '/ads/ad-every-empire-falls-1200x300.webp',
  '/ads/ad-follow-the-crypto-1200x300.png': '/ads/ad-follow-the-crypto-1200x300.webp',
  '/ads/ad-guard-has-changed-1200x300.png': '/ads/ad-guard-has-changed-1200x300.webp',
  '/ads/ad-krakow-empty-square-1200x300.png': '/ads/ad-krakow-empty-square-1200x300.webp',
  '/ads/ad-line-keeps-moving-1200x300.png': '/ads/ad-line-keeps-moving-1200x300.webp',
  '/ads/ad-measles-vaccination-card-1200x300.png': '/ads/ad-measles-vaccination-card-1200x300.webp',
  '/ads/ad-power-new-address-1200x300.png': '/ads/ad-power-new-address-1200x300.webp',
  '/ads/ad-qeshm-strait-tanker-1200x300.png': '/ads/ad-qeshm-strait-tanker-1200x300.webp',
  '/ads/ad-strait-on-fire-1200x300.png': '/ads/ad-strait-on-fire-1200x300.webp',
  '/ads/ad-when-lights-go-out-1200x300.png': '/ads/ad-when-lights-go-out-1200x300.webp',
  '/ads/nov6-curiosity-1.png': '/ads/nov6-curiosity-1.webp',
  '/ads/nov6-curiosity-2.png': '/ads/nov6-curiosity-2.webp',
  '/ads/nov6-curiosity-3.png': '/ads/nov6-curiosity-3.webp',
  '/covers/cyclone-murasu-india-landfall-2026-11-03.png': '/covers/cyclone-murasu-india-landfall-2026-11-03.webp',
  '/covers/europe-supermarket-freezer-hack-2026-11-02.png': '/covers/europe-supermarket-freezer-hack-2026-11-02.webp',
  '/covers/europe-supermarket-freezer-hack-2026-11-03.png': '/covers/europe-supermarket-freezer-hack-2026-11-03.webp',
  '/covers/hormuz-qeshm-tankers-hit-2026-11-04.png': '/covers/hormuz-qeshm-tankers-hit-2026-11-04.webp',
  '/covers/russia-ukraine-alert-apps-cyberattack-2026-11-02.png': '/covers/russia-ukraine-alert-apps-cyberattack-2026-11-02.webp',
  '/covers/south-florida-neighborhood-crash-2026-11-02.png': '/covers/south-florida-neighborhood-crash-2026-11-02.webp',
  '/covers/ukraine-school-aid-distribution-strike-2026-11-03.png': '/covers/ukraine-school-aid-distribution-strike-2026-11-03.webp',
  '/covers/us-iran-doha-talks-no-deal-2026-11-03.png': '/covers/us-iran-doha-talks-no-deal-2026-11-03.webp',
  '/covers/us-midterms-early-voting-2026-11-02.png': '/covers/us-midterms-early-voting-2026-11-02.webp',
  '/covers/us-midterms-election-day-2026-11-03.png': '/covers/us-midterms-election-day-2026-11-03.webp',
  '/covers/western-sahara-minurso-end-2026-11-02.png': '/covers/western-sahara-minurso-end-2026-11-02.webp',
  '/covers/van-gogh-wheat-field-final-days.png': '/covers/van-gogh-wheat-field-final-days.webp',
  '/covers/gerrothorax-maritimus-marine-amphibian.png': '/covers/gerrothorax-maritimus-marine-amphibian.webp',
  '/covers/olympia-paris-salon-1865.png': '/covers/olympia-paris-salon-1865.webp',
  '/covers/bolivia-tilcayo-new-wild-cat.png': '/covers/bolivia-tilcayo-new-wild-cat.webp',
  '/covers/amsterdam-art-zoo-visitors-behind-bars.png': '/covers/amsterdam-art-zoo-visitors-behind-bars.webp',
  '/covers/iran-no-limits-gulf-countdown.png': '/covers/iran-no-limits-gulf-countdown.webp',
};

// Consolidated articles keep their existing language and query string.
const STORY_REDIRECTS = {
  '/de/story/america-turns-blue-democrats-seize-congress-midterm-rout/': '/de/story/democrats-seize-both-chambers-congress-midterm-rout/',
  '/de/story/democrats-sweep-congress-midterms-trump-rebuke/': '/de/story/democrats-seize-both-chambers-congress-midterm-rout/',
  '/de/story/icj-rules-myanmar-committed-genocide-rohingya/': '/de/story/icj-finds-myanmar-guilty-rohingya-genocide/',
  '/de/story/krakow-shooting-main-market-square-five-killed/': '/de/story/krakow-main-square-nine-dead/',
  '/de/story/trump-xi-putin-hold-first-trilateral-summit-shenzhen/': '/de/story/trump-xi-putin-meet-shenzhen-first-trilateral-summit/',
  '/de/story/trump-xi-putin-sign-peace-declaration-shenzhen/': '/de/story/trump-xi-putin-peace-declaration-shenzhen-summit/',
  '/de/story/trump-xi-putin-trilateral-shenzhen-nuclear-talks/': '/de/story/trump-xi-putin-meet-shenzhen-first-trilateral-summit/',
  '/de/story/ukraine-collapses-crimean-bridge-road-arch/': '/de/story/ukraine-second-strike-sends-crimea-bridge-into-sea/',
  '/de/story/us-flights-grounded-nationwide-faa-communications-failure/': '/de/story/faa-nationwide-ground-stop-flights-halted/',
  '/es/story/america-turns-blue-democrats-seize-congress-midterm-rout/': '/es/story/democrats-seize-both-chambers-congress-midterm-rout/',
  '/es/story/democrats-sweep-congress-midterms-trump-rebuke/': '/es/story/democrats-seize-both-chambers-congress-midterm-rout/',
  '/es/story/icj-rules-myanmar-committed-genocide-rohingya/': '/es/story/icj-finds-myanmar-guilty-rohingya-genocide/',
  '/es/story/krakow-shooting-main-market-square-five-killed/': '/es/story/krakow-main-square-nine-dead/',
  '/es/story/trump-xi-putin-hold-first-trilateral-summit-shenzhen/': '/es/story/trump-xi-putin-meet-shenzhen-first-trilateral-summit/',
  '/es/story/trump-xi-putin-sign-peace-declaration-shenzhen/': '/es/story/trump-xi-putin-peace-declaration-shenzhen-summit/',
  '/es/story/trump-xi-putin-trilateral-shenzhen-nuclear-talks/': '/es/story/trump-xi-putin-meet-shenzhen-first-trilateral-summit/',
  '/es/story/ukraine-collapses-crimean-bridge-road-arch/': '/es/story/ukraine-second-strike-sends-crimea-bridge-into-sea/',
  '/es/story/us-flights-grounded-nationwide-faa-communications-failure/': '/es/story/faa-nationwide-ground-stop-flights-halted/',
  '/story/america-turns-blue-democrats-seize-congress-midterm-rout/': '/story/democrats-seize-both-chambers-congress-midterm-rout/',
  '/story/democrats-sweep-congress-midterms-trump-rebuke/': '/story/democrats-seize-both-chambers-congress-midterm-rout/',
  '/story/icj-rules-myanmar-committed-genocide-rohingya/': '/story/icj-finds-myanmar-guilty-rohingya-genocide/',
  '/story/krakow-shooting-main-market-square-five-killed/': '/story/krakow-main-square-nine-dead/',
  '/story/spain-toledo-high-speed-train-collision/': '/story/spain-counts-69-dead-train-crash-investigation/',
  '/story/trump-xi-putin-hold-first-trilateral-summit-shenzhen/': '/story/trump-xi-putin-meet-shenzhen-first-trilateral-summit/',
  '/story/trump-xi-putin-sign-peace-declaration-shenzhen/': '/story/trump-xi-putin-peace-declaration-shenzhen-summit/',
  '/story/trump-xi-putin-trilateral-shenzhen-nuclear-talks/': '/story/trump-xi-putin-meet-shenzhen-first-trilateral-summit/',
  '/story/ukraine-collapses-crimean-bridge-road-arch/': '/story/ukraine-second-strike-sends-crimea-bridge-into-sea/',
  '/story/us-flights-grounded-nationwide-faa-communications-failure/': '/story/faa-nationwide-ground-stop-flights-halted/',
  '/tr/story/america-turns-blue-democrats-seize-congress-midterm-rout/': '/tr/story/democrats-seize-both-chambers-congress-midterm-rout/',
  '/tr/story/democrats-sweep-congress-midterms-trump-rebuke/': '/tr/story/democrats-seize-both-chambers-congress-midterm-rout/',
  '/tr/story/icj-rules-myanmar-committed-genocide-rohingya/': '/tr/story/icj-finds-myanmar-guilty-rohingya-genocide/',
  '/tr/story/krakow-shooting-main-market-square-five-killed/': '/tr/story/krakow-main-square-nine-dead/',
  '/tr/story/trump-xi-putin-hold-first-trilateral-summit-shenzhen/': '/tr/story/trump-xi-putin-meet-shenzhen-first-trilateral-summit/',
  '/tr/story/trump-xi-putin-sign-peace-declaration-shenzhen/': '/tr/story/trump-xi-putin-peace-declaration-shenzhen-summit/',
  '/tr/story/trump-xi-putin-trilateral-shenzhen-nuclear-talks/': '/tr/story/trump-xi-putin-meet-shenzhen-first-trilateral-summit/',
  '/tr/story/ukraine-collapses-crimean-bridge-road-arch/': '/tr/story/ukraine-second-strike-sends-crimea-bridge-into-sea/',
  '/tr/story/us-flights-grounded-nationwide-faa-communications-failure/': '/tr/story/faa-nationwide-ground-stop-flights-halted/',
};

const BOT_RE = /bot|crawl|spider|slurp|facebookexternalhit|twitterbot|linkedinbot|whatsapp|telegrambot|googlebot|bingbot|yandex|duckduckbot|baiduspider|facebot|ia_archiver|ahrefsbot|semrushbot|mj12bot|dotbot|petalbot/i;

function setLangCookie(res, lang) {
  res.headers.set(
    'Set-Cookie',
    `curtain-lang=${lang}; Path=/; Max-Age=31536000; SameSite=Lax`
  );
  return res;
}

// Response.redirect() returns a response with immutable headers, so a
// redirect that also sets a cookie must be built by hand.
function redirectWithCookie(url, status, lang) {
  const res = new Response(null, { status, headers: { Location: url } });
  return setLangCookie(res, lang);
}

async function serveSite(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    const articlePath = path.replace(/\/index\.html$/, '/').replace(/\/?$/, '/');
    const storyDestination = STORY_REDIRECTS[articlePath];
    if (storyDestination) {
      url.pathname = storyDestination;
      if (url.hostname === 'www.thecurtain.online') url.hostname = 'thecurtain.online';
      return Response.redirect(url.toString(), 301);
    }

    // 0. Canonical host: www -> apex, 301, path and query preserved.
    // Runs first so the geo/language logic below always sees the apex
    // host; ads.txt and the AdSense script are served from the apex
    // host unchanged, so AdSense is unaffected.
    if (url.hostname === 'www.thecurtain.online') {
      return Response.redirect(
        `https://thecurtain.online${path}${url.search}`, 301
      );
    }

    // 1. Static redirects (from the old _redirects file).
    if (STATIC_REDIRECTS[path]) {
      return Response.redirect(new URL(STATIC_REDIRECTS[path], url).toString(), 301);
    }

    const ua = request.headers.get('User-Agent') || '';
    const isBot = BOT_RE.test(ua);

    // 2. Explicit choice (?lang=xx): store it, redirect to the clean URL.
    const param = url.searchParams.get('lang');
    if (param && ['en', 'tr', 'de', 'es'].includes(param)) {
      url.searchParams.delete('lang');
      return redirectWithCookie(url.toString(), 302, param);
    }

    const cookie = (request.headers.get('Cookie') || '')
      .match(/(?:^|;\s*)curtain-lang=(en|tr|de|es)/);

    // 3. Language pages: remember the language for later visits.
    const langPage = path.match(/^\/(tr|de|es)(\/|$)/);
    if (langPage) {
      const res = await env.ASSETS.fetch(request);
      if (isBot) return res;
      return setLangCookie(new Response(res.body, res), langPage[1]);
    }

    // 4. Homepage only, never bots: a saved choice wins (redirect to the
    // saved language, or stay on English when the choice is English);
    // on a first visit (no cookie) the country decides.
    if ((path === '/' || path === '') && !isBot) {
      let target = null;
      if (cookie) {
        target = cookie[1] === 'en' ? null : cookie[1];
      } else {
        const country = (request.cf && request.cf.country) || '';
        for (const [lang, countries] of Object.entries(LANG_COUNTRIES)) {
          if (countries.includes(country)) { target = lang; break; }
        }
      }
      if (target) {
        return redirectWithCookie(new URL(`/${target}/`, url).toString(), 302, target);
      }
    }

    // 5. Everything else: serve the static file (with the old _headers
    // rule for hashed /_astro/ assets, which a _worker.js also replaces).
    const res = await env.ASSETS.fetch(request);
    if (path.startsWith('/_astro/')) {
      const out = new Response(res.body, res);
      out.headers.set('Cache-Control', 'public, max-age=31536000, immutable');
      return out;
    }
    return res;
}

export default {
  async fetch(request, env) {
    const response = await serveSite(request, env);
    const result = new Response(response.body, response);
    const url = new URL(request.url);
    result.headers.set('X-Content-Type-Options', 'nosniff');
    result.headers.set('Referrer-Policy', 'strict-origin-when-cross-origin');
    // Start HSTS on the publication's HTTPS hosts only. Do not extend it to
    // unrelated subdomains or the Pages preview domain.
    if (url.protocol === 'https:' &&
        ['thecurtain.online', 'www.thecurtain.online'].includes(url.hostname)) {
      result.headers.set('Strict-Transport-Security', 'max-age=2592000');
    }
    if (/^\/(?:tr\/|de\/|es\/)?rss\.xml$/.test(url.pathname) && response.status === 200) {
      result.headers.set('Content-Type', 'application/rss+xml; charset=utf-8');
      result.headers.set('Cache-Control', 'public, max-age=300, must-revalidate');
    }
    return result;
  },
};
