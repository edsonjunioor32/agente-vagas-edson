import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.request import Request, urlopen

INHIRE_API = "https://api.inhire.app/job-posts/public/pages"


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
    pattern = re.compile(r"<script\b[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.I | re.S)
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


def parse_inhire_url(url):
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    match = re.fullmatch(r"([a-z0-9-]+)\.inhire\.app", host)
    if not match:
        return None
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2 or parts[0].lower() != "vagas":
        return None
    tenant = match.group(1)
    job_id = parts[1]
    if not re.fullmatch(r"[A-Za-z0-9._:-]{4,120}", job_id):
        return None
    return tenant, job_id


def extract_inhire_description(detail):
    if not isinstance(detail, dict):
        return ""
    fields = [
        detail.get("description"), detail.get("responsibilities"), detail.get("requirements"),
        detail.get("qualifications"), detail.get("skills"), detail.get("benefits"),
    ]
    description = strip_html(" ".join(str(x) for x in fields if x))
    return description[:30000] if len(description) >= 180 else ""


def fetch_inhire_description(url, timeout=10, max_bytes=2500000):
    parsed = parse_inhire_url(url)
    if not parsed:
        return None
    tenant, job_id = parsed
    endpoint = f"{INHIRE_API}/{job_id}"
    last_error = ""
    for attempt in range(2):
        req = Request(endpoint, headers={
            "X-Inhire-Client": "web-inhire", "X-Tenant": tenant,
            "Content-Type": "application/json", "Accept": "application/json",
            "User-Agent": "AgenteVagasEdson/2.2",
        })
        try:
            with urlopen(req, timeout=timeout) as response:
                payload = response.read(max_bytes + 1)[:max_bytes]
            detail = json.loads(payload.decode("utf-8-sig", errors="replace"))
            description = extract_inhire_description(detail)
            if description:
                return {"status": "enriched", "method": "inhire-api", "error": "", "description": description}
            return {"status": "not_available", "method": "inhire-api", "error": "descrição útil não encontrada", "description": ""}
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {str(exc)[:180]}"
            if attempt == 0:
                continue
    return {"status": "error", "method": "inhire-api", "error": last_error, "description": ""}


def fetch_generic_description(url, timeout=10, max_bytes=2500000):
    result = {"status": "not_available", "method": "", "error": "", "description": ""}
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            result["error"] = "URL não HTTP(S)"
            return result
        req = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; AgenteVagasEdson/2.2)",
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


def fetch_job_description(url, timeout=10, max_bytes=2500000):
    specific = fetch_inhire_description(url, timeout, max_bytes)
    if specific and specific.get("status") == "enriched":
        return specific
    generic = fetch_generic_description(url, timeout, max_bytes)
    if generic.get("status") == "enriched":
        return generic
    if specific:
        if generic.get("error"):
            specific["error"] = f"{specific.get('error','')}; fallback: {generic['error']}".strip("; ")
        return specific
    return generic


def summarize_enrichment(jobs):
    attempted_jobs = [job for job in jobs if int(job.get("enrichment_attempts") or 0) > 0]
    enriched_jobs = [job for job in attempted_jobs if job.get("enrichment_status") == "enriched"]
    methods = {}
    for job in enriched_jobs:
        method = job.get("enrichment_method") or "unknown"
        methods[method] = methods.get(method, 0) + 1
    return {
        "attempted": len(attempted_jobs),
        "enriched": len(enriched_jobs),
        "failed": len(attempted_jobs) - len(enriched_jobs),
        "methods": methods,
    }


def enrich_jobs(jobs, score_fn, limit=40, workers=6, timeout=10, max_bytes=2500000, max_attempts=1):
    candidates = [
        job for job in jobs[:limit]
        if (int(job.get("coverage") or 0) < 85 or len(str(job.get("description") or "")) < 200)
        and int(job.get("enrichment_attempts") or 0) < max_attempts
    ]
    if not candidates:
        return summarize_enrichment(jobs)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch_job_description, job["url"], timeout, max_bytes): job for job in candidates}
        for future in as_completed(futures):
            job = futures[future]
            job["enrichment_attempts"] = int(job.get("enrichment_attempts") or 0) + 1
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
                job["enrichment_status"] = "enriched"
            job["description_length"] = len(str(job.get("description") or ""))
            job["score"], job["reasons"] = score_fn(job, None)
    return summarize_enrichment(jobs)
