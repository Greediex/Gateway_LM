"""Public iGate passages and curated FAQ matching, isolated from evidence."""
from __future__ import annotations

import json
import re

from ..rag import lexical_scores
from .igate_proposal import fold

QUESTION = {
    'vi': re.compile(r'\b(?:la gi|nghia la gi|khac nhau|so sanh|lam sao|the nao|cach|giai thich|nen dat|nen dung|huong dan)\b'),
    'en': re.compile(r'^(?:what (?:is|are|does)|how (?:to|can|do|does)|where (?:to|should)|why does|'
                     r'explain|compare|difference between|tips for|where is)\b'),
}
QUERY_PREFIX = {
    'vi': r'^(?:lam sao (?:de )?|cach |huong dan |giai thich )',
    'en': r'^(?:how (?:to|can i|do i|does)|what (?:is|are|does)|where (?:to|should i)|explain) ',
}
PASSAGE = re.compile(r'^## ([^\n]+)\n<!-- id: ([^ |]+)([^\n]*) -->\n(.+?)(?=^## |\Z)', re.M | re.S)


def _terms(text: str) -> str:
    return re.sub(r'\bwi[ -]?fi[ -]?(?=\d)', 'wifi', re.sub(r'\bwi[ -]fi\b', 'wifi', fold(text)))


def _passages(vendor: dict[str, bytes], lang: str) -> dict:
    docs = {doc for topic in json.loads(vendor['kb_src/manifest.json'])['topics']
            if topic['visibility'] == 'public' for doc in topic['documents'] if doc.endswith('.' + lang)}
    passages = {}
    for doc in sorted(docs):
        content = vendor[f'kb_src/{doc}.md'].decode().replace('\r\n', '\n')
        for title, pid, meta, raw_body in PASSAGE.findall(content):
            aliases = re.search(r'\| aliases: ([^|]+)', meta)
            body = raw_body.strip()
            if body:
                index = _terms(f'{title} {aliases[1] if aliases else ""}')
                passages[pid] = (body, doc, index)
    return passages


def knowledge(request: str, vendor: dict[str, bytes]) -> dict | None:
    text = _terms(request)
    groups = json.loads(vendor['kb_src/answer_cache.json'])['groups']
    hits = [group for group in groups if not group.get('pick_only')
            and text in {_terms(phrase) for phrase in group.get('variants', [])}
            and text not in {_terms(phrase) for phrase in group.get('negatives', [])}]
    if len(hits) == 1:
        hit = hits[0]
        return {'kind': 'instant', 'method': 'igate_answer_cache', 'answer': hit['answer'],
                'knowledge': {'label': 'kiến thức (draft)', 'language': hit['lang'],
                              'passages': hit['passages'], 'cache_id': hit['id']}}
    lang = next((lang for lang, pattern in QUESTION.items() if pattern.search(text)), None)
    if lang is None:
        return None
    passages = _passages(vendor, lang)
    query = re.sub(QUERY_PREFIX[lang], '', text)
    if lang == 'en':
        query = re.sub(r'\b(?:improve|strengthen)\b', 'boost', query)
        query = re.sub(r'\b(?:place|position|put)\b', 'placement', query)
    scores = lexical_scores(query, {pid: passage[2] for pid, passage in passages.items()})
    if not scores:
        scores = lexical_scores(query, {pid: passage[0] for pid, passage in passages.items()})
    if not scores:
        return None
    pid = min(scores, key=lambda key: (-scores[key], key))
    body, doc, _ = passages[pid]
    return {'kind': 'knowledge', 'method': 'igate_bm25', 'answer': body,
            'knowledge': {'label': 'kiến thức (draft)', 'language': lang, 'passages': [pid],
                          'document': doc}}
