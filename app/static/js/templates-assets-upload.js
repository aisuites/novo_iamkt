/**
 * Upload de Templates Visuais e Assets de Grafismo (Fase 4).
 * Segue mesmo padrao de presigned URL do brandguide-upload.js.
 */
(function () {
  'use strict';

  function getCsrfToken() {
    const name = 'csrftoken=';
    for (const raw of document.cookie.split(';')) {
      const c = raw.trim();
      if (c.startsWith(name)) return decodeURIComponent(c.slice(name.length));
    }
    return '';
  }

  // ============================================================
  // TEMPLATES
  // ============================================================

  const templateInput = document.getElementById('template-upload-input');
  if (templateInput) {
    templateInput.addEventListener('change', async (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;
      templateInput.value = '';
      await uploadItem(file, 'template');
    });
  }

  // ============================================================
  // ASSETS
  // ============================================================

  const assetInput = document.getElementById('asset-upload-input');
  if (assetInput) {
    assetInput.addEventListener('change', async (e) => {
      const file = e.target.files && e.target.files[0];
      if (!file) return;
      assetInput.value = '';
      await uploadItem(file, 'asset');
    });
  }

  // ============================================================
  // UPLOAD GENERICO
  // ============================================================

  async function uploadItem(file, type) {
    const isTemplate = type === 'template';
    const urlEndpoint = isTemplate
      ? '/knowledge/template/upload-url/'
      : '/knowledge/asset/upload-url/';
    const createEndpoint = isTemplate
      ? '/knowledge/template/create/'
      : '/knowledge/asset/create/';
    const gallery = document.getElementById(
      isTemplate ? 'templates-gallery' : 'assets-gallery'
    );

    try {
      // 1. Obter presigned URL
      const urlResp = await fetch(urlEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-CSRFToken': getCsrfToken(),
        },
        body: new URLSearchParams({
          fileName: file.name,
          fileType: file.type,
          fileSize: String(file.size),
        }),
      });
      const urlData = await urlResp.json();
      if (!urlResp.ok || !urlData.success) {
        throw new Error(urlData.error || 'Falha ao obter URL de upload');
      }

      // 2. Upload para S3 usando signed_headers
      const headers = { 'Content-Type': file.type, ...(urlData.data.signed_headers || {}) };
      const s3Resp = await fetch(urlData.data.upload_url, {
        method: 'PUT',
        body: file,
        headers,
      });
      if (!s3Resp.ok) throw new Error('Falha ao enviar para S3');

      // 3. Criar registro no banco
      const name = file.name.replace(/\.(png|jpg|jpeg|webp|svg)$/i, '');
      const createBody = new URLSearchParams({
        s3Key: urlData.data.s3_key,
        name: name,
      });
      if (isTemplate) {
        createBody.append('templateType', 'outro');
        createBody.append('socialNetwork', 'universal');
      } else {
        createBody.append('orientation', 'both');
      }

      const createResp = await fetch(createEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'X-CSRFToken': getCsrfToken(),
        },
        body: createBody,
      });
      const createData = await createResp.json();
      if (!createResp.ok || !createData.success) {
        throw new Error(createData.error || 'Falha ao registrar');
      }

      // 4. Adicionar preview na galeria
      const itemId = isTemplate ? createData.data.templateId : createData.data.assetId;
      const previewUrl = createData.data.previewUrl;
      addPreviewToGallery(gallery, itemId, name, previewUrl, type);

      if (window.toaster) {
        window.toaster.success(
          isTemplate ? 'Template enviado!' : 'Asset enviado!',
          { duration: 2000 }
        );
      }
    } catch (err) {
      console.error(`[${type}] upload falhou:`, err);
      if (window.toaster) {
        window.toaster.error(err.message || 'Erro no upload');
      }
    }
  }

  function addPreviewToGallery(gallery, itemId, name, previewUrl, type) {
    if (!gallery) return;

    const isTemplate = type === 'template';
    const size = isTemplate ? '120px' : '90px';

    const div = document.createElement('div');
    div.className = `${type}-preview-item`;
    div.dataset[isTemplate ? 'templateId' : 'assetId'] = itemId;
    div.style.cssText = `position:relative; width:${size}; height:${size}; border-radius:10px; overflow:hidden; border:1px solid #e2e8f0; background:#f8fafc;`;

    const img = document.createElement('img');
    img.src = previewUrl;
    img.alt = name;
    img.style.cssText = `width:100%; height:100%; object-fit:${isTemplate ? 'cover' : 'contain'}; ${isTemplate ? '' : 'padding:4px;'}`;
    div.appendChild(img);

    if (isTemplate) {
      const label = document.createElement('div');
      label.style.cssText = 'position:absolute; bottom:0; left:0; right:0; background:rgba(0,0,0,0.6); padding:3px 6px;';
      label.innerHTML = `<span style="color:#fff; font-size:10px; display:block; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${name}</span>`;
      div.appendChild(label);
    }

    const delBtn = document.createElement('button');
    delBtn.type = 'button';
    delBtn.title = 'Remover';
    delBtn.innerHTML = '&times;';
    delBtn.style.cssText = 'position:absolute; top:3px; right:3px; width:20px; height:20px; border-radius:50%; border:none; background:rgba(0,0,0,0.5); color:#fff; cursor:pointer; font-size:12px; display:flex; align-items:center; justify-content:center;';
    delBtn.addEventListener('click', () => {
      if (isTemplate) deleteTemplate(itemId, div);
      else deleteAsset(itemId, div);
    });
    div.appendChild(delBtn);

    gallery.appendChild(div);
  }

  // ============================================================
  // DELETE
  // ============================================================

  window.deleteTemplate = async function (id, el) {
    if (!confirm('Remover este template?')) return;
    try {
      const resp = await fetch(`/knowledge/template/${id}/delete/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrfToken() },
      });
      const data = await resp.json();
      if (data.success) {
        const item = el || document.querySelector(`[data-template-id="${id}"]`);
        if (item) item.remove();
      }
    } catch (err) {
      console.error('Delete template falhou:', err);
    }
  };

  window.deleteAsset = async function (id, el) {
    if (!confirm('Remover este asset?')) return;
    try {
      const resp = await fetch(`/knowledge/asset/${id}/delete/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCsrfToken() },
      });
      const data = await resp.json();
      if (data.success) {
        const item = el || document.querySelector(`[data-asset-id="${id}"]`);
        if (item) item.remove();
      }
    } catch (err) {
      console.error('Delete asset falhou:', err);
    }
  };
})();
