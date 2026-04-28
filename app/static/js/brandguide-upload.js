/**
 * Brandguide upload (Fase 2 + Etapa 2 do redesign).
 *
 * Fluxo:
 *   1. Solicita presigned URL ao backend
 *   2. Faz PUT direto no S3 usando signed_headers do backend
 *   3. Confirma upload criando BrandguideUpload no banco
 *   4. Polling do status ate completed/error
 *   5. Quando completed: page reload (servidor renderiza com campos preenchidos)
 *
 * Comportamento UI:
 *   - Durante processamento, o resto da pagina /knowledge/ fica em modo
 *     readonly (overlay + inputs/botoes desabilitados).
 *   - Re-upload exige confirmacao em modal (window.confirmModal).
 */
(function () {
  'use strict';

  const UPLOAD_URL_ENDPOINT = '/knowledge/brandguide/upload-url/';
  const CREATE_ENDPOINT = '/knowledge/brandguide/create/';
  const STATUS_ENDPOINT = '/knowledge/brandguide/status/';
  const DELETE_ENDPOINT_TEMPLATE = '/knowledge/brandguide/{id}/delete/';

  const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB
  const POLL_INTERVAL_MS = 3000;
  const POLL_MAX_ATTEMPTS = 120; // ~6 min

  const PROCESSING_STATUSES = [
    'uploaded', 'converting', 'extracting_assets', 'analyzing',
  ];

  // ---- Helpers -----------------------------------------------------------

  function getCsrfToken() {
    const name = 'csrftoken=';
    const cookies = document.cookie.split(';');
    for (const raw of cookies) {
      const c = raw.trim();
      if (c.startsWith(name)) return decodeURIComponent(c.slice(name.length));
    }
    return '';
  }

  function $(selector) {
    return document.querySelector(selector);
  }

  function show(el) { if (el) el.style.display = ''; }
  function hide(el) { if (el) el.style.display = 'none'; }

  function setError(message) {
    const el = $('#brandguide-error');
    if (!el) return;
    if (message) {
      el.textContent = message;
      show(el);
    } else {
      el.textContent = '';
      hide(el);
    }
  }

  /**
   * Bloqueia/libera a interacao com os blocos do formulario enquanto o
   * brandguide processa. NAO afeta o card de brandguide nem outras URLs.
   */
  function setReadonlyState(isReadonly) {
    const form = document.getElementById('knowledge-form');
    const overlay = $('#brandguide-processing-overlay');
    if (!form) return;

    form.classList.toggle('is-brandguide-processing', !!isReadonly);
    if (overlay) overlay.style.display = isReadonly ? '' : 'none';

    // Desabilita inputs/botoes dentro dos blocos do formulario.
    // Mantem ativo o que estiver dentro de #brandguide-section (botao X, etc).
    const blocks = form.querySelectorAll('section.form-block');
    blocks.forEach((block) => {
      block.classList.toggle('is-disabled', !!isReadonly);
      block.querySelectorAll('input, select, textarea, button').forEach((el) => {
        if (isReadonly) {
          if (!el.dataset.bgPrevDisabled) {
            el.dataset.bgPrevDisabled = el.disabled ? '1' : '0';
          }
          el.disabled = true;
        } else {
          // Restaurar somente o que foi desabilitado por nos
          if (el.dataset.bgPrevDisabled === '0') {
            el.disabled = false;
          }
          delete el.dataset.bgPrevDisabled;
        }
      });
    });
  }

  function updateStatusUI(data) {
    const card = $('#brandguide-current');
    const uploadArea = $('#brandguide-upload-area');

    if (!data) {
      hide(card);
      show(uploadArea);
      setReadonlyState(false);
      return;
    }

    show(card);
    hide(uploadArea);

    const filenameEl = $('#brandguide-filename');
    const statusEl = $('#brandguide-status-label');
    const progressEl = $('#brandguide-progress');
    const fillEl = $('#brandguide-progress-fill');
    const pagesEl = $('#brandguide-pages-count');

    if (filenameEl) {
      filenameEl.textContent = data.originalFilename || '—';
      if (data.pdfDownloadUrl) {
        filenameEl.setAttribute('href', data.pdfDownloadUrl);
        filenameEl.removeAttribute('aria-disabled');
      } else {
        filenameEl.setAttribute('href', '#');
        filenameEl.setAttribute('aria-disabled', 'true');
      }
    }

    const statusLabels = {
      uploaded: 'Enviando documento',
      converting: 'Processando documento',
      extracting_assets: 'Extraindo grafismos',
      analyzing: 'Analisando com IA',
      completed: 'Processamento concluido',
      error: 'Erro no processamento',
    };
    if (statusEl) statusEl.textContent = statusLabels[data.status] || data.status;

    const isProcessing = PROCESSING_STATUSES.includes(data.status);

    card.classList.toggle('is-processing', isProcessing);
    card.classList.toggle('is-completed', data.status === 'completed');
    card.classList.toggle('is-error', data.status === 'error');

    // Bloqueia o restante do formulario somente durante o processamento.
    setReadonlyState(isProcessing);

    // Progresso real: pagesProcessed / totalPages
    const total = data.totalPages || 0;
    const processed = data.pagesProcessed || 0;
    let percent = 0;
    if (data.status === 'completed') {
      percent = 100;
    } else if (total > 0) {
      percent = Math.min(99, Math.round((processed / total) * 100));
    } else if (isProcessing) {
      percent = 5;
    }

    if (fillEl) fillEl.style.width = percent + '%';

    if (isProcessing) show(progressEl); else hide(progressEl);

    if (total > 0) {
      show(pagesEl);
      if (data.status === 'completed') {
        pagesEl.textContent = `${total} paginas`;
      } else {
        pagesEl.textContent = `${processed}/${total} paginas`;
      }
    } else {
      hide(pagesEl);
    }

    if (data.status === 'error' && data.errorMessage) {
      setError(data.errorMessage);
    } else {
      setError('');
    }
  }

  // ---- Upload flow -------------------------------------------------------

  async function requestUploadUrl(file) {
    const body = new URLSearchParams({
      fileName: file.name,
      fileType: file.type,
      fileSize: String(file.size),
    });

    const res = await fetch(UPLOAD_URL_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': getCsrfToken(),
      },
      body,
    });

    const json = await res.json().catch(() => ({}));
    if (!res.ok || !json.success) {
      throw new Error(json.error || 'Falha ao obter URL de upload');
    }
    return json.data;
  }

  async function uploadToS3(file, uploadData) {
    const headers = {
      'Content-Type': file.type,
      ...(uploadData.signed_headers || {}),
    };

    const res = await fetch(uploadData.upload_url, {
      method: 'PUT',
      body: file,
      headers,
    });
    if (!res.ok) {
      throw new Error('Falha ao enviar arquivo para o S3 (status ' + res.status + ')');
    }
  }

  async function createBrandguideRecord(file, uploadData) {
    const body = new URLSearchParams({
      s3Key: uploadData.s3_key,
      originalFilename: file.name,
      fileSize: String(file.size),
    });

    const res = await fetch(CREATE_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': getCsrfToken(),
      },
      body,
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok || !json.success) {
      throw new Error(json.error || 'Falha ao registrar brandguide');
    }
    return json.data;
  }

  async function fetchStatus(brandguideId) {
    const url = brandguideId
      ? `/knowledge/brandguide/${brandguideId}/status/`
      : STATUS_ENDPOINT;
    const res = await fetch(url, {
      method: 'GET',
      headers: { 'X-CSRFToken': getCsrfToken() },
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok || !json.success) {
      throw new Error(json.error || 'Falha ao consultar status');
    }
    return json.data;
  }

  /**
   * Polling ate completed/error. Quando completed, recarrega a pagina para
   * que os campos auto-preenchidos pela IA apareçam no formulario.
   */
  async function pollUntilDone(brandguideId) {
    let attempts = 0;
    while (attempts < POLL_MAX_ATTEMPTS) {
      attempts += 1;
      try {
        const data = await fetchStatus(brandguideId);
        updateStatusUI(data);
        if (!data) return null;
        if (data.status === 'completed') {
          // Pequeno delay para o usuario ver o estado "concluido" antes do reload
          setTimeout(() => window.location.reload(), 600);
          return data;
        }
        if (data.status === 'error') {
          return data;
        }
      } catch (err) {
        console.warn('[brandguide] status check falhou:', err.message);
      }
      await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
    }
    return null;
  }

  async function deleteBrandguideViaUI(brandguideId) {
    const message = (
      'Voce ja tem um brandguide processado nesta base. '
      + 'Subir um novo PDF vai apagar os dados atuais que vieram do brandguide '
      + '(cores, tipografia e textos preenchidos pela IA). Edicoes manuais que '
      + 'voce fez em outros campos sao preservadas. Deseja continuar?'
    );
    let confirmed = true;
    if (window.confirmModal && typeof window.confirmModal.show === 'function') {
      confirmed = await window.confirmModal.show(message, 'Substituir brandguide');
    } else {
      confirmed = window.confirm(message);
    }
    if (!confirmed) return false;

    const url = DELETE_ENDPOINT_TEMPLATE.replace('{id}', brandguideId);
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCsrfToken() },
    });
    const json = await res.json().catch(() => ({}));
    if (!res.ok || !json.success) {
      setError(json.error || 'Falha ao remover brandguide');
      return false;
    }
    return true;
  }

  // ---- Main handler ------------------------------------------------------

  async function handleFileSelected(file) {
    setError('');

    if (!file) return;
    if (file.type !== 'application/pdf') {
      setError('Apenas arquivos PDF sao aceitos.');
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      setError('Arquivo excede o limite de 50 MB.');
      return;
    }

    try {
      updateStatusUI({
        originalFilename: file.name,
        status: 'uploaded',
        totalPages: 0,
        pagesProcessed: 0,
      });

      const uploadData = await requestUploadUrl(file);
      await uploadToS3(file, uploadData);
      const record = await createBrandguideRecord(file, uploadData);

      await pollUntilDone(record.brandguideId);
    } catch (err) {
      console.error('[brandguide] upload falhou:', err);
      setError(err.message || 'Erro no upload');
      setReadonlyState(false);
    }
  }

  // ---- Init --------------------------------------------------------------

  function init() {
    const section = $('#brandguide-section');
    if (!section) return;

    const input = $('#brandguide-upload-input');
    const triggerBtn = $('#btn-trigger-brandguide-upload');
    const uploadArea = $('#brandguide-upload-area');
    const removeBtn = $('#btn-remove-brandguide');

    if (triggerBtn) {
      triggerBtn.addEventListener('click', () => input && input.click());
    }

    if (input) {
      input.addEventListener('change', (e) => {
        const file = e.target.files && e.target.files[0];
        if (file) {
          handleFileSelected(file);
          input.value = '';
        }
      });
    }

    if (uploadArea) {
      ['dragenter', 'dragover'].forEach((evt) => {
        uploadArea.addEventListener(evt, (e) => {
          e.preventDefault();
          e.stopPropagation();
          uploadArea.classList.add('drag-over');
        });
      });
      ['dragleave', 'drop'].forEach((evt) => {
        uploadArea.addEventListener(evt, (e) => {
          e.preventDefault();
          e.stopPropagation();
          uploadArea.classList.remove('drag-over');
        });
      });
      uploadArea.addEventListener('drop', (e) => {
        const file = e.dataTransfer.files && e.dataTransfer.files[0];
        if (file) handleFileSelected(file);
      });
    }

    if (removeBtn) {
      removeBtn.addEventListener('click', async () => {
        try {
          const current = await fetchStatus();
          if (current && current.brandguideId) {
            const ok = await deleteBrandguideViaUI(current.brandguideId);
            if (ok) {
              // Ao apagar, recarrega para refletir a KB com os campos limpos
              window.location.reload();
            }
          } else {
            updateStatusUI(null);
          }
        } catch (e) {
          console.error('[brandguide] erro ao remover:', e);
          setError('Erro ao remover brandguide');
        }
      });
    }

    // Estado inicial ao carregar a pagina
    fetchStatus()
      .then((data) => {
        updateStatusUI(data);
        // Se ja estiver processando ao carregar, retoma o polling
        if (data && PROCESSING_STATUSES.includes(data.status)) {
          pollUntilDone(data.brandguideId);
        }
      })
      .catch(() => {});
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
