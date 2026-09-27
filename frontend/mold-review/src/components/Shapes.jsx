import React from 'react';
import {Pinnable} from './Pins.jsx';

// Renders `code` spans in document text as chips. Everything stays React text, never HTML.
export function Inline({text}) {
  return String(text ?? '').split('`').map((part, index) => (
    index % 2 ? <code className="ec-chip" key={index}>{part}</code> : <React.Fragment key={index}>{part}</React.Fragment>
  ));
}

function isAccent(row) {
  return row.tone === 'accent' || row.label === 'asking';
}

function itemAnchor(prefix, item) {
  return `${prefix} › ${item.id || String(item.text || '').slice(0, 32)}`;
}

function Chip({id, accent}) {
  if (!id) return null;
  return <><span className={`ec-chip${accent ? ' mc-chip-accent' : ''}`}>{id}</span>&nbsp; </>;
}

export function LedgerPanel({ledger}) {
  return (
    <section className="ec-panel mc-ledger" aria-label="Ledger">
      {ledger.map((row, rowIndex) => {
        const accent = isAccent(row);
        const dim = row.tone === 'dim' || row.label === 'agent-decided';
        return (
          <React.Fragment key={`${row.label}-${rowIndex}`}>
            <span className={`mc-label${accent ? ' mc-label-accent' : ''}`}>{row.label}</span>
            <div className={`mc-ledger-items${dim ? ' mc-dim' : ''}`}>
              {row.text && <span><Inline text={row.text} /></span>}
              {(row.items || []).map((item, index) => (
                <span key={item.id || index}>
                  <Pinnable anchor={itemAnchor('ledger', item)} highlight={Boolean(item.highlight)}>
                    <Chip id={item.id} accent={accent} />
                    <Inline text={item.text} />
                  </Pinnable>
                </span>
              ))}
            </div>
          </React.Fragment>
        );
      })}
    </section>
  );
}

const KEY_WIDTH = 12;

export function PlacementPanel({placement}) {
  const rows = placement.rows || [];
  return (
    <section className="ec-panel" aria-label="Placement">
      <div className="mc-panel-head"><h3>{placement.title || 'Placement'}</h3>{placement.badge && <span className="mc-rev-badge">{placement.badge}</span>}</div>
      <pre className="ec-code mc-placement">
        {rows.map((row, index) => {
          const [first, ...rest] = String(row.value ?? '').split('\n');
          const body = [`${`${row.key}:`.padEnd(KEY_WIDTH)}${first}`, ...rest.map(line => `${' '.repeat(KEY_WIDTH)}${line}`)].join('\n');
          return (
            <React.Fragment key={row.key || index}>
              <Pinnable anchor={`placement › ${row.key}`}>
                <span className={row.highlight ? 'mc-hl' : undefined}>{body}</span>
              </Pinnable>
              {index < rows.length - 1 ? '\n' : ''}
            </React.Fragment>
          );
        })}
      </pre>
    </section>
  );
}

const GATE_MARKS = {met: '✓', current: '●', open: '○', na: '—'};

export function GatesPanel({gates}) {
  const items = gates.items || [];
  const counted = items.filter(item => item.state !== 'na');
  const met = counted.filter(item => item.state === 'met').length;
  return (
    <section className="ec-panel" aria-label="Gates">
      <h3>Gates · {met} of {counted.length} met</h3>
      <div className="mc-gates">
        {items.map(item => (
          <span key={item.label} className={`mc-gate mc-gate--${item.state || 'open'}`}>
            <span className="mc-gate-mark">{GATE_MARKS[item.state] || GATE_MARKS.open}</span> {item.label}
          </span>
        ))}
      </div>
    </section>
  );
}

export function DecisionMap({map}) {
  const verdict = map.verdict;
  return (
    <div className="mc-decision" aria-label="Decision map">
      <section className="ec-panel mc-stack-5">
        {map.settled?.length > 0 && (
          <div>
            <h3>Settled</h3>
            <div className="mc-map-grid">
              {map.settled.map(item => (
                <React.Fragment key={item.id}>
                  <span className="ec-chip">{item.id}</span>
                  <Pinnable anchor={itemAnchor('decision map', item)}><Inline text={item.text} /></Pinnable>
                </React.Fragment>
              ))}
            </div>
          </div>
        )}
        {map.open?.length > 0 && (
          <div>
            <h3>Open</h3>
            <div className="mc-map-grid mc-map-grid--marker">
              {map.open.map(item => (
                <React.Fragment key={item.id}>
                  <span className="ec-chip">{item.id}</span>
                  <Pinnable anchor={itemAnchor('decision map', item)}><Inline text={item.text} /></Pinnable>
                  <span className="mc-mono-dim">{item.marker || ''}</span>
                </React.Fragment>
              ))}
            </div>
          </div>
        )}
      </section>
      {verdict && (
        <aside className="ec-callout mc-verdict">
          <p className="ec-eyebrow">verdict</p>
          <h4>{verdict.title}</h4>
          {(verdict.lines || []).map((line, index) => <p key={index}>{line}</p>)}
        </aside>
      )}
    </div>
  );
}

const REVISION_MARKS = ['solid', 'dashed', 'dotted'];

export function RevisionsPopover({revisions}) {
  return (
    <div className="ec-panel mc-revisions" role="dialog" aria-label="Revisions">
      <div className="mc-revisions-grid">
        {revisions.map((item, index) => (
          <React.Fragment key={item.label}>
            <span className={`mc-rev-mark mc-rev-mark--${REVISION_MARKS[Math.min(index, REVISION_MARKS.length - 1)]}${index === revisions.length - 1 ? ' mc-rev-mark--current' : ''}`} />
            <span>{item.label}{item.note && <span className="mc-dim"> · {item.note}</span>}</span>
          </React.Fragment>
        ))}
      </div>
    </div>
  );
}

export function TrailRow({item}) {
  const answered = item.state === 'answered';
  return (
    <div className={`mc-trail${answered ? '' : ' mc-trail--waiting'}`}>
      <span>{item.label}</span>
      <span>{answered && <span className="mc-accent">✓ </span>}{item.note || (answered ? 'answered' : 'waiting')}</span>
    </div>
  );
}
