import re
import unicodedata


def _text(value):
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(_text(x) for x in value)
    if isinstance(value, dict):
        return " ".join(f"{k} {_text(v)}" for k, v in value.items())
    return str(value)


def norm(value):
    text = unicodedata.normalize("NFKD", _text(value).lower().strip())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text)


def _contains_alias(haystack, alias):
    token = norm(alias)
    if not token:
        return False
    if re.fullmatch(r"[a-z0-9.+#/-]{1,3}", token):
        return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", haystack) is not None
    return token in haystack


def _contains_any(haystack, aliases):
    return any(_contains_alias(haystack, alias) for alias in aliases)


def _job_text(job):
    return norm(" ".join([
        _text(job.get("title")), _text(job.get("company")), _text(job.get("description")),
        _text(job.get("work_model")), _text(job.get("city")), _text(job.get("seniority")),
        _text(job.get("skills")), _text(job.get("categories")), _text(job.get("contract_types")),
    ]))


def is_remote(job):
    model = norm(f"{_text(job.get('work_model'))} {_text(job.get('city'))}")
    return _contains_any(model, ("remote", "remoto", "home office", "home-office", "anywhere", "totalmente remoto"))


ROLE_GROUPS = [
    (30, ("technical support", "analista de suporte", "support analyst", "support engineer", "analista de sustentacao", "application support", "production support", "analista de incidentes", "incident analyst")),
    (27, ("technical customer support", "suporte tecnico", "suporte n2", "suporte l2")),
    (22, ("customer support", "service desk", "help desk")),
    (18, ("customer success", "sucesso do cliente")),
]

SKILL_GROUPS = [
    (8, "N2/L2", ("n2", "l2", "nivel 2", "nivel ii")),
    (8, "APIs e integrações", ("api", "apis", "postman", "webhook", "webhooks", "integracao", "integration")),
    (7, "SQL e banco de dados", ("sql", "oracle", "pl/sql", "database", "banco de dados")),
    (6, "Observabilidade e logs", ("splunk", "datadog", "grafana", "observabilidade", "logs", "monitoramento")),
    (6, "Incidentes/RCA/ITIL", ("incident", "incidente", "rca", "itil", "problem management", "troubleshooting")),
    (8, "Pagamentos e cartões", ("pagamento", "payment", "cartao", "cards", "autorizacao", "conciliacao", "fatura", "embossing")),
    (4, "Sustentação", ("sustentacao", "sustentar aplicacao", "support application")),
    (3, "B2B", ("b2b", "cliente corporativo", "enterprise customer")),
]


def _role_points(title):
    for points, aliases in ROLE_GROUPS:
        if _contains_any(title, aliases):
            return points
    return 0


def _skill_evidence(job, body):
    points = 0
    matched = []
    matched_weight = 0
    for weight, label, aliases in SKILL_GROUPS:
        if _contains_any(body, aliases):
            points += weight
            matched_weight += weight
            matched.append(label)

    # Se a fonte trouxe lista de skills ou descrição razoavelmente completa, o bloco técnico
    # pode ser avaliado por inteiro. Caso contrário, só contamos como "coberto" aquilo que
    # realmente apareceu no snapshot (por exemplo N2 no próprio título).
    has_explicit_skills = bool(norm(job.get("skills")))
    description = norm(job.get("description"))
    has_full_description = len(description) >= 200
    covered = 40 if (has_explicit_skills or has_full_description) else min(40, matched_weight)
    return min(40, points), covered, matched


def _domain_evidence(body):
    if _contains_any(body, ("fintech", "meios de pagamento", "pagamento", "payment", "cartao", "banking", "banco", "financeiro", "financial")):
        return 15, 15, "financeiro/pagamentos"
    if _contains_any(body, ("saas", "tecnologia", "technology", "software")):
        return 11, 15, "tecnologia/SaaS"
    return 0, 0, ""


def _seniority_evidence(job, title):
    seniority = norm(job.get("seniority"))
    combined = norm(f"{title} {seniority}")
    if not combined or combined in {"nao informado", "não informado", "unknown"}:
        return 0, 0, "senioridade não informada"
    if _contains_any(combined, ("estagio", "trainee", "aprendiz")):
        return 0, 10, "nível de entrada fora do alvo"
    if _contains_any(combined, ("pleno", "mid-level", "mid level")):
        return 10, 10, "senioridade pleno"
    if _contains_any(combined, ("senior", "especialista", "sr")):
        return 9, 10, "senioridade sênior/especialista"
    if _contains_any(combined, ("junior", "jr")):
        return 6, 10, "senioridade júnior"
    if _contains_any(combined, ("lider", "lead", "manager", "gerente", "coordenador")):
        return 4, 10, "liderança/gestão"
    # Campo de senioridade preenchido, mas sem classe reconhecida: há evidência parcial,
    # porém não assumimos compatibilidade total.
    if seniority and seniority not in {"nao informado", "não informado", "unknown"}:
        return 7, 10, "senioridade informada, classificação não mapeada"
    return 0, 0, "senioridade não informada"


def score_job(job, profile=None):
    title = norm(job.get("title"))
    body = _job_text(job)
    reasons = []

    # Função e remoto são sempre observáveis no conjunto atual.
    role = _role_points(title)
    role_covered = 30
    remote = 5 if is_remote(job) else 0
    remote_covered = 5

    skills, skills_covered, matched_skills = _skill_evidence(job, body)
    domain, domain_covered, domain_label = _domain_evidence(body)
    seniority, seniority_covered, seniority_label = _seniority_evidence(job, title)

    points = role + skills + domain + seniority + remote
    covered = role_covered + skills_covered + domain_covered + seniority_covered + remote_covered
    raw_fit = round((points / covered) * 100) if covered else 0
    score = raw_fit

    reasons.append(f"função: {role}/30") if role else reasons.append("função-alvo não identificada: 0/30")
    if matched_skills:
        reasons.append(f"competências observadas: {skills}/{skills_covered or 40} ({', '.join(matched_skills[:5])})")
    elif skills_covered:
        reasons.append(f"competências técnicas: 0/{skills_covered}")
    else:
        reasons.append("competências técnicas sem dados suficientes — não penalizadas")
    if domain_covered:
        reasons.append(f"segmento: {domain}/{domain_covered} ({domain_label})")
    else:
        reasons.append("segmento sem evidência suficiente — não penalizado")
    if seniority_covered:
        reasons.append(f"senioridade: {seniority}/{seniority_covered} ({seniority_label})")
    else:
        reasons.append("senioridade não informada — não penalizada")
    if remote:
        reasons.append("remoto: 5/5")

    # Compartilhar tecnologias/segmento não basta para ser vaga-alvo.
    if role == 0:
        score = min(score, 45)
        reasons.append("teto aplicado: cargo fora da função-alvo")

    # Customer Success só ultrapassa a faixa de triagem quando há evidência técnica concreta.
    if _contains_any(title, ("customer success", "sucesso do cliente")):
        technical_cs = bool(matched_skills) or _contains_any(body, ("technical", "tecnico"))
        if not technical_cs:
            score = min(score, 35)
            reasons.append("teto aplicado: CS sem evidência técnica")

    if _contains_any(title, ("n1", "nivel 1")):
        score -= 10
        reasons.append("-10: posição N1")

    if _contains_any(title, ("frontend", "front-end", "backend developer", "software developer", "mobile developer", "product manager", "product owner", "designer", "marketing", "sales", "vendas")):
        score = min(score - 20, 30)
        reasons.append("penalidade: função principal fora de suporte/sustentação")

    score = max(0, min(100, round(score)))
    coverage = max(0, min(100, round(covered)))

    # Mantém compatibilidade com pipeline.main(), que espera apenas (score, reasons),
    # e grava as novas métricas no próprio objeto da vaga para irem ao JSON final.
    job["coverage"] = coverage
    job["fit_points"] = points
    job["covered_points"] = covered
    job["score_method"] = "observed_evidence_v3"
    reasons.append(f"cobertura da análise: {coverage}%")
    return score, reasons
