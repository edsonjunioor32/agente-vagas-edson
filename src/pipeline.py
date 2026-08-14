#!/usr/bin/env python3
import csv
import json
import os
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "perfil.json"
OUT = ROOT / "output"
DEFAULT_SOURCE = "https://raw.githubusercontent.com/edsonjunioor32/todas-as-vagas/main/docs/data/vagas.json"
SOURCE_URL = os.getenv("SOURCE_URL", DEFAULT_SOURCE)
MAX_JOBS = int(os.getenv("MAX_JOBS", "100"))
MIN_SCORE = int(os.getenv("MIN_SCORE", "35"))
MAX_AGE_DAYS = int(os.getenv("MAX_AGE_DAYS", "60"))
BR_TZ = timezone(timedelta(hours=-3))


def norm(value):
    text = str(value or "").lower().strip()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text)


def load_json_url(url):
    req = Request(url, headers={"User-Agent": "agente-vagas-edson/1.0"})
    with urlopen(req, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def decode_snapshot(data):
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []

    for key in ("vagas", "data", "items"):
        value = data.get(key)
        if isinstance(value, list):
            return value

    # Formato compacto usado pelo dashboard do todas-as-vagas.
    if isinstance(data.get("jobs"), dict) and isinstance(data.get("dict"), dict):
        dictionaries = data.get("dict") or {}
        jobs = data.get("jobs") or {}
        count = int(data.get("count") or len(jobs.get("title") or []))

        def arr(name):
            value = jobs.get(name)
            return value if isinstance(value, list) else []

        def at(name, index, default=""):
            values = arr(name)
            return values[index] if index < len(values) else default

        def lookup(name, code):
            values = dictionaries.get(name)
            if not isinstance(values, list):
                return ""
            try:
                idx = int(code)
            except (TypeError, ValueError):
                return ""
            return values[idx] if 0 <= idx < len(values) else ""

        output = []
        for index in range(count):
            output.append({
                "title": at("title", index),
                "company": lookup("company", at("cmp", index)),
                "source": lookup("source", at("src", index)),
                "work_model": lookup("work_model", at("wm", index)),
                "city": at("city", index),
                "country": lookup("country", at("co", index)),
                "market": lookup("market", at("mk", index)),
                "published_date": at("pub", index),
                "last_seen_at": at("seen", index),
                "url": at("url", index),
                "skills": at("sk", index),
                "categories": [lookup("area", at("area", index))],
                "seniority": lookup("seniority", at("sen", index)),
                "contract_types": str(at("ct", index) or "").split(" · ") if at("ct", index) else [],
                "description": "",
            })
        return output

    jobs = data.get("jobs")
    return jobs if isinstance(jobs, list) else []


def parse_date(value):
    if not value:
        return None
    raw = str(value).strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=BR_TZ)
        return dt.astimezone(BR_TZ)
    except ValueError:
        try:
            return datetime.strptime(raw[:10], "%Y-%m-%d").replace(tzinfo=BR_TZ)
        except ValueError:
            return None


def field(job, *names, default=""):
    for name in names:
        value = job.get(name)
        if value not in (None, "", []):
            return value
    return default


def canonical(job):
    return {
        "id": field(job, "id", "job_id"),
        "title": field(job, "title", "name", "job_title"),
        "company": field(job, "company", "company_name"),
        "url": field(job, "url", "job_url", "apply_url"),
        "source": field(job, "source", "portal"),
        "work_model": field(job, "work_model", "workModel", "remote"),
        "city": field(job, "city", "location"),
        "state": field(job, "state"),
        "country": field(job, "country", default="BR"),
        "market": field(job, "market", default="BR"),
        "published_date": field(job, "published_date", "publishedAt", "created_at", "date", "last_seen_at"),
        "description": field(job, "description", "summary"),
        "skills": field(job, "skills", default=[]),
        "categories": field(job, "categories", default=[]),
        "contract_types": field(job, "contract_types", "contractTypes", default=[]),
    }


def flatten(value):
    if isinstance(value, list):
        return " ".join(str(x) for x in value)
    if isinstance(value, dict):
        return " ".join(f"{k} {v}" for k, v in value.items())
    return str(value or "")


def score_job(job, profile):
    title = norm(job["title"])
    body = norm(" ".join([
        job["title"], job["company"], job["description"], job["work_model"],
        job["city"], flatten(job["skills"]), flatten(job["categories"]),
        flatten(job["contract_types"]),
    ]))
    score = 0
    reasons = []

    title_hits = [x for x in profile["titulos_prioritarios"] if norm(x) in title]
    if title_hits:
        score += min(38, 18 + 5 * len(title_hits))
        reasons.append("cargo aderente: " + ", ".join(title_hits[:3]))

    skill_hits = [x for x in profile["competencias_prioritarias"] if norm(x) in body]
    if skill_hits:
        score += min(35, 4 * len(skill_hits))
        reasons.append("competências: " + ", ".join(skill_hits[:6]))

    segment_hits = [x for x in profile["segmentos_prioritarios"] if norm(x) in body]
    if segment_hits:
        score += min(15, 5 * len(segment_hits))
        reasons.append("segmento: " + ", ".join(segment_hits[:3]))

    model = norm(job["work_model"] + " " + job["city"])
    if any(x in model for x in ("remoto", "remote", "home office", "anywhere")):
        score += 15
        reasons.append("trabalho remoto")
    elif "hibr" in model:
        score -= 8
        reasons.append("modelo híbrido")
    elif "presencial" in model or "on-site" in model or "onsite" in model:
        score -= 25
        reasons.append("modelo presencial")

    penalties = [x for x in profile["penalizar"] if norm(x) in body]
    if penalties:
        score -= min(35, 10 * len(penalties))
        reasons.append("penalidades: " + ", ".join(penalties[:3]))

    if any(x in title for x in ("senior", "sênior", "especialista", " sr ")):
        score += 3
    if any(x in title for x in ("estagio", "estágio", "trainee", "aprendiz")):
        score -= 30

    return max(0, min(100, score)), reasons


def main():
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    print(f"Fonte: {SOURCE_URL}")
    raw = decode_snapshot(load_json_url(SOURCE_URL))
    if not isinstance(raw, list):
        raise RuntimeError("Formato de fonte não reconhecido")

    print(f"Vagas recebidas da fonte: {len(raw)}")
    now = datetime.now(BR_TZ)
    cutoff = now - timedelta(days=MAX_AGE_DAYS)
    unique = {}

    for source_job in raw:
        if not isinstance(source_job, dict):
            continue
        job = canonical(source_job)
        if not job["title"] or not job["url"]:
            continue
        market = norm(job["market"] + " " + job["country"])
        if market and not any(x in market for x in ("br", "brasil", "brazil")):
            continue
        published = parse_date(job["published_date"])
        if published and published > now + timedelta(minutes=5):
            published = now
        if published and published < cutoff:
            continue
        job["published_at_br"] = published.isoformat() if published else ""
        job["score"], job["reasons"] = score_job(job, profile)
        if job["score"] < MIN_SCORE:
            continue
        key = norm(job["url"]) or f"{norm(job['title'])}|{norm(job['company'])}"
        current = unique.get(key)
        if not current or job["score"] > current["score"]:
            unique[key] = job

    jobs = list(unique.values())
    jobs.sort(key=lambda j: (j["score"], j["published_at_br"]), reverse=True)
    jobs = jobs[:MAX_JOBS]

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "vagas_ranqueadas.json").write_text(
        json.dumps({"generated_at": now.isoformat(), "count": len(jobs), "jobs": jobs}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    columns = ["score", "published_at_br", "title", "company", "work_model", "city", "source", "url", "reasons"]
    with (OUT / "vagas_ranqueadas.csv").open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for job in jobs:
            row = dict(job)
            row["reasons"] = " | ".join(job["reasons"])
            writer.writerow(row)

    lines = [f"# Vagas priorizadas — {now.strftime('%d/%m/%Y %H:%M')} (UTC-3)", "", f"Total: **{len(jobs)}**", ""]
    for idx, job in enumerate(jobs[:30], 1):
        lines += [
            f"## {idx}. {job['title']} — {job['company']} ({job['score']}%)",
            f"- Modelo/local: {job['work_model'] or 'não informado'} · {job['city'] or 'não informado'}",
            f"- Fonte: {job['source'] or 'não informada'}",
            f"- Publicação: {job['published_at_br'] or 'não informada'}",
            f"- Motivos: {'; '.join(job['reasons'])}",
            f"- Link: {job['url']}", "",
        ]
    (OUT / "resumo.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Pipeline concluído: {len(jobs)} vagas com score >= {MIN_SCORE}.")


if __name__ == "__main__":
    main()
