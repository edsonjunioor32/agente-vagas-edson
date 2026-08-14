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


def _contains_any(haystack, aliases):
    return any(norm(alias) in haystack for alias in aliases)


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
    (8, "N2/L2", (" n2", "n2 ", " n2 ", " l2", "l2 ", "nivel 2", "nivel ii")),
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


def _skill_points(body):
    total = 0
    matched = []
    for points, label, aliases in SKILL_GROUPS:
        if _contains_any(body, aliases):
            total += points
            matched.append(label)
    return min(40, total), matched


def _domain_points(body):
    if _contains_any(body, ("fintech", "meios de pagamento", "pagamento", "payment", "cartao", "banking", "banco", "financeiro", "financial")):
        return 15, "financeiro/pagamentos"
    if _contains_any(body, ("saas", "tecnologia", "technology", "software")):
        return 8, "tecnologia/SaaS"
    return 0, ""


def _seniority_points(job, title, body):
    seniority = norm(job.get("seniority"))
    combined = f"{title} {seniority}"
    if _contains_any(combined, ("estagio", "trainee", "aprendiz")):
        return 0, "nível de entrada fora do alvo"
    if _contains_any(combined, ("pleno", "mid-level", "mid level", " pleno ")):
        return 10, "senioridade pleno"
    if _contains_any(combined, ("senior", "especialista", " sr ", "senior")):
        return 9, "senioridade sênior/especialista"
    if _contains_any(combined, ("junior", "jr", "júnior")):
        return 6, "senioridade júnior"
    if _contains_any(combined, ("lider", "lead", "manager", "gerente", "coordenador")):
        return 4, "liderança/gestão"
    if _contains_any(body, ("analista", "specialist", "engineer", "support")):
        return 7, "senioridade compatível não especificada"
    return 5, "senioridade não informada"


def score_job(job, profile=None):
    title = norm(job.get("title"))
    body = _job_text(job)
    reasons = []

    role = _role_points(title)
    skills, matched_skills = _skill_points(body)
    domain, domain_label = _domain_points(body)
    seniority, seniority_label = _seniority_points(job, title, body)
    remote = 5 if is_remote(job) else 0

    score = role + skills + domain + seniority + remote

    if role:
        reasons.append(f"função: {role}/30")
    else:
        reasons.append("função-alvo não identificada")

    if matched_skills:
        reasons.append(f"competências: {skills}/40 ({', '.join(matched_skills[:5])})")
    else:
        reasons.append("competências técnicas: 0/40")

    if domain:
        reasons.append(f"segmento: {domain}/15 ({domain_label})")
    if seniority_label:
        reasons.append(f"senioridade: {seniority}/10 ({seniority_label})")
    if remote:
        reasons.append("remoto: 5/5")

    # Evita falsos positivos: compartilhar tecnologias/segmento não basta para ser vaga-alvo.
    if role == 0:
        score = min(score, 45)
        reasons.append("teto aplicado: cargo fora da função-alvo")

    # Customer Success só é aderente quando há evidência técnica concreta.
    if _contains_any(title, ("customer success", "sucesso do cliente")):
        technical_cs = _contains_any(body, ("api", "integration", "integracao", "sql", "webhook", "technical", "tecnico", "pagamento", "payment", "b2b"))
        if not technical_cs:
            score = min(score, 35)
            reasons.append("teto aplicado: CS sem evidência técnica")

    # N1 é válido como adjacente, mas abaixo do alvo N2.
    if _contains_any(title, (" n1", "n1 ", "nivel 1", "nível 1")):
        score -= 10
        reasons.append("-10: posição N1")

    # Cargos claramente de desenvolvimento/produto/áreas comerciais ficam fora do alvo.
    if _contains_any(title, ("frontend", "front-end", "backend developer", "software developer", "mobile developer", "product manager", "product owner", "designer", "marketing", "sales", "vendas")):
        score = min(score - 20, 30)
        reasons.append("penalidade: função principal fora de suporte/sustentação")

    return max(0, min(100, round(score))), reasons
