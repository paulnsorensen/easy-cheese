import React from 'react';

const TUI_MOCK = '┌──────────────────────────┐\n│ Mold review · focus state │\n└──────────────────────────┘';

export function LayoutCards({layout}) {
  return (
    <>
      {(layout === 'frontend' || layout === 'mixed') && (
        <aside className="ec-callout"><h4>Frontend</h4><p>Wireframes, flows, and component states.</p></aside>
      )}
      {(layout === 'tui' || layout === 'mixed') && (
        <aside className="ec-callout"><h4>TUI</h4><pre>{TUI_MOCK}</pre></aside>
      )}
      {(layout === 'backend' || layout === 'mixed') && (
        <aside className="ec-callout"><h4>Backend</h4><p>Contracts, boundaries, and request sequence.</p></aside>
      )}
    </>
  );
}
