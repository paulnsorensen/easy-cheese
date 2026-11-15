import React, {useEffect, useState} from 'react';
import mermaid from 'mermaid';

export function MermaidPanel({source, title = 'Mermaid source', theme, onChange}) {
  const [svg, setSvg] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let live = true;
    setSvg('');
    setError('');
    mermaid.initialize({startOnLoad: false, securityLevel: 'strict', theme: theme === 'dark' ? 'dark' : 'neutral'});
    mermaid
      .render(`mold-${Math.random().toString(36).slice(2)}`, source || 'graph TD; Empty-->Diagram')
      .then(result => live && setSvg(result.svg))
      .catch(renderError => live && setError(String(renderError)));
    return () => {
      live = false;
    };
  }, [source, theme]);

  return (
    <section className="ec-panel">
      <h3>{title}</h3>
      <p className="ec-artifact-note">Edit the Mermaid source directly. The preview updates as you work.</p>
      <label className="ec-field">
        Source
        <textarea className="ec-input ec-input--code" aria-label={title} value={source} onChange={event => onChange(event.target.value)} />
      </label>
      <div className="ec-diagram diagram" aria-label="Mermaid rendering">
        {error ? <p role="alert">Diagram error: {error}</p> : <div dangerouslySetInnerHTML={{__html: svg}} />}
      </div>
    </section>
  );
}
