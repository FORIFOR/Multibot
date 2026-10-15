/* Progressive enhancement of retained records. No model, generated text or hidden-on-load content. */
(() => {
  'use strict';
  const buttons = [...document.querySelectorAll('[data-finding]')];
  const panels = [...document.querySelectorAll('[data-diff]')];
  const show = button => {
    const id = button.dataset.finding;
    buttons.forEach(item => item.setAttribute('aria-pressed', String(item === button)));
    panels.forEach(panel => { panel.hidden = panel.dataset.diff !== id; });
  };
  buttons.forEach(button => button.addEventListener('click', () => show(button)));
  if (buttons.length) show(buttons[0]);
  // Without JavaScript every exact source excerpt is readable in document order.
  const copy = document.getElementById('copy');
  const status = document.getElementById('copy-status');
  if (copy && navigator.clipboard) {
    copy.hidden = false;
    copy.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(document.getElementById('cmd').textContent);
        status.textContent = copy.dataset.copied;
      } catch {
        status.textContent = copy.dataset.failed;
      }
    });
  } else if (copy) copy.hidden = true;
})();
