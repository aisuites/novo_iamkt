/**
 * GOOGLE FONTS LOADER
 *
 * Carrega a lista oficial de Google Fonts (1900+ familias) do endpoint
 * /knowledge/google-fonts/, com cache em localStorage para evitar refetch
 * a cada page load.
 *
 * Uso:
 *   await window.GoogleFontsLoader.load()  // retorna array de strings
 *   const list = window.GoogleFontsLoader.cached()  // sincrono, pode ser []
 *   window.GoogleFontsLoader.populateSelect(selectEl, valorAtual)
 *
 * Mantemos uma lista de fallback (20 fontes populares) caso fetch + cache
 * falhem - o usuario nunca vê o select vazio.
 */
(function () {
    'use strict';

    const ENDPOINT = '/knowledge/google-fonts/';
    const STORAGE_KEY = 'iamkt:google_fonts:v1';
    const TTL_MS = 24 * 60 * 60 * 1000; // 24h

    const FALLBACK = [
        'Roboto', 'Open Sans', 'Lato', 'Montserrat', 'Oswald',
        'Source Sans Pro', 'Raleway', 'PT Sans', 'Merriweather', 'Ubuntu',
        'Playfair Display', 'Poppins', 'Nunito', 'Quicksand', 'Inter',
        'Work Sans', 'Rubik', 'Mulish', 'Karla', 'DM Sans',
    ];

    let cachedList = null;
    let inflight = null;

    function readFromStorage() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return null;
            const obj = JSON.parse(raw);
            if (!obj || typeof obj !== 'object') return null;
            if (!Array.isArray(obj.families) || obj.families.length === 0) return null;
            if (!obj.expiresAt || obj.expiresAt < Date.now()) return null;
            return obj.families;
        } catch (e) {
            return null;
        }
    }

    function writeToStorage(families) {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({
                families: families,
                expiresAt: Date.now() + TTL_MS,
            }));
        } catch (e) {
            // QuotaExceededError ou similar - ignorar
        }
    }

    function load() {
        if (cachedList && cachedList.length) return Promise.resolve(cachedList);

        const fromStorage = readFromStorage();
        if (fromStorage) {
            cachedList = fromStorage;
            return Promise.resolve(cachedList);
        }

        if (inflight) return inflight;

        inflight = fetch(ENDPOINT, { credentials: 'same-origin' })
            .then(function (r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function (data) {
                const families = (data && Array.isArray(data.families)) ? data.families : [];
                if (families.length === 0) throw new Error('Lista vazia');
                cachedList = families;
                writeToStorage(families);
                return families;
            })
            .catch(function (err) {
                console.warn('[GoogleFontsLoader] usando fallback:', err);
                cachedList = FALLBACK.slice();
                return cachedList;
            })
            .finally(function () {
                inflight = null;
            });

        return inflight;
    }

    function cached() {
        if (cachedList && cachedList.length) return cachedList;
        const fromStorage = readFromStorage();
        if (fromStorage) {
            cachedList = fromStorage;
            return cachedList;
        }
        return FALLBACK.slice();
    }

    /**
     * Popula um <select> com a lista atual (cached() - sincrono).
     * Se ainda nao foi carregada, dispara load() em background e
     * repopula quando chegar.
     */
    function populateSelect(selectEl, valorAtual) {
        if (!selectEl) return;

        function render(families) {
            const current = valorAtual || selectEl.value || '';
            selectEl.innerHTML =
                '<option value="">Selecione...</option>' +
                families.map(function (f) {
                    const sel = (f === current) ? ' selected' : '';
                    const safe = String(f).replace(/"/g, '&quot;');
                    return '<option value="' + safe + '"' + sel + '>' + safe + '</option>';
                }).join('');
        }

        render(cached());

        if (!cachedList || cachedList.length <= FALLBACK.length) {
            load().then(function (families) {
                if (families && families.length > 0) render(families);
            });
        }
    }

    /**
     * Popula um <datalist> com a lista atual. <datalist> permite que um <input>
     * exiba sugestoes filtradas conforme o usuario digita.
     */
    function populateDatalist(datalistEl) {
        if (!datalistEl) return;

        function render(families) {
            datalistEl.innerHTML = families.map(function (f) {
                const safe = String(f).replace(/"/g, '&quot;');
                return '<option value="' + safe + '"></option>';
            }).join('');
        }

        render(cached());

        if (!cachedList || cachedList.length <= FALLBACK.length) {
            load().then(function (families) {
                if (families && families.length > 0) render(families);
            });
        }
    }

    /**
     * Garante que existe um <datalist> compartilhado com a lista de Google Fonts.
     * Cria sob demanda no <body> (id 'google-fonts-datalist') e popula.
     * Retorna o id que pode ser usado em <input list="...">.
     */
    function ensureSharedDatalist() {
        const SHARED_ID = 'google-fonts-datalist';
        let dl = document.getElementById(SHARED_ID);
        if (!dl) {
            dl = document.createElement('datalist');
            dl.id = SHARED_ID;
            document.body.appendChild(dl);
            populateDatalist(dl);
        }
        return SHARED_ID;
    }

    // Pre-carrega em background ao iniciar o script
    load();

    window.GoogleFontsLoader = {
        load: load,
        cached: cached,
        populateSelect: populateSelect,
        populateDatalist: populateDatalist,
        ensureSharedDatalist: ensureSharedDatalist,
        FALLBACK: FALLBACK,
    };
})();
