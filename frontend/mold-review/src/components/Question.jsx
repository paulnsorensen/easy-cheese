import React from 'react';

function OptionCard({option, type, name, checked, recommended, onSelect}) {
  const detail = option.tradeoff || option.description;
  return (
    <label className="ec-option">
      <input type={type} name={name} checked={checked} onChange={onSelect} />
      <span>
        <strong>{option.label}</strong>
        {recommended && <> <span className="ec-badge">Recommended</span></>}
        <small>Option ID: {option.id}{detail ? ` · ${detail}` : ''}</small>
      </span>
    </label>
  );
}

export function Question({question, answer, onChange}) {
  const mode = question.selection_mode || question.selectionMode || 'single';
  const selected = answer?.selected || [];
  const other = answer?.other || '';
  const recommended = question.recommended_option_id || question.recommended;

  function selectOption(id) {
    if (mode === 'single') {
      onChange({selected: [id], other});
      return;
    }
    const next = selected.includes(id)
      ? selected.filter(value => value !== id)
      : [...selected, id];
    onChange({selected: next, other});
  }

  return (
    <fieldset className="ec-panel ec-question question">
      <legend>{question.prompt || question.text}</legend>
      <small className="ec-question-meta">Question ID: {question.id} · Selection mode: {mode}</small>
      <p className="ec-question-help">{mode === 'single' ? 'Choose one response.' : 'Choose all responses that apply.'}</p>
      <div className="ec-options">
        {(question.options || []).map(option => (
          <OptionCard
            key={option.id}
            option={option}
            type={mode === 'single' ? 'radio' : 'checkbox'}
            name={question.id}
            checked={selected.includes(option.id)}
            recommended={option.id === recommended || Boolean(option.recommended)}
            onSelect={() => selectOption(option.id)}
          />
        ))}
      </div>
      <label className="ec-field">
        Other
        <input
          className="ec-input"
          value={other}
          onChange={event => onChange({selected, other: event.target.value})}
          placeholder="Add your own response"
        />
      </label>
    </fieldset>
  );
}
