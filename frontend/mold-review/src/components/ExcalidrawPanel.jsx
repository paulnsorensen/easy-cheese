import React, {useCallback, useMemo, useRef, useState} from 'react';
import {Excalidraw} from '@excalidraw/excalidraw';
import '@excalidraw/excalidraw/index.css';

function hydrateScene(scene) {
  const initial = scene || {elements: [], appState: {viewBackgroundColor: '#ffffff'}, files: {}};
  const collaborators = initial.appState?.collaborators;
  if (!collaborators || collaborators instanceof Map) return initial;
  return {
    ...initial,
    appState: {...initial.appState, collaborators: new Map(Object.entries(collaborators))},
  };
}

export function ExcalidrawPanel({scene, title = 'Editable Excalidraw scene', theme, onChange}) {
  const [exported, setExported] = useState('');
  const initial = useMemo(() => hydrateScene(scene), [scene]);
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
    <section className="ec-panel">
      <h3>{title}</h3>
      <p className="ec-artifact-note">Draw and revise the spatial artifact in the embedded editor.</p>
      <div className="ec-embed">
        <Excalidraw
          initialData={initial}
          theme={theme}
          onChange={update}
          onExportedImageChange={handleExport}
        />
      </div>
      {exported && <a className="ec-link" href={exported} download="mold-review.png">Exported image reference</a>}
      <p className="ec-artifact-hint">Scene data stays local and remains editable.</p>
    </section>
  );
}
