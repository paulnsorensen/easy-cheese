import React from 'react';

export function ContractTable({artifact}) {
  const columns = artifact.columns || artifact.headers || [];
  const rows = artifact.rows || artifact.data || [];
  return (
    <section className="ec-panel">
      <h3>{artifact.title || artifact.label || 'Contract table'}</h3>
      <div className="ec-table-wrap">
        <table className="ec-table">
          <thead><tr>{columns.map(column => <th key={String(column)}>{String(column)}</th>)}</tr></thead>
          <tbody>{rows.map((row, index) => (
            <tr key={index}>{(Array.isArray(row) ? row : columns.map(column => row[column])).map((cell, cellIndex) => (
              <td key={cellIndex}>{String(cell ?? '')}</td>
            ))}</tr>
          ))}</tbody>
        </table>
      </div>
    </section>
  );
}
