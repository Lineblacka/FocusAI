import html
import json
import logging
import re
from typing import Any, Dict, List
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import cloudscraper


logger = logging.getLogger(__name__)


class WebSearchService:
    AUTO_TRIGGERS = [
        'днес',
        'днешн',
        'сега',
        'новини',
        'ново',
        'последно',
        'последните',
        'актуално',
        'актуални',
        'в момента',
        'цена',
        'цени',
        'курс',
        'времето',
        'температура',
        'резултат',
        'резултати',
        'мач',
        'кой е',
        'кога е',
        'къде е',
        'release',
        'latest',
        'today',
        'current',
        'news',
        'price',
        'weather',
        'score',
        'search',
        'internet',
        'онлайн',
        'потърси',
        'провери',
        'виж дали',
    ]

    def __init__(self, timeout_seconds: int = 12):
        self.timeout_seconds = timeout_seconds
        self.user_agent = 'FocusAI/1.0 (+https://github.com/Lineblacka)'
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
        )
        self.scraper.headers.update({'User-Agent': self.user_agent})

    def should_search(self, query: str, preference: str = 'auto') -> bool:
        if preference == 'on':
            return True
        if preference == 'off':
            return False

        normalized = query.lower().strip()
        return any(trigger in normalized for trigger in self.AUTO_TRIGGERS)

    def build_context(self, query: str, preference: str = 'auto') -> tuple[str | None, Dict[str, Any]]:
        if not self.should_search(query, preference):
            return None, {'used': False, 'query': query, 'results': []}

        results = self.search(query)
        if not results:
            return None, {'used': False, 'query': query, 'results': []}

        lines = [
            'Свеж уеб контекст за текущата заявка:',
            f'Търсене: {query}',
            'Използвай само ако помага. Ако има несигурност, кажи го ясно.',
        ]
        for index, item in enumerate(results, start=1):
            lines.append(f'{index}. {item["title"]}')
            lines.append(f'URL: {item["url"]}')
            lines.append(f'Резюме: {item["snippet"]}')

        return '\n'.join(lines), {'used': True, 'query': query, 'results': results}

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        results: List[Dict[str, str]] = []

        instant = self._fetch_instant_answer(query)
        if instant:
            results.append(instant)

        html_results = self._fetch_html_results(query, max_results=max_results)
        results.extend(html_results)

        deduped: List[Dict[str, str]] = []
        seen_urls = set()
        for item in results:
            url = item.get('url')
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            deduped.append(item)

        return deduped[:max_results]

    def _fetch_text(self, url: str) -> str:
        response = self.scraper.get(url, timeout=self.timeout_seconds)
        response.raise_for_status()
        response.encoding = response.encoding or 'utf-8'
        return response.text

    def _fetch_instant_answer(self, query: str) -> Dict[str, str] | None:
        try:
            url = f'https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_redirect=1&no_html=1&skip_disambig=1'
            payload = json.loads(self._fetch_text(url))
        except Exception:
            logger.exception('duckduckgo_instant_answer_failed')
            return None

        title = (payload.get('Heading') or '').strip()
        snippet = (payload.get('AbstractText') or payload.get('Answer') or '').strip()
        source_url = (payload.get('AbstractURL') or '').strip()

        if title and snippet and source_url:
            return {'title': title, 'snippet': snippet, 'url': source_url}
        return None

    def _fetch_html_results(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        try:
            raw_html = self._fetch_text(f'https://html.duckduckgo.com/html/?q={quote_plus(query)}')
        except Exception:
            logger.exception('duckduckgo_html_search_failed')
            return []

        blocks = re.findall(r'<div class="result results_links.*?</div>\s*</div>\s*</div>', raw_html, flags=re.S)
        results: List[Dict[str, str]] = []

        for block in blocks:
            title_match = re.search(r'class="result__a" href="([^"]+)".*?>(.*?)</a>', block, flags=re.S)
            snippet_match = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', block, flags=re.S)
            if not title_match:
                continue

            duck_url = html.unescape(title_match.group(1))
            title = self._strip_tags(title_match.group(2))
            snippet = self._strip_tags(snippet_match.group(1)) if snippet_match else ''
            final_url = self._resolve_duckduckgo_url(duck_url)

            if not title or not final_url:
                continue

            results.append({
                'title': title,
                'snippet': snippet or title,
                'url': final_url,
            })

            if len(results) >= max_results:
                break

        return results

    def _resolve_duckduckgo_url(self, url: str) -> str:
        if url.startswith('//'):
            url = f'https:{url}'
        if 'duckduckgo.com/l/' not in url:
            return url

        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        target = params.get('uddg', [''])[0]
        return unquote(target) if target else url

    def _strip_tags(self, value: str) -> str:
        text = re.sub(r'<[^>]+>', ' ', value)
        text = html.unescape(text)
        return re.sub(r'\s{2,}', ' ', text).strip()
