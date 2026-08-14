#!/usr/bin/env python3
import csv
import json
import os

import pipeline
from enrichment import enrich_jobs
from scoring_v2 import score_job, is_remote

pipeline.score_job = score_job
pipeline.is_remote = is_remote

ENRICH_LIMIT = pipeline.env_int("ENRICH_LIMIT", 40, 0, 200)
ENRICH_WORKERS = pipeline.env_int("ENRICH_WORKERS", 6, 1, 16)
ENRICH_TIMEOUT = pipeline.env_int("ENRICH_TIMEOUT", 10, 3, 30)
MAX_HTML_BYTES = pipeline.env_int("MAX_HTML_BYTES", 2500000, 100000, 5000000)


def prepare_jobs(profile):
    raw = pipeline.decode_snapshot(pipeline.load_json_url(pipeline.SOURCE_URL))
    if not raw:
        raise RuntimeError("Fonte decodificada sem vagas")

    print(f"Fonte: {pipeline.SOURCE_URL}")
    print(f"Vagas recebidas da fonte: {len(raw)}")
    now = pipeline.datetime.now(pipeline.BR_TZ)
    cutoff = now - pipeline.timedelta(days=pipeline.MAX_AGE_DAYS)
    unique = {}

    for source_job in raw:
        if not isinstance(source_job, dict):
            continue
        job = pipeline.canonical(source_job)
        if not job["title"] or not job["url"]:
            continue

        market = pipeline.norm(f"{job['market']} {job['country']}")
        if market and not any(x in market for x in ("br", "brasil", "brazil")):
            continue
        if pipeline.ONLY_REMOTE and not is_remote(job):
            continue

        published = pipeline.parse_date(job["published_date"])
        if published and published > now + pipeline.timedelta(minutes=5):
            published = now
        if published and published < cutoff:
            continue

        job["published_at_br"] = published.isoformat() if published else ""
        job["score"], job["reasons"] = score_job(job, profile)

        key = pipeline.norm(job["url"]) or f"{pipeline.norm(job['title'])}|{pipeline.norm(job['company'])}"
        current = unique.get(key)
        if not current or (job["score"], job.get("coverage", 0)) > (current["score"], current.get("coverage", 0)):
            unique[key] = job

    jobs = list(unique.values())
    jobs.sort(key=lambda j: (j["score"], j.get("coverage", 0), j["published_at_br"]), reverse=True)
    return jobs, now


def write_outputs(jobs, now, enrichment_stats):
    jobs = [job for job in jobs if int(job.get("score") or 0) >= pipeline.MIN_SCORE]
    jobs.sort(key=lambda j: (j["score"], j.get("coverage", 0), j["published_at_br"]), reverse=True)
    jobs = jobs[:pipeline.MAX_JOBS]

    pipeline.OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": now.isoformat(),
        "count": len(jobs),
        "enrichment": enrichment_stats,
        "jobs": jobs,
    }
    (pipeline.OUT / "vagas_ranqueadas.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    columns = [
        "score", "coverage", "observed_fit", "published_at_br", "title", "company",
        "work_model", "city", "source", "enrichment_status", "enrichment_method",
        "description_length", "url", "reasons",
    ]
    with (pipeline.OUT / "vagas_ranqueadas.csv").open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for job in jobs:
            row = dict(job)
            row["reasons"] = " | ".join(job.get("reasons") or [])
            writer.writerow(row)

    lines = [
        f"# Vagas priorizadas — {now.strftime('%d/%m/%Y %H:%M')} (UTC-3)", "",
        f"Total: **{len(jobs)}**",
        f"Enriquecimento: **{enrichment_stats['enriched']}/{enrichment_stats['attempted']}** vagas com descrição ampliada", "",
    ]
    for idx, job in enumerate(jobs[:30], 1):
        status = job.get("enrichment_status", "não tentado")
        method = job.get("enrichment_method")
        if method:
            status += f" ({method})"
        lines += [
            f"## {idx}. {job['title']} — {job['company']} ({job['score']}%)",
            f"- Cobertura: {job.get('coverage', 0)}% · Fit observado: {job.get('observed_fit', 0)}%",
            f"- Enriquecimento: {status}",
            f"- Modelo/local: {job['work_model'] or 'não informado'} · {job['city'] or 'não informado'}",
            f"- Fonte: {job['source'] or 'não informada'}",
            f"- Publicação: {job['published_at_br'] or 'não informada'}",
            f"- Motivos: {'; '.join(job.get('reasons') or [])}",
            f"- Link: {job['url']}", "",
        ]
    (pipeline.OUT / "resumo.md").write_text("\n".join(lines), encoding="utf-8")
    print(
        f"Pipeline concluído: {len(jobs)} vagas; "
        f"enriquecimento {enrichment_stats['enriched']}/{enrichment_stats['attempted']}."
    )


def main():
    profile = json.loads(pipeline.PROFILE_PATH.read_text(encoding="utf-8"))
    jobs, now = prepare_jobs(profile)

    enrichment_stats = enrich_jobs(
        jobs,
        score_fn=score_job,
        limit=ENRICH_LIMIT,
        workers=ENRICH_WORKERS,
        timeout=ENRICH_TIMEOUT,
        max_bytes=MAX_HTML_BYTES,
    )

    jobs.sort(key=lambda j: (j["score"], j.get("coverage", 0), j["published_at_br"]), reverse=True)
    write_outputs(jobs, now, enrichment_stats)


if __name__ == "__main__":
    main()
