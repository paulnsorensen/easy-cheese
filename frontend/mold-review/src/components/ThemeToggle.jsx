import React from 'react';

export function ThemeToggle({choice, choices, onChange}) {
  return (
    <div className="ec-segment" role="group" aria-label="Theme">
      {choices.map(option => (
        <button key={option} type="button" aria-pressed={choice === option} onClick={() => onChange(option)}>
          {option}
        </button>
      ))}
    </div>
  );
}
