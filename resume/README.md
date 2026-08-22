# Currículo ATS-Friendly

Esta pasta contém uma prova de conceito de currículo ATS-Friendly em LaTeX para Edson Paiva Jr., integrada ao repositório `agente-vagas-edson`.

## Objetivo

Transformar o currículo em um artefato reproduzível e validado automaticamente, mantendo leitura previsível por Applicant Tracking Systems (ATS).

O template evita tabelas, múltiplas colunas e elementos gráficos que podem prejudicar a ordem de leitura do PDF. A versão PT-BR utiliza texto selecionável, fontes incorporadas e mapeamento Unicode.

## Estrutura

- `pt-br/main.tex`: currículo em português brasileiro.
- `LICENSE_TEMPLATE`: licença MIT do template-base original.
- `.github/workflows/ats-resume.yml`: workflow que compila e valida o currículo.

## Pipeline

A cada alteração em `resume/**`, o GitHub Actions:

1. instala LaTeX e Poppler;
2. compila `main.tex` em PDF;
3. extrai o texto com `pdftotext`;
4. verifica conteúdo essencial e ordem legível;
5. inspeciona metadados/criptografia com `pdfinfo`;
6. verifica incorporação/Unicode das fontes com `pdffonts`;
7. publica o PDF e os relatórios como artifact do workflow.

Também é possível executar manualmente pelo botão **Run workflow**.

## Próxima evolução

O passo seguinte é gerar versões do currículo direcionadas a vagas específicas. O agente poderá usar `perfil.json` e a descrição da vaga para selecionar palavras-chave e experiências reais, gerar um `main.tex` customizado e então executar esta mesma validação ATS.

## Origem do template

Baseado em `danielteles/ats-friendly-latex-cv`, disponibilizado sob licença MIT. O aviso de copyright e a licença original estão preservados em `LICENSE_TEMPLATE`.
