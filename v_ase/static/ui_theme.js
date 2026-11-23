// Shared, synchronous chrome bootstrap. Scientific colors and data never live here.
(() => {
    const root = document.documentElement;
    const appearanceKey = 'v_ase_ui_theme', paletteKey = 'v_ase_ui_palette';
    const palettes = ['graphite', 'slate', 'stone', 'moss'];
    const media = matchMedia('(prefers-color-scheme: dark)');
    const normalize = value => ['light', 'dark'].includes(String(value || '').toLowerCase()) ? String(value).toLowerCase() : 'system';
    const normalizePalette = value => palettes.includes(String(value || '').toLowerCase()) ? String(value).toLowerCase() : 'graphite';
    const read = key => {
        try {
            const cookie = document.cookie.split(';').map(s => s.trim()).find(s => s.startsWith(`${key}=`));
            return cookie ? decodeURIComponent(cookie.slice(key.length + 1)) : localStorage.getItem(key) || '';
        } catch { return ''; }
    };
    const write = (key, value) => {
        try { document.cookie = `${key}=${encodeURIComponent(value)}; Path=/; Max-Age=31536000; SameSite=Lax`; } catch {}
        try { localStorage.setItem(key, value); } catch {}
    };
    const savedAppearance = root.dataset.themePreference || read(appearanceKey), savedPalette = root.dataset.uiPalette || read(paletteKey);
    let preference = normalize(savedAppearance), palette = normalizePalette(savedPalette);
    let persisted = Boolean(savedAppearance), palettePersisted = Boolean(savedPalette);
    const info = () => ({ preference, resolved: root.dataset.uiTheme, palette, persisted, palettePersisted });
    const paint = announce => {
        root.dataset.uiTheme = preference === 'system' ? (media.matches ? 'dark' : 'light') : preference;
        root.dataset.themePreference = preference;
        root.dataset.uiPalette = palette;
        root.style.colorScheme = root.dataset.uiTheme;
        if (announce) dispatchEvent(new CustomEvent('v_ase-theme-change', { detail: info() }));
        return info();
    };
    const apply = (value, { persist = true, announce = true } = {}) => {
        preference = normalize(value);
        if (persist) { persisted = true; write(appearanceKey, preference); }
        return paint(announce);
    };
    const applyPalette = (value, { persist = true, announce = true } = {}) => {
        palette = normalizePalette(value);
        if (persist) { palettePersisted = true; write(paletteKey, palette); }
        return paint(announce);
    };
    const applyPresentation = (value, {persist=true,announce=true}={}) => {
        preference=normalize(value.preference);palette=normalizePalette(value.palette);
        if(persist){persisted=true;palettePersisted=true;write(appearanceKey,preference);write(paletteKey,palette);}
        return paint(announce);
    };
    window.v_aseTheme = { apply, applyPalette, applyPresentation, info, palettes: [...palettes] };
    paint(false);
    media.addEventListener?.('change', () => { if (preference === 'system') paint(true); });
    // The real desktop adapter marks its parent; child editors inherit only
    // presentation metadata, never the privileged native IPC bridge.
    try {
        if (window.vaseDesktop || (parent !== window && parent.document.documentElement.dataset.nativeMenus === 'true')) root.dataset.nativeMenus = 'true';
    } catch {}
})();
