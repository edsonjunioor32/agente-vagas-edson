(() => {
  'use strict';

  const DATA_URL = 'https://raw.githubusercontent.com/edsonjunioor32/agente-vagas-edson/main/output/vagas_ranqueadas.json';
  const dateTimeFormatter = new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short',
    timeStyle: 'short',
    timeZone: 'America/Fortaleza'
  });
  const dateFormatter = new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'medium',
    timeZone: 'America/Fortaleza'
  });

  const els = {
    totalJobs: document.querySelector('#totalJobs'),
    topScore: document.querySelector('#topScore'),
    updatedAt: document.querySelector('#updatedAt'),
    search: document.querySelector('#search'),
    sourceFilter: document.querySelector('#sourceFilter'),
    scoreFilter: document.querySelector('#scoreFilter'),
    sortFilter: document.querySelector('#sortFilter'),
    clearFilters: document.querySelector('#clearFilters'),
    resultCount: document.querySelector('#resultCount'),
    status: document.querySelector('#status'),
    jobs: document.querySelector('#jobs'),
    emptyState: document.querySelector('#emptyState'),
    template: document.querySelector('#jobTemplate')
  };

  const state = { all: [], filtered: [], generatedAt: null };

  function normalize(value) {
    return String(value ?? '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .toLowerCase()
      .trim();
  }

  function escapeText(value) {
    return String(value ?? '').trim();
  }

  function formatSource(value) {
    const labels = {
      gupy: 'Gupy', inhire: 'InHire', nerdin: 'Nerdin', empregare: 'Empregare',
      geekhunter: 'GeekHunter', totvs: 'TOTVS', himalayas: 'Himalayas', jobicy: 'Jobicy',
      remoteok: 'Remote OK', remotive: 'Remotive', stone: 'Stone', ifood: 'iFood',
      greenhouse: 'Greenhouse', lever: 'Lever', ashby: 'Ashby', solids: 'Sólides', solides: 'Sólides'
    };
    const key = normalize(value);
    return labels[key] || escapeText(value) || 'Fonte não informada';
  }

  function isValidDate(value) {
    return value && !Number.isNaN(Date.parse(value));
  }

  function relativeDate(value) {
    if (!isValidDate(value)) return 'Data não informada';
    const now = new Date();
    const date = new Date(value);
    const diffDays = Math.floor((now - date) / 86400000);
    if (diffDays <= 0) return `Publicada hoje · ${dateTimeFormatter.format(date)}`;
    if (diffDays === 1) return 'Publicada ontem';
    if (diffDays < 7) return `Publicada há ${diffDays} dias`;
    return `Publicada em ${dateFormatter.format(date)}`;
  }

  function renderStats() {
    els.totalJobs.textContent = state.all.length.toLocaleString('pt-BR');
    const top = state.all.reduce((max, job) => Math.max(max, Number(job.score) || 0), 0);
    els.topScore.textContent = `${top}%`;
    els.updatedAt.textContent = isValidDate(state.generatedAt)
      ? dateTimeFormatter.format(new Date(state.generatedAt))
      : 'não informada';
  }

  function populateSources() {
    const sources = [...new Set(state.all.map(job => escapeText(job.source)).filter(Boolean))]
      .sort((a, b) => formatSource(a).localeCompare(formatSource(b), 'pt-BR'));
    for (const source of sources) {
      const option = document.createElement('option');
      option.value = source;
      option.textContent = formatSource(source);
      els.sourceFilter.append(option);
    }
  }

  function makeChip(text) {
    const chip = document.createElement('span');
    chip.className = 'chip';
    chip.textContent = text;
    return chip;
  }

  function renderJobs() {
    els.jobs.replaceChildren();
    els.resultCount.textContent = state.filtered.length.toLocaleString('pt-BR');
    els.emptyState.hidden = state.filtered.length !== 0;

    const fragment = document.createDocumentFragment();
    for (const job of state.filtered) {
      const node = els.template.content.cloneNode(true);
      const score = Number(job.score) || 0;
      const coverage = Math.max(0, Math.min(100, Number(job.coverage) || 0));
      node.querySelector('.score').textContent = `${score}%`;
      node.querySelector('.score').title = `Aderência estimada com ${coverage}% de cobertura da análise`;
      node.querySelector('.job-title').textContent = escapeText(job.title) || 'Vaga sem título';
      node.querySelector('.company').textContent = escapeText(job.company) || 'Empresa não informada';
      node.querySelector('.source-pill').textContent = formatSource(job.source);

      const chips = node.querySelector('.chips');
      const chipValues = [
        `Cobertura ${coverage}%`,
        job.work_model ? String(job.work_model).toLowerCase() === 'remote' ? 'Remoto' : job.work_model : '',
        job.city,
        ...(Array.isArray(job.contract_types) ? job.contract_types : [])
      ].map(escapeText).filter(Boolean);
      [...new Set(chipValues)].slice(0, 6).forEach(value => chips.append(makeChip(value)));
      if (!chips.childElementCount) chips.remove();

      const reasons = Array.isArray(job.reasons) ? job.reasons : [];
      node.querySelector('.reasons').textContent = reasons.length
        ? `Aderência estimada: ${score}% · Cobertura: ${coverage}% · ${reasons.join(' · ')}`
        : `Aderência estimada: ${score}% · Cobertura da análise: ${coverage}%.`;

      node.querySelector('.published').textContent = relativeDate(job.published_at_br);
      const link = node.querySelector('.apply');
      link.href = job.url || '#';
      if (!job.url) {
        link.removeAttribute('target');
        link.setAttribute('aria-disabled', 'true');
      }
      fragment.append(node);
    }
    els.jobs.append(fragment);
  }

  function applyFilters() {
    const query = normalize(els.search.value);
    const source = els.sourceFilter.value;
    const minScore = Number(els.scoreFilter.value || 0);
    const sort = els.sortFilter.value;
    const terms = query.split(/\s+/).filter(Boolean);

    state.filtered = state.all.filter(job => {
      if ((Number(job.score) || 0) < minScore) return false;
      if (source && job.source !== source) return false;
      if (terms.length) {
        const haystack = normalize([
          job.title, job.company, job.source, job.work_model, job.city,
          Array.isArray(job.skills) ? job.skills.join(' ') : job.skills,
          Array.isArray(job.categories) ? job.categories.join(' ') : job.categories,
          Array.isArray(job.reasons) ? job.reasons.join(' ') : job.reasons
        ].join(' '));
        if (!terms.every(term => haystack.includes(term))) return false;
      }
      return true;
    });

    state.filtered.sort((a, b) => {
      if (sort === 'recent') return (Date.parse(b.published_at_br) || 0) - (Date.parse(a.published_at_br) || 0) || (b.score - a.score);
      if (sort === 'company') return String(a.company || '').localeCompare(String(b.company || ''), 'pt-BR', { sensitivity: 'base' });
      return (Number(b.score) || 0) - (Number(a.score) || 0)
        || (Number(b.coverage) || 0) - (Number(a.coverage) || 0)
        || (Date.parse(b.published_at_br) || 0) - (Date.parse(a.published_at_br) || 0);
    });

    renderJobs();
  }

  async function load() {
    try {
      const response = await fetch(`${DATA_URL}?v=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (!data || !Array.isArray(data.jobs)) throw new Error('Formato de dados inválido');
      state.all = data.jobs;
      state.generatedAt = data.generated_at || null;
      renderStats();
      populateSources();
      applyFilters();
      els.status.textContent = 'Dados carregados com sucesso.';
    } catch (error) {
      console.error(error);
      els.status.textContent = 'Não foi possível carregar as vagas agora.';
      els.emptyState.hidden = false;
      els.emptyState.querySelector('h2').textContent = 'Falha ao carregar os dados';
      els.emptyState.querySelector('p').textContent = 'Atualize a página ou tente novamente em alguns instantes.';
    }
  }

  let debounce;
  els.search.addEventListener('input', () => {
    clearTimeout(debounce);
    debounce = setTimeout(applyFilters, 120);
  });
  [els.sourceFilter, els.scoreFilter, els.sortFilter].forEach(el => el.addEventListener('change', applyFilters));
  els.clearFilters.addEventListener('click', () => {
    els.search.value = '';
    els.sourceFilter.value = '';
    els.scoreFilter.value = '35';
    els.sortFilter.value = 'score';
    applyFilters();
    els.search.focus();
  });

  load();
})();
