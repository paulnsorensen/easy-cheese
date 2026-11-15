const token = new URLSearchParams(location.search).get('token') || '';

export async function api(path, options = {}) {
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
