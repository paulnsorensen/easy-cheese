import React, {useId, useState} from 'react';
import {Inline} from './Shapes.jsx';

// One mark and word per point kind, as the fork-card legend in skills/mold/references/fork-questions.md defines them.
const POINT_KINDS = [['gains', '✔', 'gain'], ['costs', '✘', 'cost'], ['risks', '⚠', 'risk']];

function texts(value) {
  const list = Array.isArray(value) ? value : [value];
  return list.filter(item => typeof item === 'string' && item.trim());
}

function OptionCard({option, type, name, checked, recommended, onSelect}) {
  const detail = option.tradeoff || option.description;
  const points = POINT_KINDS.flatMap(([field, mark, word]) => texts(option[field]).map(text => ({mark, word, text})));
  return (
    <label className="ec-option">
      <input type={type} name={name} checked={checked} onChange={onSelect} />
      <span className="ec-option-body">
        <span className="ec-option-head">
          <strong>{option.label}</strong> <code className="ec-option-id">{option.id}</code>
          {recommended && <> <span className="ec-badge">recommended</span></>}
        </span>
        {detail && <span className="ec-option-detail">{detail}</span>}
        {points.length > 0 && (
          <ul className="ec-option-points">
            {points.map((point, index) => (
              <li key={index} className={`ec-option-point ec-option-point--${point.word}`}>
                <span className="ec-option-mark" aria-hidden="true">{point.mark}</span>
                <span>{point.word}: {point.text}</span>
              </li>
            ))}
          </ul>
        )}
      </span>
    </label>
  );
}

function BasisItem({item}) {
  const hedge = item.confidence && item.confidence !== 'certain' ? ` (${item.confidence})` : '';
  return <>{item.ref && <><code className="ec-chip">{item.ref}</code> </>}<Inline text={item.text} />{hedge}</>;
}

// Leads into the fork from the ledger evidence that opened it:
// "Based on X and Y, the next question is:".
function Basis({id, basis}) {
  const last = basis.length - 1;
  return (
    <p className="mc-fork-basis" id={id}>
      Based on{' '}
      {basis.map((item, index) => (
        <React.Fragment key={index}>
          {index > 0 && (index === last ? `${last > 1 ? ',' : ''} and ` : ', ')}
          <BasisItem item={item} />
        </React.Fragment>
      ))}
      , the next question is:
    </p>
  );
}

export function Question({question, answer, state = {kind: 'ready'}, onChange}) {
  const mode = question.selection_mode || question.selectionMode || 'single';
  const selected = answer?.selected || [];
  const other = answer?.other || '';
  const recommended = question.recommended_option_id || question.recommended;
  const [otherOpen, setOtherOpen] = useState(Boolean(other));
  const meta = question.meta || question.context;
  const basis = question.basis || [];
  const basisId = useId();

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
    <div className="mc-fork">
    {basis.length > 0 && <Basis id={basisId} basis={basis} />}
    <fieldset className="ec-panel ec-question question mc-question" disabled={state.kind !== 'ready'} aria-describedby={basis.length > 0 ? basisId : undefined}>
      <legend>{question.prompt || question.text}</legend>
      <small className="ec-question-meta">{question.id}{meta ? ` · ${meta}` : ''}{mode === 'single' ? '' : ' · choose all that apply'}{state.kind !== 'ready' ? ` · ${state.label}` : ''}</small>
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
      {otherOpen || other ? (
        <label className="ec-field">
          Other
          <input
            className="ec-input"
            value={other}
            autoFocus={!other}
            onChange={event => onChange({selected, other: event.target.value})}
            placeholder="Add your own response"
          />
        </label>
      ) : (
        <button type="button" className="mc-link" onClick={() => setOtherOpen(true)}>other…</button>
      )}
    </fieldset>
    </div>
  );
}
