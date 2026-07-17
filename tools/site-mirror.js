#!/usr/bin/env node
/**
 * Thin CLI over website-scraper (https://github.com/website-scraper/node-website-scraper).
 * JARVIS shells out to this to mirror a site's public front end for offline reading.
 *
 *   node site-mirror.js --url <url> --out <dir> [--depth 1] [--max 200]
 */
import scrape from 'website-scraper';
import { rm, mkdir } from 'node:fs/promises';
import path from 'node:path';

function arg(name, dflt = null) {
  const i = process.argv.indexOf(`--${name}`);
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : dflt;
}

const url = arg('url');
const out = arg('out');
const depth = parseInt(arg('depth', '1'), 10);
const max = parseInt(arg('max', '200'), 10);

if (!url || !out) {
  console.error('usage: site-mirror.js --url <url> --out <dir> [--depth 1] [--max 200]');
  process.exit(2);
}

// website-scraper refuses to write into an existing directory.
await rm(out, { recursive: true, force: true });
await mkdir(path.dirname(path.resolve(out)), { recursive: true });

let count = 0;
const limiter = {
  apply(register) {
    register('beforeRequest', async ({ resource }) => {
      if (count >= max) return { action: 'abort' };
      count += 1;
      return { resource };
    });
  },
};

try {
  const result = await scrape({
    urls: [url],
    directory: out,
    recursive: depth > 0,
    maxRecursiveDepth: depth,
    maxDepth: depth + 1,
    prettifyUrls: true,
    ignoreErrors: true,
    plugins: [limiter],
    // grab the whole front end: markup, styles, scripts, media, fonts
    sources: [
      { selector: 'img', attr: 'src' },
      { selector: 'img', attr: 'srcset' },
      { selector: 'source', attr: 'src' },
      { selector: 'source', attr: 'srcset' },
      { selector: 'link[rel="stylesheet"]', attr: 'href' },
      { selector: 'link[rel*="icon"]', attr: 'href' },
      { selector: 'script', attr: 'src' },
      { selector: 'video', attr: 'src' },
      { selector: 'audio', attr: 'src' },
      { selector: 'object', attr: 'data' },
      { selector: '[style]', attr: 'style' },
      { selector: 'style' },
    ],
  });
  const pages = Array.isArray(result) ? result.length : 1;
  console.log(JSON.stringify({ ok: true, url, out, pages, resources: count }));
} catch (e) {
  console.log(JSON.stringify({ ok: false, url, error: String(e && e.message || e) }));
  process.exit(1);
}
