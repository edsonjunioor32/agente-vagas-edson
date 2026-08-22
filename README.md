# Agente de Vagas — Edson Paiva

Pipeline automatizado de busca e priorização de vagas e alimentado pelas fontes consolidadas do repositório `edsonjunioor32/todas-as-vagas`.

## Objetivo

Priorizar oportunidades aderentes ao perfil de Edson Paiva Jr., especialmente:

- Suporte Técnico N2 / Technical Support
- Application Support / Production Support
- Sustentação de Sistemas
- Operações de Pagamentos e Cartões
- Gestão de Incidentes
- Suporte técnico B2B / integrações / APIs
- Customer Success técnico quando houver forte componente de produto, integrações ou troubleshooting

Preferência por vagas 100% remotas no Brasil.

## Como funciona

1. Baixa o snapshot público de vagas gerado pelo `todas-as-vagas`.
2. Normaliza os campos principais.
3. Remove duplicidades por URL e por combinação título/empresa.
4. Filtra vagas incompatíveis com o mercado Brasil.
5. Calcula aderência ao perfil usando palavras-chave, contexto, senioridade e modelo de trabalho.
6. Gera `output/vagas_ranqueadas.json`, `output/vagas_ranqueadas.csv` e `output/resumo.md`.

## Execução local

Requer Python 3.11+.

```bash
python src/pipeline.py
```

Variáveis opcionais:

- `SOURCE_URL`: URL alternativa para o snapshot JSON.
- `MAX_JOBS`: quantidade máxima de vagas no resultado (padrão: 100).
- `MIN_SCORE`: score mínimo de aderência (padrão: 35).
- `MAX_AGE_DAYS`: idade máxima da vaga em dias (padrão: 60).

## Automação

O workflow `.github/workflows/vagas.yml` executa diariamente e também pode ser iniciado manualmente pelo botão **Run workflow** no GitHub Actions.

## Origem das fontes

As fontes são mantidas no pipeline `edsonjunioor32/todas-as-vagas`, que agrega múltiplos ATS, páginas de carreira e job boards. Este repositório atua como camada de seleção e ranking personalizada, evitando duplicar toda a lógica de scraping.
