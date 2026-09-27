import React, {createContext, useContext, useEffect, useState} from 'react';

// Pins are numbered notes the user attaches to a part of the canvas.
// Each pin records an anchor (for example "placement › public") and the note text.
const PinContext = createContext({annotate: false, pins: [], addPin: () => {}, removePin: () => {}});

export const PinProvider = PinContext.Provider;

export function pinNumbers(pins, anchor) {
  return pins.flatMap((pin, index) => (pin.anchor === anchor ? [index + 1] : []));
}

export function PinMarker({number}) {
  return <span className="mc-pin" aria-label={`note ${number}`}>{number}</span>;
}

function PinEditor({anchor, onDone}) {
  const {addPin} = useContext(PinContext);
  const [text, setText] = useState('');
  function queue() {
    if (text.trim()) addPin(anchor, text.trim());
    onDone();
  }
  return (
    <span className="ec-panel mc-pin-editor" role="dialog" aria-label={`Note on ${anchor}`} onClick={event => event.stopPropagation()}>
      <small className="ec-question-meta">{anchor}</small>
      <textarea
        className="ec-input"
        aria-label="Note text"
        autoFocus
        value={text}
        onChange={event => setText(event.target.value)}
        onKeyDown={event => {
          if (event.key === 'Escape') onDone();
          if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) queue();
        }}
      />
      <span className="mc-row">
        <button type="button" className="ec-btn ec-btn--sm mc-btn-accent" onClick={queue}>queue note</button>
        <button type="button" className="mc-link" onClick={onDone}>cancel</button>
      </span>
    </span>
  );
}

// Inline text target: in annotate mode a click opens the note editor.
// Block target (`handle`): a small "+ note" button opens the editor, so
// interactive children such as Excalidraw keep their own pointer input.
export function Pinnable({anchor, handle = false, highlight = false, children}) {
  const {annotate, pins} = useContext(PinContext);
  const [editing, setEditing] = useState(false);
  useEffect(() => {
    if (!annotate) setEditing(false);
  }, [annotate]);
  const numbers = pinNumbers(pins, anchor);
  const markers = annotate && numbers.map(number => <PinMarker key={number} number={number} />);
  const editor = editing && <PinEditor anchor={anchor} onDone={() => setEditing(false)} />;

  if (handle) {
    return (
      <div className="mc-pin-block">
        {children}
        {annotate && (
          <span className="mc-pin-corner">
            {markers}
            <button type="button" className="mc-pin-add" onClick={() => setEditing(true)} aria-label={`Add note on ${anchor}`}>+ note</button>
          </span>
        )}
        {editor}
      </div>
    );
  }

  const pinned = annotate && (numbers.length > 0 || highlight);
  if (!annotate) return <span className="mc-pin-target">{children}</span>;
  return (
    <span className="mc-pin-target">
      <span
        className={`mc-pinnable${pinned ? ' mc-pinned' : ''}`}
        role="button"
        tabIndex={0}
        title={`Add a note on ${anchor}`}
        onClick={() => setEditing(true)}
        onKeyDown={event => {
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            setEditing(true);
          }
        }}
      >
        {children}
      </span>
      {markers}
      {editor}
    </span>
  );
}

export function PinQueue() {
  const {pins, removePin} = useContext(PinContext);
  if (!pins.length) return null;
  return (
    <div className="mc-queue">
      <span className="mc-label">queued · {pins.length}</span>
      {pins.map((pin, index) => (
        <div className="mc-queue-item" key={pin.id}>
          <PinMarker number={index + 1} />
          <span>
            {pin.text}
            <br />
            <span className="mc-mono-dim">{pin.anchor}</span>
          </span>
          <button type="button" className="mc-link" onClick={() => removePin(pin.id)} aria-label={`Remove note ${index + 1}`}>×</button>
        </div>
      ))}
    </div>
  );
}
