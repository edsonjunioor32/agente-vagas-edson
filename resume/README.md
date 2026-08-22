# Currículo ATS-Friendly direcionado por vaga

Este módulo integra um currículo ATS-Friendly em LaTeX ao repositório `agente-vagas-edson` e permite gerar automaticamente uma versão direcionada a uma vaga do ranking.

## Objetivo

O fluxo transforma uma vaga ranqueada em um currículo reproduzível, direcionado por palavras-chave e validado automaticamente para leitura por Applicant Tracking Systems (ATS), sem inventar competências ou experiências.

O documento usa coluna única, texto selecionável, fontes incorporadas e mapeamento Unicode. Não utiliza tabelas, múltiplas colunas, foto ou elementos gráficos que possam prejudicar a ordem de leitura do ATS.

## Fonte de verdade

`resume/base_profile.json` contém os fatos e competências autorizados para geração do currículo. O gerador pode reorganizar e destacar informações dessa base, mas não pode adicionar requisitos da vaga que não estejam verificados.

Quando uma vaga exige uma competência rastreada que não consta na base — por exemplo Linux, Java/Spring, PL/SQL, Docker ou cloud — ela aparece no relatório como lacuna e não é inserida no currículo.

## Estrutura

- `resume/base_profile.json`: fonte de verdade do currículo.
- `resume/pt-br/main.tex`: versão-base ATS-Friendly em português brasileiro.
- `src/resume_generator.py`: analisa a vaga e gera o LaTeX direcionado.
- `src/scoring_v2.py`: calcula aderência com evidências observadas.
- `tests/test_resume_generator.py`: testes de integridade do gerador e do scoring.
- `.github/workflows/ats-resume.yml`: geração, compilação e validação no GitHub Actions.
- `LICENSE_TEMPLATE`: licença MIT do template-base original.

## Como funciona

O GitHub Actions executa as seguintes etapas:

1. seleciona uma vaga de `output/vagas_ranqueadas.json`;
2. executa os testes automatizados;
3. compara a descrição da vaga com as competências verificadas em `resume/base_profile.json`;
4. calcula o percentual de aderência;
5. identifica lacunas sem adicioná-las ao currículo;
6. prioriza no currículo as competências e evidências profissionais mais relevantes para a vaga;
7. gera `output/curriculo_ats/main.tex`;
8. compila o PDF em LaTeX;
9. valida que não existem estouros horizontais de layout;
10. valida extração de texto com `pdftotext`;
11. verifica metadados, criptografia e JavaScript com `pdfinfo`;
12. verifica incorporação e Unicode das fontes com `pdffonts`;
13. publica PDF, LaTeX e relatórios como artifact do workflow.

## Executar para uma vaga

No GitHub, abra **Actions > ATS Resume - Generate, Build and Validate > Run workflow**.

Há duas formas de selecionar a vaga:

- `job_index`: posição da vaga no ranking. O valor `1` utiliza a melhor vaga atualmente ranqueada.
- `job_url`: URL exata de uma vaga presente no ranking. Quando preenchida, ela tem prioridade sobre `job_index`.

## Saídas

O artifact `curriculo-edson-paiva-ats-targeted` contém:

- `Curriculo_Edson_Paiva_ATS.pdf`: currículo final para candidatura;
- `main.tex`: LaTeX efetivamente compilado;
- `main.txt`: texto extraído do PDF, usado para validação ATS;
- `match_report.md`: relatório legível de aderência e lacunas;
- `match_report.json`: relatório estruturado para futuras automações;
- `pdfinfo.txt`: validação de metadados e segurança;
- `pdffonts.txt`: validação de fontes e Unicode.

## Regra de integridade

A descrição da vaga serve para **selecionar e priorizar** fatos reais, nunca para criar experiência. Se uma tecnologia for exigida pela vaga e não constar na fonte de verdade, ela deverá permanecer no relatório de lacunas.

## Origem do template

Baseado em `danielteles/ats-friendly-latex-cv`, disponibilizado sob licença MIT. O aviso de copyright e a licença original estão preservados em `LICENSE_TEMPLATE`.
