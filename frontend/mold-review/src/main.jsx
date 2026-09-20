import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {api} from './api.js';
import {useTheme} from './theme.js';
import {ArtifactCanvas} from './components/ArtifactCanvas.jsx';
import {ExcalidrawPanel} from './components/ExcalidrawPanel.jsx';
import {LayoutCards} from './components/LayoutCards.jsx';
import {LayoutTabs} from './components/LayoutTabs.jsx';
import {MermaidPanel} from './components/MermaidPanel.jsx';
import {Question} from './components/Question.jsx';
import {ThemeToggle} from './components/ThemeToggle.jsx';
import './style.css';

const initialData = {
  review_id: '',
  goal: 'Mold review',
  revision: null,
  working: {},
  generation: {},
};
const defaultMermaid = 'sequenceDiagram\n participant User\n participant Agent\n User->>Agent: Review';

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

function App() {
  const {
    data, setData, answers, setAnswers, notes, setNotes, annotations, setAnnotations,
    scene, setScene, artifactValues, setArtifactValues, layout, setLayout, mermaidSource, setMermaidSource,
    hydrate, hydrationVersion, status, setStatus,
  } = useReviewData();
  const [submitted, setSubmitted] = useState(false);
  const [newRevision, setNewRevision] = useState(false);
  const theme = useTheme();
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

  const blocked = hasFailed || status.startsWith('Save failed') || status.startsWith('Conflict');

  async function switchRevision() {
    if (blocked) {
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
    <main className="ec-canvas">
      <header className="ec-canvas-head">
        <div><p className="ec-eyebrow">Mold review canvas</p><h1>{data.goal || 'Mold review'}</h1></div>
        <div className="ec-canvas-tools">
          <ThemeToggle choice={theme.choice} choices={theme.choices} onChange={theme.setChoice} />
          <p className={`ec-status${blocked ? '' : ' ec-status--live'}`} role="status">Revision {revision} · {status}</p>
          {hasFailed && <button type="button" className="ec-btn ec-btn--sm" onClick={discardAutosave}>discard unsaved changes</button>}
          {newRevision && !blocked && <button type="button" className="ec-btn ec-btn--sm" onClick={switchRevision}>new revision available — switch</button>}
        </div>
      </header>
      <LayoutTabs layout={layout} onChange={setLayout} />
      <section className="ec-split">
        <article className="questions">
          <div>
            <h2>Decision questions</h2>
            <p className="ec-canvas-lede">Choose the response that best reflects your review. Your working notes save as you type.</p>
          </div>
          {questions.map(question => (
            <Question
              key={question.id}
              question={question}
              answer={answers[question.id]}
              onChange={value => setAnswers(current => ({...current, [question.id]: value}))}
            />
          ))}
          <label className="ec-field">Working notes<textarea className="ec-input" aria-label="Working notes" value={notes} onChange={event => setNotes(event.target.value)} /></label>
          <label className="ec-field">Annotations<textarea className="ec-input" aria-label="Annotations" value={annotations} onChange={event => setAnnotations(event.target.value)} /></label>
          <button type="button" className="ec-btn ec-btn--fill" onClick={submit} disabled={!revision || submitted}>send to agent</button>
        </article>
        <section className="artifacts">
          <LayoutCards layout={layout} />
          {artifacts.length ? <ArtifactCanvas artifacts={artifacts} values={artifactValues} theme={theme.resolved} onChange={(id, value) => setArtifactValues(current => ({...current, [id]: value}))} /> : <>
            <MermaidPanel source={mermaidSource} theme={theme.resolved} onChange={setMermaidSource} />
            <ExcalidrawPanel scene={scene} theme={theme.resolved} onChange={setScene} />
          </>}
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);