// Runs in page's MAIN world to intercept modal script dialogs and keep page non-blocking
(() => {
  const origAlert = window.alert;
  const origConfirm = window.confirm;
  const origPrompt = window.prompt;

  window.alert = function (message?: any) {
    window.dispatchEvent(
      new CustomEvent('__quince_script_dialog', {
        detail: { type: 'alert', message: String(message), auto_response: 'ok' },
      })
    );
  };

  window.confirm = function (message?: any): boolean {
    window.dispatchEvent(
      new CustomEvent('__quince_script_dialog', {
        detail: { type: 'confirm', message: String(message), auto_response: 'false' },
      })
    );
    return false;
  };

  window.prompt = function (message?: any, defaultVal?: any): string | null {
    window.dispatchEvent(
      new CustomEvent('__quince_script_dialog', {
        detail: { type: 'prompt', message: String(message), auto_response: 'null' },
      })
    );
    return null;
  };
})();
