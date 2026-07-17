# -*- coding: utf-8 -*-
"""A one-off Scrapy spider JARVIS runs via `scrapy runspider`.

No project scaffolding needed. Stays on the starting domain, obeys robots.txt,
and stops after `maxpages`.

    scrapy runspider quick_spider.py -a start=https://example.com -a maxpages=50 -o out.jsonl
"""
from urllib.parse import urlparse

import scrapy


class QuickSpider(scrapy.Spider):
    name = "quick"
    custom_settings = {
        "ROBOTSTXT_OBEY": True,
        "DOWNLOAD_DELAY": 0.25,
        "CONCURRENT_REQUESTS_PER_DOMAIN": 4,
        "USER_AGENT": "JARVIS-archiver (+https://github.com/Shreyaspro-ai/jarvis-mark-xlviii)",
        "DEPTH_LIMIT": 3,
        "HTTPERROR_ALLOW_ALL": False,
    }

    def __init__(self, start=None, maxpages=50, *a, **kw):
        super().__init__(*a, **kw)
        if not start:
            raise ValueError("pass -a start=<url>")
        self.start_urls = [start]
        self.allowed_domains = [urlparse(start).netloc]
        self.maxpages = int(maxpages)
        self.seen = 0

    def parse(self, response):
        if self.seen >= self.maxpages:
            return
        self.seen += 1

        ctype = response.headers.get("Content-Type", b"").decode("latin-1")
        if "html" not in ctype.lower():
            return

        yield {
            "url": response.url,
            "status": response.status,
            "title": (response.css("title::text").get() or "").strip(),
            "h1": [h.strip() for h in response.css("h1::text").getall()][:5],
            "description": response.css('meta[name="description"]::attr(content)').get(),
            "links": len(response.css("a::attr(href)").getall()),
            "scripts": response.css("script::attr(src)").getall()[:20],
            "text": " ".join(response.css("p::text").getall())[:1000],
        }

        for href in response.css("a::attr(href)").getall():
            if self.seen >= self.maxpages:
                return
            yield response.follow(href, callback=self.parse)
