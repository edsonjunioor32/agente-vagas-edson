#!/usr/bin/env python3
"""Generate a vacancy-targeted ATS-friendly LaTeX resume using verified facts only."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

from scoring_v2 import score_job


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JOBS = ROOT / "output" / "vagas_ranqueadas.json"
DEFAULT_PROFILE = ROOT / "resume" / "base_profile.json"
DEFAULT_OUT = ROOT / "output" / "curriculo_ats"

# Requirements that may appear in jobs but are intentionally NOT assumed as candidate skills.
# They are used only to flag possible gaps in the report.
TRACKED_GAPS = {
    ".NET/C#": [".net", "c#", "asp.net", "razor"],
    "Java/Spring": ["java", "spring boot", "springboot", "spring framework"],
    "PL/SQL": ["pl/sql", "plsql"],
    "Linux": ["linux", "unix"],
    "Cloud/AWS": ["aws", "amazon web services"],
    "Cloud/Azure": ["azure", "azure devops"],
    "Cloud/GCP": ["gcp", "google cloud"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Docker": ["docker", "containers", "containerização", "containerizacao"],
    "Python": ["python"],
    "Inglês": ["inglês", "ingles", "english"],
}

SKILL_CATEGORIES = [
    ("Suporte e Sustentação", ["Suporte N2", "Sustentação de Sistemas", "Gestão de Incidentes", "RCA", "Troubleshooting", "SLA", "GMUD", "Gestão de Backlog", "Documentação Técnica"]),
    ("Dados e Diagnóstico", ["SQL", "Oracle", "Logs", "Testes Funcionais", "Homologação"]),
    ("Observabilidade", ["Splunk", "Datadog", "Grafana", "Observabilidade"]),
    ("Integrações", ["APIs REST", "Webhooks", "Postman"]),
    ("Pagamentos e Cartões", ["Meios de Pagamento", "Cartões", "Autorização", "Conciliação", "Faturas", "Embossing", "B2B"]),
    ("Ferramentas e Processos", ["Jira", "Zendesk", "ITIL", "Metodologias Ágeis", "Ambientes Microsoft/Web", "ERP/Automação Comercial"]),
]


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip()


def contains(text: str, term: str) -> bool:
    token = norm(term)
    if not token:
        return False
    if re.fullmatch(r"[a-z0-9.+#/-]{1,4}", token):
        return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", text) is not None
    return token in text


def latex(value: object) -> str:
    text = str(value or "")
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in text)


def job_text(job: dict) -> str:
    values = [
        job.get("title", ""), job.get("company", ""), job.get("description", ""),
        job.get("skills", ""), job.get("categories", ""), job.get("seniority", ""),
        job.get("work_model", ""), job.get("city", ""),
    ]
    return norm(" ".join(str(v) for v in values))


def select_job(payload: dict, job_index: int, job_url: str) -> dict:
    jobs = payload.get("jobs") or []
    if not jobs:
        raise SystemExit("Nenhuma vaga disponível em output/vagas_ranqueadas.json")
    if job_url:
        target = norm(job_url)
        for job in jobs:
            if norm(job.get("url")) == target:
                return dict(job)
        raise SystemExit(f"URL não encontrada no ranking: {job_url}")
    idx = job_index - 1
    if idx < 0 or idx >= len(jobs):
        raise SystemExit(f"job-index fora do intervalo: 1..{len(jobs)}")
    return dict(jobs[idx])


def analyze(job: dict, profile: dict) -> tuple[list[str], list[str]]:
    text = job_text(job)
    matched = []
    verified_labels = {item["label"] for item in profile.get("verified_skills", [])}
    for item in profile.get("verified_skills", []):
        if any(contains(text, alias) for alias in item.get("aliases", [])):
            matched.append(item["label"])

    gaps = []
    for label, aliases in TRACKED_GAPS.items():
        if any(contains(text, alias) for alias in aliases) and label not in verified_labels:
            gaps.append(label)
    return matched, gaps


def ordered_skill_rows(profile: dict, matched: list[str]) -> list[tuple[str, list[str]]]:
    matched_set = set(matched)
    rows = []
    for category, labels in SKILL_CATEGORIES:
        available = [x for x in labels if any(s.get("label") == x for s in profile.get("verified_skills", []))]
        available.sort(key=lambda x: (x not in matched_set, labels.index(x)))
        if available:
            rows.append((category, available))
    rows.sort(key=lambda row: (-sum(1 for x in row[1] if x in matched_set), SKILL_CATEGORIES.index(next(x for x in SKILL_CATEGORIES if x[0] == row[0]))))
    return rows


def ranked_bullets(exp: dict, matched: list[str]) -> list[dict]:
    matched_set = set(matched)
    bullets = list(exp.get("bullets", []))
    scored = []
    for pos, bullet in enumerate(bullets):
        overlap = sum(1 for tag in bullet.get("tags", []) if tag in matched_set)
        scored.append((overlap, -pos, bullet))
    scored.sort(reverse=True, key=lambda x: (x[0], x[1]))
    # Keep all verified bullets, only reorder them so vacancy-relevant evidence appears first.
    return [item[2] for item in scored]


def summary(profile: dict, matched: list[str]) -> str:
    c = profile["candidate"]
    focus = matched[:8]
    if not focus:
        focus = ["Suporte N2", "Sustentação de Sistemas", "Gestão de Incidentes", "SQL", "APIs REST"]
    joined = ", ".join(focus[:-1]) + (f" e {focus[-1]}" if len(focus) > 1 else focus[0])
    return (
        f"Profissional de Tecnologia com {c['years_it']} de experiência, com forte atuação em Suporte N2, "
        f"sustentação de sistemas críticos e meios de pagamento. Experiência comprovada em {joined}. "
        "Vivência em investigação de incidentes, análise de causa raiz, suporte a integrações e relacionamento técnico B2B, "
        "atuando em interface com Produto, Engenharia e Operações. Perfil orientado a SLA, estabilidade, documentação "
        "e resolução estruturada de problemas."
    )


def build_tex(job: dict, profile: dict, matched: list[str]) -> str:
    c = profile["candidate"]
    rows = ordered_skill_rows(profile, matched)
    sections = []
    for category, skills in rows:
        sections.append(rf"\skillrow{{{latex(category)}}}{{{latex(', '.join(skills))}}}")

    experiences = []
    matched_set = set(matched)
    for exp in profile.get("experiences", []):
        bullets = ranked_bullets(exp, matched)
        relevant_tags = []
        for bullet in bullets:
            for tag in bullet.get("tags", []):
                if tag not in relevant_tags:
                    relevant_tags.append(tag)
        relevant_tags.sort(key=lambda x: (x not in matched_set, relevant_tags.index(x)))
        bullet_tex = "\n".join(rf"  \item {latex(b['text'])}" for b in bullets)
        experiences.append(
            rf"\cventry{{{latex(exp['role'])}}}{{{latex(exp['company'])}}}{{{latex(exp['location'])}}}{{{latex(exp['dates'])}}}\n"
            rf"\begin{{itemize}}\small\n{bullet_tex}\n\end{{itemize}}\n"
            rf"\keytech{{{latex(', '.join(relevant_tags[:14]))}}}\n\n\vspace{{\cventrysep}}"
        )

    courses = "\n".join(rf"  \item \textbf{{{latex(course)}}}" for course in profile.get("courses", []))
    target_title = job.get("title") or "Vaga-alvo"
    target_company = job.get("company") or "Empresa"

    return rf"""% Generated automatically by src/resume_generator.py
% Uses verified facts from resume/base_profile.json only.
\documentclass[a4paper,11pt]{{article}}
\usepackage{{cmap}}
\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage[margin=1.45cm]{{geometry}}
\usepackage{{titlesec}}
\usepackage{{enumitem}}
\usepackage{{xcolor}}
\usepackage{{lmodern}}
\usepackage{{needspace}}
\renewcommand{{\familydefault}}{{\sfdefault}}
\raggedbottom
\clubpenalty=10000
\widowpenalty=10000
\newcommand{{\candidatename}}{{{latex(c['name'])}}}
\definecolor{{accent}}{{HTML}}{{1F4E79}}
\newlength{{\cventrysep}}\setlength{{\cventrysep}}{{6pt}}
\newlength{{\cvblocksep}}\setlength{{\cvblocksep}}{{4pt}}
\usepackage[colorlinks=true,linkcolor=accent,urlcolor=accent]{{hyperref}}
\hypersetup{{pdftitle={{{latex(c['name'])} -- {latex(target_title)}}},pdfauthor={{{latex(c['name'])}}},pdflang={{pt-BR}},pdfdisplaydoctitle=true}}
\ifdefined\pdfgentounicode
  \input{{glyphtounicode}}
  \pdfgentounicode=1
\fi
\titleformat{{\section}}{{\raggedright\large\bfseries\color{{accent}}}}{{}}{{0em}}{{}}[{{\color{{accent}}\titlerule[0.8pt]}}]
\titlespacing{{\section}}{{0pt}}{{9pt}}{{5pt}}
\newcommand{{\cvsection}}[1]{{\section{{#1}}}}
\setlist[itemize]{{leftmargin=0.18in,labelsep=5pt,itemsep=2pt,parsep=0pt,topsep=3pt}}
\setlength{{\parindent}}{{0pt}}
\newcommand{{\cventry}}[4]{{%
  \Needspace{{7\baselineskip}}
  \noindent\normalsize\textbf{{#1}}\hfill\small\textbf{{#4}}\par
  \nopagebreak[4]
  \noindent\normalsize\textit{{\textcolor{{accent}}{{#2}}}}\hfill\small\textit{{#3}}\par
  \nopagebreak[4]
}}
\newcommand{{\keytech}}[1]{{\small\textbf{{Competências-Chave:}} #1\par}}
\newcommand{{\skillrow}}[2]{{\noindent\textbf{{#1:}} #2\par\vspace{{2pt}}}}
\begin{{document}}
\pagestyle{{empty}}
\begin{{center}}
  {{\huge\textbf{{\candidatename}}}} \\ \vspace{{2pt}}
  {{\normalsize\color{{accent}}{latex(c['headline'])}}} \\ \vspace{{4pt}}
  \small
  {latex(c['city'])} \quad|\quad {latex(c['work_preference'])} \quad|\quad
  \href{{tel:{latex(c['phone_uri'])}}}{{{latex(c['phone'])}}} \quad|\quad
  \href{{mailto:{latex(c['email'])}}}{{{latex(c['email'])}}} \\[3pt]
  \href{{{latex(c['linkedin_url'])}}}{{{latex(c['linkedin'])}}}
\end{{center}}
\vspace{{\cvblocksep}}
\cvsection{{Resumo Profissional}}
\small
{latex(summary(profile, matched))}
\vspace{{\cventrysep}}
\cvsection{{Competências Técnicas}}
\small
{chr(10).join(sections)}
\vspace{{\cventrysep}}
\cvsection{{Experiência Profissional}}
{chr(10).join(experiences)}
\cvsection{{Cursos e Desenvolvimento Profissional}}
\begin{{itemize}}\small
{courses}
\end{{itemize}}
\end{{document}}
"""


def write_report(out: Path, job: dict, score: int, reasons: list[str], matched: list[str], gaps: list[str]) -> None:
    report = {
        "job": {
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "url": job.get("url", ""),
            "source": job.get("source", ""),
            "work_model": job.get("work_model", ""),
        },
        "match_score": score,
        "coverage": job.get("coverage", 0),
        "observed_fit": job.get("observed_fit", 0),
        "matched_verified_skills": matched,
        "tracked_gaps_not_added_to_resume": gaps,
        "scoring_reasons": reasons,
        "safety_rule": "O currículo usa somente fatos e competências de resume/base_profile.json; requisitos não verificados nunca são adicionados.",
    }
    (out / "match_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"# Aderência — {job.get('title', 'Vaga')} — {job.get('company', 'Empresa')}", "",
        f"**Aderência:** {score}%", f"**Cobertura da análise:** {job.get('coverage', 0)}%", "",
        "## Competências verificadas encontradas na vaga", "",
    ]
    lines += [f"- {x}" for x in matched] or ["- Nenhuma correspondência explícita identificada."]
    lines += ["", "## Lacunas rastreadas (não adicionadas ao currículo)", ""]
    lines += [f"- {x}" for x in gaps] or ["- Nenhuma lacuna rastreada identificada."]
    lines += ["", "## Regra de integridade", "", "O currículo gerado usa apenas fatos presentes em `resume/base_profile.json`. Requisitos da vaga sem comprovação são reportados como lacunas e não entram no currículo.", "", f"Vaga: {job.get('url', '')}"]
    (out / "match_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=Path, default=DEFAULT_JOBS)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--job-index", type=int, default=1, help="1-based position in vagas_ranqueadas.json")
    parser.add_argument("--job-url", default="", help="Exact URL from vagas_ranqueadas.json; overrides --job-index")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    payload = json.loads(args.jobs.read_text(encoding="utf-8"))
    profile = json.loads(args.profile.read_text(encoding="utf-8"))
    job = select_job(payload, args.job_index, args.job_url)
    score, reasons = score_job(job, profile)
    matched, gaps = analyze(job, profile)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "main.tex").write_text(build_tex(job, profile, matched), encoding="utf-8")
    write_report(args.output_dir, job, score, reasons, matched, gaps)
    print(f"Currículo direcionado gerado: {job.get('title')} — {job.get('company')} ({score}%)")
    print(f"Competências verificadas em aderência: {', '.join(matched) if matched else 'nenhuma explícita'}")
    if gaps:
        print(f"Lacunas rastreadas (não adicionadas): {', '.join(gaps)}")


if __name__ == "__main__":
    main()
