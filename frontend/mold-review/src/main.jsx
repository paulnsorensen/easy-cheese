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

function MermaidPanel({source, title = 'Mermaid source', onChange}) {
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
      <h3>{title}</h3>
      <textarea aria-label={title} value={source} onChange={event => onChange(event.target.value)} />
      <div className="diagram" aria-label="Mermaid rendering">
        {error ? <p role="alert">Diagram error: {error}</p> : <div dangerouslySetInnerHTML={{__html: svg}} />}
      </div>
    </section>
  );
}

function ExcalidrawPanel({scene, title = 'Editable Excalidraw scene', onChange}) {
  const [exported, setExported] = useState('');
  const initial = useMemo(
    () => scene || {elements: [], appState: {viewBackgroundColor: '#ffffff'}, files: {}},
    [scene],
  );
  const initialKey = JSON.stringify({elements: initial.elements || [], files: initial.files || {}});
  const last = useRef(initialKey);
  if (last.current !== initialKey) last.current = initialKey;

  const update = useCallback((elements, appState, files) => {
    const next = {elements, appState, files};
    const key = JSON.stringify({elements: elements || [], files: files || {}});
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
      <h3>{title}</h3>
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

function ContractTable({artifact}) {
  const columns = artifact.columns || artifact.headers || [];
  const rows = artifact.rows || artifact.data || [];
  return (
    <section className="artifact">
      <h3>{artifact.title || artifact.label || 'Contract table'}</h3>
      <table>
        <thead><tr>{columns.map(column => <th key={String(column)}>{String(column)}</th>)}</tr></thead>
        <tbody>{rows.map((row, index) => (
          <tr key={index}>{(Array.isArray(row) ? row : columns.map(column => row[column])).map((cell, cellIndex) => (
            <td key={cellIndex}>{String(cell ?? '')}</td>
          ))}</tr>
        ))}</tbody>
      </table>
    </section>
  );
}

function artifactId(artifact, index) {
  return String(artifact.id || artifact.artifact_id || `artifact-${index}`);
}

function artifactType(artifact) {
  return String(artifact.type || artifact.kind || artifact.format || '').toLowerCase();
}

function ArtifactCanvas({artifacts, values, onChange}) {
  return artifacts.map((declared, index) => {
    const id = artifactId(declared, index);
    const artifact = values[id] || declared;
    const type = artifactType(artifact);
    const changed = value => onChange(id, {...declared, ...artifact, ...value});
    if (type === 'image' || type === 'picture') {
      const source = artifact.src || artifact.url || artifact.uri || artifact.data;
      return <section className="artifact" key={id}><h3>{artifact.title || artifact.alt || 'Image'}</h3><img src={source} alt={artifact.alt || artifact.title || 'Review artifact'} /></section>;
    }
    if (type === 'mermaid' || type === 'diagram') {
      const source = artifact.source || artifact.mermaid || artifact.data?.source || '';
      return <MermaidPanel key={id} title={artifact.title || 'Mermaid diagram'} source={source} onChange={source => changed({source})} />;
    }
    if (type === 'contract_table' || type === 'table') {
      return <ContractTable key={id} artifact={artifact} />;
    }
    if (type === 'excalidraw' || type === 'scene') {
      const scene = artifact.scene || artifact.data || artifact;
      return <ExcalidrawPanel key={id} title={artifact.title || 'Editable Excalidraw scene'} scene={scene} onChange={scene => changed({scene})} />;
    }
    return <section className="artifact" key={id}><h3>{artifact.title || 'Review artifact'}</h3><pre>{JSON.stringify(artifact, null, 2)}</pre></section>;
  });
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
  const [artifactValues, setArtifactValues] = useState({});
  const [layout, setLayout] = useState('mixed');
  const [mermaidSource, setMermaidSource] = useState(defaultMermaid);
  const [status, setStatus] = useState('Loading');
  const [hydrationVersion, setHydrationVersion] = useState(0);

  function hydrate(review) {
    const working = workingCopy(review);
    setAnswers(working.answers || {});
    setNotes(working.notes || '');
    setAnnotations(working.annotations || '');
    setScene(working.scene || null);
    setArtifactValues(working.artifacts || {});
    setLayout(working.layout || 'mixed');
    setMermaidSource(working.mermaid_source || defaultMermaid);
    setHydrationVersion(current => current + 1);
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
    artifactValues,
    setArtifactValues,
    layout,
    setLayout,
    mermaidSource,
    setMermaidSource,
    hydrate,
    hydrationVersion,
    status,
    setStatus,
  };
}

function useAutosave({data, feedback, revision, hydrationVersion, setData, setStatus}) {
  const autosave = useRef({pending: null, failed: null, busy: false, generation: {}, timer: null, promise: null});
  const lastHydrationVersion = useRef(hydrationVersion);
  const generations = useRef(data.generation || {});
  generations.current = data.generation || generations.current;
  const flushRef = useRef(() => Promise.resolve());
  const [hasFailed, setHasFailed] = useState(false);

  const flush = useCallback(async () => {
    if (autosave.current.busy) return autosave.current.promise;
    autosave.current.busy = true;
    const run = (async () => {
      while (autosave.current.failed || autosave.current.pending) {
        const job = autosave.current.failed || autosave.current.pending;
        const generation = autosave.current.generation[job.revision] ?? generations.current[job.revision] ?? 0;
        try {
          const result = await api('/api/autosave', {
            method: 'POST',
            body: JSON.stringify({revision: job.revision, generation, feedback: job.feedback}),
          });
          if (autosave.current.pending === job) autosave.current.pending = null;
          if (autosave.current.failed === job) autosave.current.failed = null;
          autosave.current.generation[job.revision] = result.generation;
          setHasFailed(false);
          generations.current = {...generations.current, [job.revision]: result.generation};
          setData(current => ({
            ...current,
            generation: {...current.generation, [job.revision]: result.generation},
          }));
          setStatus('Saved');
        } catch (error) {
          autosave.current.failed = job;
          setHasFailed(true);
          const message = String(error.message);
          if (message.includes('stale')) {
            setStatus('Conflict: durable review changed. Local edits remain unsent.');
          } else {
            setStatus(`Save failed: ${message}`);
          }
          throw error;
        }
      }
    })();
    autosave.current.promise = run;
    try {
      await run;
    } finally {
      autosave.current.busy = false;
      autosave.current.promise = null;
    }
    if (autosave.current.failed || autosave.current.pending) void flush();
  }, [setData, setStatus]);
  flushRef.current = flush;

  useEffect(() => {
    if (!revision) return undefined;
    if (lastHydrationVersion.current !== hydrationVersion) {
      lastHydrationVersion.current = hydrationVersion;
      return undefined;
    }
    const job = {revision, feedback};
    autosave.current.pending = job;
    if (autosave.current.failed?.revision === revision) autosave.current.failed = job;
    if (autosave.current.timer) clearTimeout(autosave.current.timer);
    autosave.current.timer = setTimeout(() => {
      void flush().catch(() => {});
    }, 400);
    return () => {
      if (autosave.current.timer) clearTimeout(autosave.current.timer);
    };
  }, [feedback, hydrationVersion, revision, flush]);

  const discard = useCallback(() => {
    if (autosave.current.timer) clearTimeout(autosave.current.timer);
    autosave.current.timer = null;
    autosave.current.pending = null;
    autosave.current.failed = null;
    setHasFailed(false);
    setStatus('Unsaved changes discarded');
  }, [setStatus]);

  return {flush: useCallback(() => flushRef.current(), []), discard, hasFailed};
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
    scene, setScene, artifactValues, setArtifactValues, layout, setLayout, mermaidSource, setMermaidSource,
    hydrate, hydrationVersion, status, setStatus,
  } = useReviewData();
  const [submitted, setSubmitted] = useState(false);
  const [newRevision, setNewRevision] = useState(false);
  const revision = data.revision?.number || 0;
  const questions = data.revision?.document?.questions || [];
  const artifacts = data.revision?.document?.artifacts || [];
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
    () => ({answers: serializedAnswers, notes, annotations, scene, artifacts: artifactValues, mermaid_source: mermaidSource, layout}),
    [serializedAnswers, notes, annotations, scene, artifactValues, mermaidSource, layout],
  );

  const {flush: flushAutosave, discard: discardAutosave, hasFailed} = useAutosave({data, feedback, revision, hydrationVersion, setData, setStatus});

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
      await flushAutosave();
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
    if (hasFailed || status.startsWith('Save failed') || status.startsWith('Conflict')) {
      setStatus('Switch failed: unsaved changes remain.');
      return;
    }
    try {
      await flushAutosave();
      const review = await api('/api/review');
      setData(review);
      hydrate(review);
      setSubmitted(false);
      setNewRevision(false);
      setStatus('Saved');
    } catch (error) {
      setStatus(`Switch failed: ${error.message}`);
    }
  }

  return (
    <main className="canvas">
      <header>
        <div><p className="eyebrow">MOLD REVIEW CANVAS</p><h1>{data.goal || 'Mold review'}</h1></div>
        <div className="status" role="status">
          Revision {revision} · {status}
          {hasFailed && <button onClick={discardAutosave}>Discard unsaved changes</button>}
          {newRevision && !hasFailed && !status.startsWith('Save failed') && !status.startsWith('Conflict') && <button onClick={switchRevision}>New revision available — switch</button>}
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
          {questions.map(question => (
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
          {artifacts.length ? <ArtifactCanvas artifacts={artifacts} values={artifactValues} onChange={(id, value) => setArtifactValues(current => ({...current, [id]: value}))} /> : <>
            <MermaidPanel source={mermaidSource} onChange={setMermaidSource} />
            <ExcalidrawPanel scene={scene} onChange={setScene} />
          </>}
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);