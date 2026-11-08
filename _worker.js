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
  '/covers/van-gogh-wheat-field-final-days.png': '/covers/van-gogh-wheat-field-final-days.webp',
  '/covers/gerrothorax-maritimus-marine-amphibian.png': '/covers/gerrothorax-maritimus-marine-amphibian.webp',
  '/covers/olympia-paris-salon-1865.png': '/covers/olympia-paris-salon-1865.webp',
  '/covers/bolivia-tilcayo-new-wild-cat.png': '/covers/bolivia-tilcayo-new-wild-cat.webp',
  '/covers/amsterdam-art-zoo-visitors-behind-bars.png': '/covers/amsterdam-art-zoo-visitors-behind-bars.webp',
  '/covers/iran-no-limits-gulf-countdown.png': '/covers/iran-no-limits-gulf-countdown.webp',
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

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

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
  },
};
