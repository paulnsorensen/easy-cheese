import React, {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {api} from './api.js';
import {useTheme} from './theme.js';
import {ArtifactCanvas} from './components/ArtifactCanvas.jsx';
import {ExcalidrawPanel} from './components/ExcalidrawPanel.jsx';
import {MermaidPanel} from './components/MermaidPanel.jsx';
import {PinProvider, PinQueue, Pinnable} from './components/Pins.jsx';
import {Question} from './components/Question.jsx';
import {DecisionMap, GatesPanel, Inline, LedgerPanel, PlacementPanel, RevisionsPopover, TrailRow} from './components/Shapes.jsx';
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
  const [pins, setPins] = useState([]);
  const [scene, setScene] = useState(null);
  const [artifactValues, setArtifactValues] = useState({});
  const [view, setView] = useState('');
  const [mermaidSource, setMermaidSource] = useState(defaultMermaid);
  const [status, setStatus] = useState('Loading');
  const [hydrationVersion, setHydrationVersion] = useState(0);

  function hydrate(review) {
    const working = workingCopy(review);
    setAnswers(working.answers || {});
    setNotes(working.notes || '');
    setPins(Array.isArray(working.pins) ? working.pins : []);
    setScene(working.scene || null);
    setArtifactValues(working.artifacts || {});
    setView(working.view || '');
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
    pins,
    setPins,
    scene,
    setScene,
    artifactValues,
    setArtifactValues,
    view,
    setView,
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

const SHAPES = ['ledger', 'placement', 'diagram', 'gates', 'decision map'];
// "all" hides the audit views; they open on their own tabs.
const AUDIT_SHAPES = new Set(['gates', 'decision map']);

function eyebrow(doc) {
  const parts = ['goal', doc.tier && `${doc.tier} tier`, doc.stage].filter(Boolean);
  return parts.length > 1 ? parts.join(' · ') : 'Mold review canvas';
}

function GoalTitle({goal, emphasis}) {
  const at = emphasis ? goal.indexOf(emphasis) : -1;
  if (at < 0) return goal;
  return <>{goal.slice(0, at)}<em>{emphasis}</em>{goal.slice(at + emphasis.length)}</>;
}

// Plain-text mirror of the pins, kept in `annotations` for pollers that read text only.
function pinText(pins) {
  return pins.map((pin, index) => `${index + 1}. ${pin.text} (${pin.anchor})`).join('\n');
}

function availableShapes(doc) {
  const map = doc.decision_map || {};
  return {
    ledger: Array.isArray(doc.ledger) && doc.ledger.length > 0,
    placement: Boolean(doc.placement?.rows?.length),
    diagram: true,
    gates: Boolean(doc.gates?.items?.length),
    'decision map': Boolean(map.settled?.length || map.open?.length || map.verdict),
  };
}

function App() {
  const {
    data, setData, answers, setAnswers, notes, setNotes, pins, setPins,
    scene, setScene, artifactValues, setArtifactValues, view, setView, mermaidSource, setMermaidSource,
    hydrate, hydrationVersion, status, setStatus,
  } = useReviewData();
  const [submitted, setSubmitted] = useState(false);
  const [newRevision, setNewRevision] = useState(false);
  const [annotate, setAnnotate] = useState(true);
  const [revisionsOpen, setRevisionsOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(true);
  const theme = useTheme();
  const revision = data.revision?.number || 0;
  const doc = data.revision?.document || {};
  const questions = doc.questions || [];
  const artifacts = doc.artifacts || [];
  const trail = doc.trail || [];
  const revisions = doc.revisions || [];
  const available = availableShapes(doc);
  const defaultView = doc.stage === 'decision map' && available['decision map'] ? 'decision map' : 'all';
  const activeView = view === 'all' || available[view] ? view : defaultView;
  const show = shape => available[shape] && (activeView === 'all' ? !AUDIT_SHAPES.has(shape) : activeView === shape);

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
    () => ({answers: serializedAnswers, notes, pins, annotations: pinText(pins), scene, artifacts: artifactValues, mermaid_source: mermaidSource, view: activeView}),
    [serializedAnswers, notes, pins, scene, artifactValues, mermaidSource, activeView],
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

  const pinApi = useMemo(() => ({
    annotate,
    pins,
    addPin: (anchor, text) => setPins(current => [...current, {id: `pin-${Date.now().toString(36)}-${current.length}`, anchor, text}]),
    removePin: id => setPins(current => current.filter(pin => pin.id !== id)),
  }), [annotate, pins, setPins]);

  async function submit(end = false) {
    setStatus('Sending');
    try {
      await flushAutosave();
      const payload = end ? {...feedback, end_session: true} : feedback;
      const result = await api('/api/submit', {
        method: 'POST',
        body: JSON.stringify({revision, operation_id: `browser-${revision}`, feedback: payload}),
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

  const goal = doc.goal || data.goal || 'Mold review';
  const agentStatus = doc.agent_status;
  const sendLabel = `send to agent${pins.length ? ` · ${pins.length}` : ''}`;
  const pairShapes = activeView === 'all' && available.placement;

  return (
    <PinProvider value={pinApi}>
      <main className="mc-shell">
        <header className="mc-bar">
          <span className="ec-brand"><span className="mc-brand-root"><a href="https://cheeselord.dev">cheeselord.dev</a><span className="ec-brand-sep">/</span></span><b>easy-cheese</b><span className="ec-brand-sep">/</span>mold</span>
          <div className="mc-bar-tools">
            <div className="ec-segment" role="group" aria-label="Pointer mode">
              <button type="button" aria-pressed={annotate} onClick={() => setAnnotate(true)}>annotate</button>
              <button type="button" aria-pressed={!annotate} onClick={() => setAnnotate(false)}>explore</button>
            </div>
            {revisions.length > 0 && (
              <button type="button" className="mc-link" aria-expanded={revisionsOpen} onClick={() => setRevisionsOpen(open => !open)}>revisions</button>
            )}
            <ThemeToggle choice={theme.choice} choices={theme.choices} onChange={theme.setChoice} />
            <p className={`ec-status${blocked ? '' : ' ec-status--live'}`} role="status">r{revision} · {status}</p>
            {hasFailed && <button type="button" className="ec-btn ec-btn--sm" onClick={discardAutosave}>discard unsaved changes</button>}
            {newRevision && !blocked && <button type="button" className="ec-btn ec-btn--sm mc-btn-accent" onClick={switchRevision}>new revision available — switch</button>}
          </div>
          {revisionsOpen && revisions.length > 0 && <RevisionsPopover revisions={revisions} />}
        </header>

        <div className="mc-goal">
          <p className="ec-eyebrow">{eyebrow(doc)}</p>
          <h1 className="ec-title mc-goal-title"><GoalTitle goal={goal} emphasis={doc.goal_emphasis} /></h1>
        </div>

        <div className="mc-body">
          <section className="mc-shapes" aria-label="Shapes">
            <nav className="ec-tabs" aria-label="Shape views">
              {['all', ...SHAPES].map(shape => (
                <button
                  key={shape}
                  type="button"
                  className="ec-tab"
                  aria-pressed={activeView === shape}
                  disabled={shape !== 'all' && !available[shape]}
                  onClick={() => setView(shape)}
                >
                  {shape}
                </button>
              ))}
            </nav>
            <div className="mc-stack">
              {show('ledger') && <LedgerPanel ledger={doc.ledger} />}
              {(show('placement') || show('diagram')) && (
                <div className={pairShapes ? 'mc-pair' : 'mc-stack'}>
                  {show('diagram') && (
                    <div className="mc-stack">
                      {artifacts.length ? (
                        <ArtifactCanvas artifacts={artifacts} values={artifactValues} theme={theme.resolved} onChange={(id, value) => setArtifactValues(current => ({...current, [id]: value}))} />
                      ) : (
                        <>
                          <Pinnable anchor="diagram › mermaid" handle><MermaidPanel source={mermaidSource} theme={theme.resolved} onChange={setMermaidSource} /></Pinnable>
                          <Pinnable anchor="diagram › sketch" handle><ExcalidrawPanel scene={scene} theme={theme.resolved} onChange={setScene} /></Pinnable>
                        </>
                      )}
                    </div>
                  )}
                  {show('placement') && <PlacementPanel placement={doc.placement} />}
                </div>
              )}
              {show('gates') && <GatesPanel gates={doc.gates} />}
              {show('decision map') && <DecisionMap map={doc.decision_map} />}
              {doc.shape_note && <p className="mc-note">{doc.shape_note}</p>}
            </div>
          </section>

          <aside className={`mc-convo${sheetOpen ? '' : ' mc-convo--lowered'}`} aria-label="Conversation">
            <div className="mc-sheet-head">
              <span className="mc-sheet-grip" aria-hidden="true" />
              <div className="mc-row mc-row--between">
                <p className={`ec-status${agentStatus && !agentStatus.startsWith('no ') ? ' ec-status--live' : ''}`}>
                  {agentStatus || 'feedback autosaves'}{pins.length ? ` · ${pins.length} queued` : ''}
                </p>
                <button type="button" className="mc-link mc-sheet-toggle" aria-label={sheetOpen ? 'Lower sheet' : 'Raise sheet'} onClick={() => setSheetOpen(open => !open)}>{sheetOpen ? '˅' : '˄'}</button>
              </div>
            </div>
            <div className="mc-convo-scroll">
              {doc.summary && <p className="mc-summary"><Inline text={doc.summary} /></p>}
              {trail.filter(item => item.position !== 'after').map(item => <TrailRow key={item.label} item={item} />)}
              {questions.map(question => (
                <Question
                  key={question.id}
                  question={question}
                  answer={answers[question.id]}
                  onChange={value => setAnswers(current => ({...current, [question.id]: value}))}
                />
              ))}
              {trail.filter(item => item.position === 'after').map(item => <TrailRow key={item.label} item={item} />)}
              <PinQueue />
            </div>
            <div className="mc-composer">
              <textarea className="ec-input" aria-label="Message the agent" placeholder="Message the agent" value={notes} onChange={event => setNotes(event.target.value)} />
              <div className="mc-row">
                <button type="button" className="ec-btn ec-btn--fill" onClick={() => submit(false)} disabled={!revision || submitted}>{sendLabel}</button>
                <button type="button" className="mc-link mc-push" onClick={() => submit(true)} disabled={!revision || submitted}>send &amp; end</button>
              </div>
            </div>
          </aside>
        </div>
      </main>
    </PinProvider>
  );
}

createRoot(document.getElementById('root')).render(<App />);

