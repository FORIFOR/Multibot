(() => {
  const button = document.querySelector('.copy-install');
  if (!button) return;
  button.addEventListener('click', async () => {
    const status = document.querySelector('.copy-status');
    const ja = document.documentElement.lang === 'ja';
    try {
      await navigator.clipboard.writeText(document.getElementById('install-command').textContent);
      status.textContent = ja ? 'コピーしました' : 'Copied';
      if (window.productEvent) window.productEvent('quickstart_open');
    } catch {
      status.textContent = ja ? '上のコマンドを選択してコピーしてください。' : 'Select and copy the command above.';
    }
  });
})();
