/**
 * Brandguide upload (Fase 2).
 *
 * Fluxo:
 *   1. Solicita presigned URL ao backend
 *   2. Faz PUT direto no S3 usando signed_headers do backend
 *   3. Confirma upload criando BrandguideUpload no banco
 *   4. Polling do status ate completed/error
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

  function updateStatusUI(data) {
    const card = $('#brandguide-current');
    const uploadArea = $('#brandguide-upload-area');

    if (!data) {
      hide(card);
      show(uploadArea);
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
      // Link para abrir o PDF em nova aba (presigned URL do backend)
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

    const isProcessing = ['uploaded', 'converting', 'extracting_assets', 'analyzing'].includes(data.status);

    card.classList.toggle('is-processing', isProcessing);
    card.classList.toggle('is-completed', data.status === 'completed');
    card.classList.toggle('is-error', data.status === 'error');

    // Progresso real: pagesProcessed / totalPages
    const total = data.totalPages || 0;
    const processed = data.pagesProcessed || 0;
    let percent = 0;
    if (data.status === 'completed') {
      percent = 100;
    } else if (total > 0) {
      percent = Math.min(99, Math.round((processed / total) * 100));
    } else if (isProcessing) {
      // Antes de ter total_pages ainda: mostra ~5% para nao ficar zerado
      percent = 5;
    }

    if (fillEl) fillEl.style.width = percent + '%';

    if (isProcessing) show(progressEl); else hide(progressEl);

    // Contador de paginas: mostra "X/Y paginas" durante processo, "Y paginas" ao fim
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
    // Usar signed_headers do backend (timestamp sincronizado com a assinatura)
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

  async function pollUntilDone(brandguideId) {
    let attempts = 0;
    while (attempts < POLL_MAX_ATTEMPTS) {
      attempts += 1;
      try {
        const data = await fetchStatus(brandguideId);
        updateStatusUI(data);
        if (!data) return null;
        if (['completed', 'error'].includes(data.status)) {
          return data;
        }
      } catch (err) {
        // Silenciar erros transitorios no polling
        console.warn('[brandguide] status check falhou:', err.message);
      }
      await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
    }
    return null;
  }

  async function deleteBrandguide(brandguideId) {
    if (!confirm('Tem certeza? O brandguide sera removido.')) return false;
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

      // Polling ate conclusao
      await pollUntilDone(record.brandguideId);
    } catch (err) {
      console.error('[brandguide] upload falhou:', err);
      setError(err.message || 'Erro no upload');
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
          input.value = ''; // permitir re-upload do mesmo arquivo depois
        }
      });
    }

    // Drag & drop
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
        const current = await fetchStatus().catch(() => null);
        if (current && current.brandguideId) {
          const ok = await deleteBrandguide(current.brandguideId);
          if (ok) updateStatusUI(null);
        } else {
          updateStatusUI(null);
        }
      });
    }

    // Carregar estado inicial (ja existe brandguide?)
    fetchStatus()
      .then((data) => updateStatusUI(data))
      .catch(() => {});
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
