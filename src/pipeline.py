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
BR_TZ = timezone(timedelta(hours=-3))


def env_int(name, default, minimum=0, maximum=None):
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{name} deve ser um número inteiro; recebido: {raw!r}") from exc
    if value < minimum or (maximum is not None and value > maximum):
        raise RuntimeError(f"{name} fora do intervalo permitido: {value}")
    return value


MAX_JOBS = env_int("MAX_JOBS", 100, 1, 1000)
MIN_SCORE = env_int("MIN_SCORE", 35, 0, 100)
MAX_AGE_DAYS = env_int("MAX_AGE_DAYS", 60, 1, 365)
ONLY_REMOTE = os.getenv("ONLY_REMOTE", "true").strip().lower() not in {"0", "false", "no"}


def text(value):
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return flatten(value)
    return str(value)


def norm(value):
    value = text(value)
    value = value.lower().strip()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", value)


def load_json_url(url):
    req = Request(url, headers={"User-Agent": "agente-vagas-edson/1.1", "Accept": "application/json"})
    with urlopen(req, timeout=120) as response:
        content_type = response.headers.get("Content-Type", "")
        payload = response.read()
    if not payload:
        raise RuntimeError("Fonte retornou conteúdo vazio")
    try:
        return json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Fonte não retornou JSON válido (Content-Type: {content_type})") from exc


def decode_snapshot(data):
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        raise RuntimeError(f"Snapshot inválido: esperado objeto/lista, recebido {type(data).__name__}")

    for key in ("vagas", "data", "items"):
        value = data.get(key)
        if isinstance(value, list):
            return value

    if isinstance(data.get("jobs"), list):
        return data["jobs"]

    if isinstance(data.get("jobs"), dict) and isinstance(data.get("dict"), dict):
        dictionaries = data.get("dict") or {}
        jobs = data.get("jobs") or {}
        titles = jobs.get("title")
        if not isinstance(titles, list):
            raise RuntimeError("Snapshot compacto sem jobs.title")
        try:
            count = int(data.get("count", len(titles)))
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Snapshot compacto com count inválido") from exc
        if count < 0 or count > len(titles):
            raise RuntimeError(f"Snapshot compacto inconsistente: count={count}, títulos={len(titles)}")

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
            contracts_raw = text(at("ct", index))
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
                "contract_types": [x.strip() for x in contracts_raw.split(" · ") if x.strip()],
                "description": "",
            })
        return output

    raise RuntimeError("Formato de snapshot não reconhecido")


def parse_date(value):
    if not value:
        return None
    raw = text(value).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        try:
            return datetime.strptime(raw, "%Y-%m-%d").replace(hour=12, tzinfo=BR_TZ)
        except ValueError:
            return None
    raw = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=BR_TZ)
    return dt.astimezone(BR_TZ)


def field(job, *names, default=""):
    for name in names:
        value = job.get(name)
        if value not in (None, "", []):
            return value
    return default


def canonical(job):
    return {
        "id": text(field(job, "id", "job_id")),
        "title": text(field(job, "title", "name", "job_title")),
        "company": text(field(job, "company", "company_name")),
        "url": text(field(job, "url", "job_url", "apply_url")),
        "source": text(field(job, "source", "portal")),
        "work_model": text(field(job, "work_model", "workModel", "remote")),
        "city": text(field(job, "city", "location")),
        "state": text(field(job, "state")),
        "country": text(field(job, "country", default="BR")),
        "market": text(field(job, "market", default="BR")),
        "published_date": field(job, "published_date", "publishedAt", "created_at", "date", "last_seen_at"),
        "description": text(field(job, "description", "summary")),
        "skills": field(job, "skills", default=[]),
        "categories": field(job, "categories", "category", default=[]),
        "contract_types": field(job, "contract_types", "contractTypes", default=[]),
        "seniority": text(field(job, "seniority")),
    }


def flatten(value):
    if isinstance(value, list):
        return " ".join(text(x) for x in value)
    if isinstance(value, dict):
        return " ".join(f"{k} {text(v)}" for k, v in value.items())
    return str(value or "")


def is_remote(job):
    model = norm(f"{job['work_model']} {job['city']}")
    return any(x in model for x in ("remote", "remoto", "home office", "home-office", "anywhere", "totalmente remoto"))


def score_job(job, profile):
    title = norm(job["title"])
    body = norm(" ".join([
        job["title"], job["company"], job["description"], job["work_model"],
        job["city"], job["seniority"], flatten(job["skills"]), flatten(job["categories"]),
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

    if is_remote(job):
        score += 15
        reasons.append("trabalho remoto")
    else:
        model = norm(f"{job['work_model']} {job['city']}")
        if "hibr" in model or "hybrid" in model:
            score -= 15
            reasons.append("modelo híbrido")
        elif any(x in model for x in ("presencial", "on-site", "onsite")):
            score -= 30
            reasons.append("modelo presencial")

    penalties = [x for x in profile["penalizar"] if norm(x) in body]
    if penalties:
        score -= min(35, 10 * len(penalties))
        reasons.append("penalidades: " + ", ".join(penalties[:3]))

    if "customer success" in title and not any(
        token in body for token in ("api", "integr", "technical", "tecnico", "técnico", "sql", "b2b", "pagament", "payment")
    ):
        score -= 12
        reasons.append("CS sem sinal técnico forte")

    if any(x in title for x in ("estagio", "estágio", "trainee", "aprendiz")):
        score -= 30

    return max(0, min(100, score)), reasons


def main():
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    required_profile_keys = {"titulos_prioritarios", "competencias_prioritarias", "segmentos_prioritarios", "penalizar"}
    missing = required_profile_keys.difference(profile)
    if missing:
        raise RuntimeError("Perfil incompleto; faltam: " + ", ".join(sorted(missing)))

    print(f"Fonte: {SOURCE_URL}")
    raw = decode_snapshot(load_json_url(SOURCE_URL))
    if not raw:
        raise RuntimeError("Fonte decodificada sem vagas")

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

        market = norm(f"{job['market']} {job['country']}")
        if market and not any(x in market for x in ("br", "brasil", "brazil")):
            continue
        if ONLY_REMOTE and not is_remote(job):
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
