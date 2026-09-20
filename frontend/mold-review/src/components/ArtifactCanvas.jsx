import React from 'react';
import {ContractTable} from './ContractTable.jsx';
import {ExcalidrawPanel} from './ExcalidrawPanel.jsx';
import {MermaidPanel} from './MermaidPanel.jsx';

function artifactId(artifact, index) {
  return String(artifact.id || artifact.artifact_id || `artifact-${index}`);
}

function artifactType(artifact) {
  return String(artifact.type || artifact.kind || artifact.format || '').toLowerCase();
}

export function ArtifactCanvas({artifacts, values, theme, onChange}) {
  return artifacts.map((declared, index) => {
    const id = artifactId(declared, index);
    const artifact = values[id] || declared;
    const type = artifactType(artifact);
    const changed = value => onChange(id, {...declared, ...artifact, ...value});
    if (type === 'image' || type === 'picture') {
      const source = artifact.src || artifact.url || artifact.uri || artifact.data;
      return (
        <section className="ec-panel" key={id}>
          <h3>{artifact.title || artifact.alt || 'Image'}</h3>
          <p className="ec-artifact-note">Reference image for this review decision.</p>
          <img className="ec-figure" src={source} alt={artifact.alt || artifact.title || 'Review artifact'} />
        </section>
      );
    }
    if (type === 'mermaid' || type === 'diagram') {
      const source = artifact.source || artifact.mermaid || artifact.data?.source || '';
      return <MermaidPanel key={id} title={artifact.title || 'Mermaid diagram'} source={source} theme={theme} onChange={source => changed({source})} />;
    }
    if (type === 'contract_table' || type === 'table') {
      return <ContractTable key={id} artifact={artifact} />;
    }
    if (type === 'excalidraw' || type === 'scene') {
      const scene = artifact.scene || artifact.data || artifact;
      return <ExcalidrawPanel key={id} title={artifact.title || 'Editable Excalidraw scene'} scene={scene} theme={theme} onChange={scene => changed({scene})} />;
    }
    return <section className="ec-panel" key={id}><h3>{artifact.title || 'Review artifact'}</h3><pre className="ec-code">{JSON.stringify(artifact, null, 2)}</pre></section>;
  });
}
