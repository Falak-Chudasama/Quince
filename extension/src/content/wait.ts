export function waitForDomQuiet(
  quietMs: number = 300,
  maxMs: number = 4000
): Promise<{ settled: boolean; reason: string; elapsed_ms: number; mutation_count: number }> {
  return new Promise((resolve) => {
    let mutationCount = 0;
    const startTime = Date.now();
    let quietTimer: any = null;

    const observer = new MutationObserver((mutations) => {
      // Ignore mutations originating inside the Quince overlay
      for (const m of mutations) {
        if ((m.target as Element)?.closest?.('[data-quince-overlay]')) {
          continue;
        }
        mutationCount++;
      }

      if (quietTimer) {
        clearTimeout(quietTimer);
      }
      quietTimer = setTimeout(done, quietMs);
    });

    const done = () => {
      observer.disconnect();
      if (quietTimer) clearTimeout(quietTimer);
      if (hardTimer) clearTimeout(hardTimer);
      resolve({
        settled: true,
        reason: 'quiet',
        elapsed_ms: Date.now() - startTime,
        mutation_count: mutationCount,
      });
    };

    const hardTimer = setTimeout(() => {
      observer.disconnect();
      if (quietTimer) clearTimeout(quietTimer);
      resolve({
        settled: false,
        reason: 'timeout',
        elapsed_ms: Date.now() - startTime,
        mutation_count: mutationCount,
      });
    }, maxMs);

    observer.observe(document.body || document.documentElement, {
      childList: true,
      subtree: true,
      attributes: true,
      characterData: true,
    });

    // Initial quiet timer in case no mutations occur
    quietTimer = setTimeout(done, quietMs);
  });
}
