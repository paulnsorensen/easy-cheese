import React from 'react';

export const LAYOUTS = ['frontend', 'tui', 'backend', 'mixed'];

export function LayoutTabs({layout, onChange}) {
  return (
    <nav className="ec-tabs" aria-label="Review layout">
      {LAYOUTS.map(option => (
        <button key={option} type="button" className="ec-tab" aria-pressed={layout === option} onClick={() => onChange(option)}>
          {option}
        </button>
      ))}
    </nav>
  );
}
