/* Local, dependency-free copy controls for Sphinx code examples. */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('div.highlight > pre').forEach((pre) => {
    const container = pre.parentElement;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'copy-code';
    button.textContent = 'Copy';
    button.setAttribute('aria-label', 'Copy this code block');
    const status = document.createElement('span');
    status.className = 'copy-status';
    status.setAttribute('role', 'status');
    container.append(button, status);
    let reset;
    button.addEventListener('click', async () => {
      const content = pre.cloneNode(true);
      content.querySelectorAll('.linenos').forEach((node) => node.remove());
      const text = content.textContent;
      let copied = false;
      try {
        await navigator.clipboard.writeText(text);
        copied = true;
      } catch (_) {
        // Supports downloaded/offline manuals where Clipboard API is absent.
        const input = document.createElement('textarea');
        input.value = text;
        input.setAttribute('aria-label', 'Code to copy');
        input.style.cssText = 'position:fixed;left:-10000px;top:0';
        document.body.append(input);
        input.select();
        try { copied = document.execCommand('copy'); } catch (_) { /* select below */ }
        input.remove();
        button.focus();
      }
      if (!copied) {
        const range = document.createRange();
        range.selectNodeContents(pre);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
      }
      button.textContent = copied ? 'Copied' : 'Selected';
      status.textContent = copied ? 'Code copied.' : 'Code selected. Use your keyboard copy shortcut.';
      clearTimeout(reset);
      reset = setTimeout(() => { button.textContent = 'Copy'; status.textContent = ''; }, 2500);
    });
  });
});
