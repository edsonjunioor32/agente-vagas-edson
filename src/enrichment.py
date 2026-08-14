import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript", "svg", "template"}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript", "svg", "template"} and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip:
            value = re.sub(r"\s+", " ", data).strip()
            if len(value) >= 2:
                self.parts.append(value)


def strip_html(value):
    if not value:
        return ""
    parser = VisibleTextParser()
    try:
        parser.feed(str(value))
        text = " ".join(parser.parts)
    except Exception:
        text = re.sub(r"<[^>]+>", " ", str(value))
    return re.sub(r"\s+", " ", unescape(text)).strip()


def walk_jobposting(value):
    if isinstance(value, list):
        for item in value:
            found = walk_jobposting(item)
            if found:
                return found
        return None
    if not isinstance(value, dict):
        return None
    kind = value.get("@type")
    kinds = kind if isinstance(kind, list) else [kind]
    if any(str(x).lower() == "jobposting" for x in kinds if x):
        return value
    graph = value.get("@graph")
    if graph:
        found = walk_jobposting(graph)
        if found:
            return found
    for child in value.values():
        if isinstance(child, (dict, list)):
            found = walk_jobposting(child)
            if found:
                return found
    return None


def posting_text(posting):
    fields = [
        posting.get("description"), posting.get("responsibilities"),
        posting.get("qualifications"), posting.get("skills"),
        posting.get("experienceRequirements"), posting.get("educationRequirements"),
    ]
    return strip_html(" ".join(str(x) for x in fields if x))


def extract_description_from_html(html_text):
    pattern = re.compile(
        r"<script\b[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        re.I | re.S,
    )
    for match in pattern.finditer(html_text):
        raw = unescape(match.group(1)).strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        posting = walk_jobposting(data)
        if posting:
            description = posting_text(posting)
            if len(description) >= 180:
                return description[:30000], "json-ld"

    parser = VisibleTextParser()
    try:
        parser.feed(html_text)
        visible = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
    except Exception:
        visible = ""
    if len(visible) >= 700:
        return visible[:30000], "html-text"
    return "", ""


def fetch_job_description(url, timeout=10, max_bytes=2500000):
    result = {"status": "not_available", "method": "", "error": "", "description": ""}
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            result["error"] = "URL não HTTP(S)"
            return result
        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; AgenteVagasEdson/2.0)",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
        })
        with urlopen(req, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            charset = response.headers.get_content_charset() or "utf-8"
            payload = response.read(max_bytes + 1)[:max_bytes]
        body = payload.decode(charset, errors="replace")

        if "json" in content_type.lower():
            try:
                posting = walk_jobposting(json.loads(body))
                if posting:
                    description = posting_text(posting)
                    if len(description) >= 180:
                        return {"status": "enriched", "method": "json", "error": "", "description": description[:30000]}
            except json.JSONDecodeError:
                pass

        description, method = extract_description_from_html(body)
        if description:
            return {"status": "enriched", "method": method, "error": "", "description": description}
        result["error"] = "descrição útil não encontrada"
    except Exception as exc:
        result["status"] = "error"
        result["error"] = f"{type(exc).__name__}: {str(exc)[:180]}"
    return result


def enrich_jobs(jobs, score_fn, limit=40, workers=6, timeout=10, max_bytes=2500000):
    candidates = [
        job for job in jobs[:limit]
        if int(job.get("coverage") or 0) < 85 or len(str(job.get("description") or "")) < 200
    ]
    stats = {"attempted": len(candidates), "enriched": 0, "failed": 0}
    if not candidates:
        return stats

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(fetch_job_description, job["url"], timeout, max_bytes): job
            for job in candidates
        }
        for future in as_completed(futures):
            job = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {"status": "error", "method": "", "error": f"{type(exc).__name__}: {str(exc)[:180]}", "description": ""}
            previous = str(job.get("description") or "")
            fetched = result.get("description") or ""
            job["enrichment_status"] = result.get("status", "error")
            job["enrichment_method"] = result.get("method", "")
            job["enrichment_error"] = result.get("error", "")
            if len(fetched) > max(180, len(previous)):
                job["description"] = fetched
                stats["enriched"] += 1
            elif job["enrichment_status"] != "enriched":
                stats["failed"] += 1
            job["description_length"] = len(str(job.get("description") or ""))
            job["score"], job["reasons"] = score_fn(job, None)
    return stats
