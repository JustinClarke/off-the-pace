import React, { useEffect, useRef } from 'react';

declare global {
  interface Window {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    PagefindUI: new (opts: { element: HTMLElement | null; showImages: boolean }) => void;
  }
}

export default function SearchBar() {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let link: HTMLLinkElement | null = null;
    let script: HTMLScriptElement | null = null;

    const load = async () => {
      try {
        // Pagefind artifacts only exist after `npm run build`.
        // The dev server returns HTML (200) for missing paths, so we must
        // verify the file is actually JS before injecting it as a script.
        const check = await fetch('/pagefind/pagefind-ui.js', { method: 'HEAD' });
        const ct = check.headers.get('content-type') ?? '';
        if (!check.ok || !ct.includes('javascript')) return;

        link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = '/pagefind/pagefind-ui.css';
        document.head.appendChild(link);

        await new Promise<void>((resolve, reject) => {
          script = document.createElement('script');
          script.src = '/pagefind/pagefind-ui.js';
          script.onload = () => resolve();
          script.onerror = () => reject(new Error('pagefind-ui.js not found'));
          document.head.appendChild(script);
        });

        new window.PagefindUI({ element: ref.current, showImages: false });
      } catch {
        // pagefind unavailable   search bar stays empty
      }
    };

    load();

    return () => {
      link?.remove();
      script?.remove();
    };
  }, []);

  return <div ref={ref} className="navbar__search" />;
}
