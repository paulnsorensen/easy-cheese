import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import mermaid from 'mermaid';
import {Excalidraw} from '@excalidraw/excalidraw';
import '@excalidraw/excalidraw/index.css';
import './style.css';

const token = new URLSearchParams(location.search).get('token') || '';
const initialData = {
  review_id: '',
  goal: 'Mold review',
  revision: null,
  working: {},
  generation: {},
};
const defaultMermaid = 'sequenceDiagram\n participant User\n participant Agent\n User->>Agent: Review';

async function api(path, options = {}) {
  const headers = {
    'X-Mold-Token': token,
    ...(options.body ? {'Content-Type': 'application/json'} : {}),
    ...(options.headers || {}),
  };
  const response = await fetch(path, {...options, headers});
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.error || `HTTP ${response.status}`);
  }
  return response.json();
}

function Question({question, answer, onChange}) {
  const mode = question.selection_mode || question.selectionMode || 'single';
  const selected = answer?.selected || [];
  const other = answer?.other || '';

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

  const recommended = question.recommended_option_id || question.recommended;

  return (
    <fieldset className="question">
      <legend>{question.prompt || question.text}</legend>
      <small>Question ID: {question.id} · Selection mode: {mode}</small>
      <div className="options">
        {(question.options || []).map(option => (
          <label key={option.id}>
            <input
              type={mode === 'single' ? 'radio' : 'checkbox'}
              name={question.id}
              checked={selected.includes(option.id)}
              onChange={() => selectOption(option.id)}
            />
            <b>{option.label}</b>
            <small>
              Option ID: {option.id}
              {(option.id === recommended || option.recommended) && ' · Recommended'}
              {option.tradeoff || option.description ? ` · ${option.tradeoff || option.description}` : ''}
            </small>
          </label>
        ))}
      </div>
      <label className="other">
        Other
        <input
          value={other}
          onChange={event => onChange({selected, other: event.target.value})}
          placeholder="Add your own response"
        />
      </label>
    </fieldset>
  );
}

function MermaidPanel({source, onChange}) {
  const [svg, setSvg] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let live = true;
    setSvg('');
    setError('');
    mermaid.initialize({startOnLoad: false, securityLevel: 'strict'});
    mermaid
      .render(`mold-${Math.random().toString(36).slice(2)}`, source || 'graph TD; Empty-->Diagram')
      .then(result => live && setSvg(result.svg))
      .catch(renderError => live && setError(String(renderError)));
    return () => {
      live = false;
    };
  }, [source]);

  return (
    <section className="artifact">
      <h3>Mermaid source</h3>
      <textarea aria-label="Mermaid source" value={source} onChange={event => onChange(event.target.value)} />
      <div className="diagram" aria-label="Mermaid rendering">
        {error ? <p role="alert">Diagram error: {error}</p> : <div dangerouslySetInnerHTML={{__html: svg}} />}
      </div>
    </section>
  );
}

function ExcalidrawPanel({scene, onChange}) {
  const [exported, setExported] = useState('');
  const last = useRef('');
  const initial = useMemo(
    () => scene || {elements: [], appState: {viewBackgroundColor: '#ffffff'}, files: {}},
    [scene],
  );

  const update = useCallback((elements, appState, files) => {
    const next = {elements, appState, files};
    const key = JSON.stringify({elements, files});
    if (key !== last.current) {
      last.current = key;
      onChange(next);
    }
  }, [onChange]);

  function handleExport(blob) {
    if (blob) {
      setExported(URL.createObjectURL(blob));
    }
  }

  return (
    <section className="artifact">
      <h3>Editable Excalidraw scene</h3>
      <div className="excalidraw">
        <Excalidraw
          initialData={initial}
          onChange={update}
          onExportedImageChange={handleExport}
        />
      </div>
      {exported && <a href={exported} download="mold-review.png">Exported image reference</a>}
      <p className="hint">Scene data stays local and remains editable.</p>
    </section>
  );
}

function workingCopy(review) {
  return review.working?.[review.revision?.number] || {};
}

function useReviewData() {
  const [data, setData] = useState(initialData);
  const [answers, setAnswers] = useState({});
  const [notes, setNotes] = useState('');
  const [annotations, setAnnotations] = useState('');
  const [scene, setScene] = useState(null);
  const [layout, setLayout] = useState('mixed');
  const [mermaidSource, setMermaidSource] = useState(defaultMermaid);
  const [status, setStatus] = useState('Loading');

  function hydrate(review) {
    const working = workingCopy(review);
    setAnswers(working.answers || {});
    setNotes(working.notes || '');
    setAnnotations(working.annotations || '');
    setScene(working.scene || null);
    setLayout(working.layout || 'mixed');
    setMermaidSource(working.mermaid_source || defaultMermaid);
  }

  useEffect(() => {
    api('/api/review')
      .then(review => {
        setData(review);
        hydrate(review);
        setStatus('Saved');
      })
      .catch(error => setStatus(error.message));
  }, []);

  return {
    data,
    setData,
    answers,
    setAnswers,
    notes,
    setNotes,
    annotations,
    setAnnotations,
    scene,
    setScene,
    layout,
    setLayout,
    mermaidSource,
    setMermaidSource,
    hydrate,
    status,
    setStatus,
  };
}

function useAutosave({data, feedback, revision, setData, setStatus}) {
  const autosave = useRef({pending: null, busy: false, generation: {}});

  useEffect(() => {
    if (!revision) return undefined;
    autosave.current.pending = {revision, feedback};

    async function flush() {
      if (autosave.current.busy) return;
      autosave.current.busy = true;
      while (autosave.current.pending) {
        const job = autosave.current.pending;
        autosave.current.pending = null;
        const generation = autosave.current.generation[job.revision] ?? data.generation?.[job.revision] ?? 0;
        try {
          const result = await api('/api/autosave', {
            method: 'POST',
            body: JSON.stringify({revision: job.revision, generation, feedback: job.feedback}),
          });
          autosave.current.generation[job.revision] = result.generation;
          setData(current => ({
            ...current,
            generation: {...current.generation, [job.revision]: result.generation},
          }));
          setStatus('Saved');
        } catch (error) {
          const message = String(error.message);
          if (message.includes('stale')) {
            setStatus('Conflict: durable review changed. Local edits remain unsent.');
          } else {
            setStatus(`Save failed: ${message}`);
          }
        }
      }
      autosave.current.busy = false;
      if (autosave.current.pending) void flush();
    }

    const timer = setTimeout(flush, 400);
    return () => clearTimeout(timer);
  }, [data.generation, feedback, revision, setData, setStatus]);
}

function LayoutCards({layout}) {
  return (
    <>
      {(layout === 'frontend' || layout === 'mixed') && (
        <div className="card"><h2>Frontend</h2><p>Wireframes, flows, and component states.</p></div>
      )}
      {(layout === 'tui' || layout === 'mixed') && (
        <div className="card"><h2>TUI</h2><pre>{'┌──────────────────────────┐\n│ Mold review · focus state │\n└──────────────────────────┘'}</pre></div>
      )}
      {(layout === 'backend' || layout === 'mixed') && (
        <div className="card"><h2>Backend</h2><p>Contracts, boundaries, and request sequence.</p></div>
      )}
    </>
  );
}

function App() {
  const {
    data, setData, answers, setAnswers, notes, setNotes, annotations, setAnnotations,
    scene, setScene, layout, setLayout, mermaidSource, setMermaidSource,
    hydrate, status, setStatus,
  } = useReviewData();
  const [submitted, setSubmitted] = useState(false);
  const [newRevision, setNewRevision] = useState(false);
  const revision = data.revision?.number || 0;
  const questions = data.revision?.document?.questions || [];
  const serializedAnswers = useMemo(
    () => Object.fromEntries(questions.map(question => [
      question.id,
      {
        ...(answers[question.id] || {}),
        selection_mode: question.selection_mode || question.selectionMode || 'single',
      },
    ])),
    [answers, questions],
  );
  const feedback = useMemo(
    () => ({answers: serializedAnswers, notes, annotations, scene, mermaid_source: mermaidSource, layout}),
    [serializedAnswers, notes, annotations, scene, mermaidSource, layout],
  );

  useAutosave({data, feedback, revision, setData, setStatus});

  useEffect(() => {
    if (!revision) return undefined;
    const timer = setInterval(() => {
      api('/api/review')
        .then(review => {
          if (review.revision?.number > revision) setNewRevision(true);
        })
        .catch(() => {});
    }, 1500);
    return () => clearInterval(timer);
  }, [revision]);

  async function submit() {
    setStatus('Sending');
    try {
      const result = await api('/api/submit', {
        method: 'POST',
        body: JSON.stringify({revision, operation_id: `browser-${revision}`, feedback}),
      });
      setSubmitted(true);
      setStatus(`Submitted ${result.submission_id}`);
    } catch (error) {
      setStatus(`Submit failed: ${error.message}`);
    }
  }

  async function switchRevision() {
    const review = await api('/api/review');
    setData(review);
    hydrate(review);
    setSubmitted(false);
    setNewRevision(false);
    setStatus('Saved');
  }

  return (
    <main className="canvas">
      <header>
        <div><p className="eyebrow">MOLD REVIEW CANVAS</p><h1>{data.goal || 'Mold review'}</h1></div>
        <div className="status" role="status">
          Revision {revision} · {status}
          {newRevision && <button onClick={switchRevision}>New revision available — switch</button>}
        </div>
      </header>
      <nav aria-label="Review layout">
        {['frontend', 'tui', 'backend', 'mixed'].map(option => (
          <button key={option} className={layout === option ? 'active' : ''} onClick={() => setLayout(option)}>
            {option}
          </button>
        ))}
      </nav>
      <section className={`layout ${layout}`}>
        <article className="questions">
          <h2>Decision questions</h2>
          {(data.revision?.document?.questions || []).map(question => (
            <Question
              key={question.id}
              question={question}
              answer={answers[question.id]}
              onChange={value => setAnswers(current => ({...current, [question.id]: value}))}
            />
          ))}
          <label className="notes">Working notes<textarea aria-label="Working notes" value={notes} onChange={event => setNotes(event.target.value)} /></label>
          <label className="notes">Annotations<textarea aria-label="Annotations" value={annotations} onChange={event => setAnnotations(event.target.value)} /></label>
          <button className="send" onClick={submit} disabled={!revision || submitted}>Send to agent</button>
        </article>
        <section className="artifacts">
          <LayoutCards layout={layout} />
          <MermaidPanel source={mermaidSource} onChange={setMermaidSource} />
          <ExcalidrawPanel scene={scene} onChange={setScene} />
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);