import {test, expect} from '@playwright/test';
import {mkdtemp, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn, execFileSync} from 'node:child_process';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '../../..');
const archive = join(root, 'skills/mold/scripts/mold.pyz');
const example = name => resolve(here, '../examples', name);

async function serve(state) {
  const child = spawn('python3', [archive, 'review', 'serve', '--state-dir', state, '--port', '0'], {cwd: root, stdio: ['ignore', 'pipe', 'inherit']});
  const line = await new Promise((done, fail) => {
    const timer = setTimeout(() => fail(Error('server did not start')), 10000);
    child.stdout.once('data', data => {
      clearTimeout(timer);
      done(JSON.parse(data.toString()));
    });
  });
  return {state, child, ...line};
}

async function serveExample(name) {
  const state = await mkdtemp(join(tmpdir(), 'mold-canvas-'));
  execFileSync('python3', [archive, 'review', 'publish', '--state-dir', state, '--input', example(name)], {cwd: root});
  return serve(state);
}

async function serveDocument(document) {
  const state = await mkdtemp(join(tmpdir(), 'mold-canvas-'));
  const input = join(state, 'revision.json');
  await writeFile(input, JSON.stringify(document));
  execFileSync('python3', [archive, 'review', 'publish', '--state-dir', state, '--input', input], {cwd: root});
  return serve(state);
}

function poll(state) {
  return JSON.parse(execFileSync('python3', [archive, 'review', 'poll', '--state-dir', state, '--after', '0', '--timeout', '0'], {cwd: root}).toString());
}

const tab = (page, name) => page.getByRole('button', {name, exact: true});
// A submit fsyncs while it holds the server lock, so wait for its response, not a fixed time budget.
const submitResponse = page => page.waitForResponse(res => res.url().endsWith('/api/submit') && res.request().method() === 'POST');

test('sketch example renders ledger, placement, diagram, trail, and revisions', async ({page}) => {
  const s = await serveExample('02-sketch.json');
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(s.url);
    await expect(page.getByText('goal · light tier · sketch')).toBeVisible();
    await expect(page.locator('h1 em')).toHaveText('file-only');
    const ledger = page.getByRole('region',{name:'Ledger'});
    await expect(ledger.getByText('decided', {exact: true})).toBeVisible();
    await expect(ledger.locator('code', {hasText: '.cheese/db/store.sqlite'})).toBeVisible();
    await expect(page.getByRole('region',{name:'Placement'})).toContainText('Store.query(kind, **where)');
    await expect(page.getByRole('heading', {name: 'Write path'})).toBeVisible();
    await expect(page.locator('.diagram svg')).toBeVisible();
    await page.getByRole('button', {name: 'Add note on diagram › Write path'}).click();
    await page.getByLabel('Note text').fill('Confirm the lock file path matches the placement block.');
    await page.getByRole('button', {name: 'queue note'}).click();
    await expect(page.locator('.mc-queue')).toContainText('diagram › Write path');
    await expect(page.getByRole('region',{name:'Gates'})).toHaveCount(0);
    await expect(page.getByText('F-2 · WAL + writer lock')).toBeVisible();
    await expect(page.getByText('waits on F-3')).toBeVisible();
    await page.getByRole('button', {name: 'revisions'}).click();
    await expect(page.getByRole('dialog', {name: 'Revisions'})).toContainText('r3 · sketch');
    await tab(page, 'gates').click();
    await expect(page.getByRole('heading', {name: 'Gates · 7 of 17 met'})).toBeVisible();
    await expect(page.getByRole('region',{name:'Ledger'})).toHaveCount(0);
    await expect(tab(page, 'decision map')).toBeDisabled();
    expect(errors).toEqual([]);
  } finally {
    s.child.kill();
  }
});

test('annotate mode pins numbered notes and explore mode hides them', async ({page, request}) => {
  const s = await serveExample('02-sketch.json');
  try {
    await page.goto(s.url);
    const ledger = page.getByRole('region',{name:'Ledger'});
    await ledger.getByRole('button').filter({hasText: 'WAL mode plus a single writer lock file'}).click();
    await page.getByLabel('Note text').fill('a');
    await page.getByRole('button', {name: 'queue note'}).click();
    await expect(ledger.getByLabel('note 1')).toBeVisible();
    const queue = page.locator('.mc-queue');
    await expect(queue).toContainText('queued · 1');
    await expect(queue).toContainText('ledger › F-2');
    await expect(page.getByRole('button', {name: 'send to agent · 1'})).toBeVisible();

    await page.getByRole('button', {name: 'Add note on diagram › Write path'}).click();
    await page.getByLabel('Note text').fill('b');
    const savedBoth = page.waitForResponse(res => res.url().endsWith('/api/autosave')
      && res.request().postData()?.includes('2. b (diagram') && res.ok());
    await page.getByRole('button', {name: 'queue note'}).click();
    await expect(queue).toContainText('queued · 2');
    await savedBoth;
    await expect.poll(async () => {
      const review = await request.get(`${new URL(s.url).origin}/api/review`, {headers: {'X-Mold-Token': s.token}}).then(r => r.json());
      return review.working?.[review.revision.number]?.annotations;
    }).toBe('1. a (ledger › F-2)\n2. b (diagram › Write path)');

    await page.getByRole('button', {name: 'explore'}).click();
    await expect(ledger.getByLabel('note 1')).toHaveCount(0);
    await expect(page.getByRole('button', {name: /^Add note on /})).toHaveCount(0);
    await ledger.getByText('Shape of the public interface').click();
    await expect(page.getByLabel('Note text')).toHaveCount(0);

    await page.getByRole('button', {name: 'annotate'}).click();
    await page.getByRole('button', {name: 'Remove note 1'}).click();
    await page.getByRole('button', {name: 'Remove note 1'}).click();
    await expect(queue).toHaveCount(0);
  } finally {
    s.child.kill();
  }
});

test('switching to explore mode closes an open pin editor, inline and block', async ({page}) => {
  const s = await serveExample('02-sketch.json');
  try {
    await page.goto(s.url);
    const ledger = page.getByRole('region',{name:'Ledger'});
    await ledger.getByRole('button').filter({hasText: 'WAL mode plus a single writer lock file'}).click();
    await expect(page.getByLabel('Note text')).toBeVisible();
    await page.getByRole('button', {name: 'explore'}).click();
    await expect(page.getByLabel('Note text')).toHaveCount(0);

    await page.getByRole('button', {name: 'annotate'}).click();
    await page.getByRole('button', {name: 'Add note on diagram › Write path'}).click();
    await expect(page.getByLabel('Note text')).toBeVisible();
    await page.getByRole('button', {name: 'explore'}).click();
    await expect(page.getByLabel('Note text')).toHaveCount(0);

    await page.getByRole('button', {name: 'annotate'}).click();
    await expect(page.getByLabel('Note text')).toHaveCount(0);
  } finally {
    s.child.kill();
  }
});

test('send then send & end use distinct operation ids so the second submit is not rejected', async ({page, request}) => {
  const s = await serveExample('02-sketch.json');
  try {
    await page.goto(s.url);
    await page.locator('fieldset.question').getByRole('radio').first().check();
    const sent = submitResponse(page);
    await page.getByRole('button', {name: /^send to agent/}).click();
    expect((await sent).ok()).toBeTruthy();
    await expect(page.getByText(/Submitted/)).toBeVisible();
    const origin = new URL(s.url).origin;
    const second = await request.post(`${origin}/api/submit`, {
      headers: {'X-Mold-Token': s.token, 'Content-Type': 'application/json', Origin: origin},
      data: {revision: 1, operation_id: 'browser-1-end', feedback: {answers: {}, notes: '', end_session: true}},
    });
    expect(second.ok()).toBeTruthy();
    const first = poll(s.state);
    expect(first.operation_id).toBe('browser-1');
    const secondSubmission = JSON.parse(execFileSync('python3', [archive, 'review', 'poll', '--state-dir', s.state, '--after', '1', '--timeout', '0'], {cwd: root}).toString());
    expect(secondSubmission.operation_id).toBe('browser-1-end');
    expect(secondSubmission.feedback.end_session).toBe(true);
  } finally {
    s.child.kill();
  }
});

test('send and end submits pins and an end_session flag', async ({page}) => {
  const s = await serveExample('02-sketch.json');
  try {
    await page.goto(s.url);
    await page.getByRole('region',{name:'Placement'}).getByRole('button').filter({hasText: 'Store.open(path)'}).click();
    await page.getByLabel('Note text').fill('query should return an iterator, not a list.');
    await page.getByRole('button', {name: 'queue note'}).click();
    await page.locator('fieldset.question').getByRole('radio').first().check();
    const sent = submitResponse(page);
    await page.getByRole('button', {name: 'send & end'}).click();
    expect((await sent).ok()).toBeTruthy();
    await expect(page.getByText(/Submitted/)).toBeVisible();
    const submitted = poll(s.state);
    expect(submitted.feedback.end_session).toBe(true);
    expect(submitted.operation_id).toBe('browser-1-end');
    expect(submitted.feedback.answers).toEqual({'F-3': {selected: ['facade'], other: '', selection_mode: 'single'}});
    expect(submitted.feedback.pins.map(pin => [pin.anchor, pin.text])).toEqual([['placement › public', 'query should return an iterator, not a list.']]);
    expect(submitted.feedback.annotations).toBe('1. query should return an iterator, not a list. (placement › public)');
  } finally {
    s.child.kill();
  }
});

test('decision map example opens on the decision map view', async ({page}) => {
  const s = await serveExample('03-decision-map.json');
  try {
    await page.goto(s.url);
    await expect(tab(page, 'decision map')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByRole('heading', {name: 'Blocked'})).toBeVisible();
    await expect(page.getByText('[BLOCKED]')).toBeVisible();
    await expect(page.getByText('no agent listening · feedback waits for the next poll')).toBeVisible();
    const decisionMap = page.locator('[aria-label="Decision map"]');
    await decisionMap.getByRole('button').filter({hasText: 'Schema migration when a kind changes shape'}).click();
    await page.getByLabel('Note text').fill('Confirm the migration story before locking this in.');
    await page.getByRole('button', {name: 'queue note'}).click();
    await expect(decisionMap.getByLabel('note 1')).toBeVisible();
    const queue = page.locator('.mc-queue');
    await expect(queue).toContainText('decision map › F-4');
    await tab(page, 'all').click();
    await expect(page.getByRole('heading', {name: 'Blocked'})).toHaveCount(0);
    await expect(page.getByRole('region',{name:'Ledger'})).toBeVisible();
  } finally {
    s.child.kill();
  }
});

test('phone width turns the conversation into a bottom sheet', async ({page}) => {
  const s = await serveExample('01-bounds.json');
  try {
    await page.setViewportSize({width: 390, height: 844});
    await page.goto(s.url);
    const sheet = page.getByRole('complementary', {name: 'Conversation'});
    await expect(sheet).toHaveCSS('position', 'fixed');
    await expect(sheet.getByText('Which storage format?')).toBeVisible();
    await page.getByRole('button', {name: 'Lower sheet'}).click();
    await expect(sheet.getByText('Which storage format?')).toBeHidden();
    await page.getByRole('button', {name: 'Raise sheet'}).click();
    await expect(sheet.getByText('Which storage format?')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  } finally {
    s.child.kill();
  }
});

test('malformed agent field types still render the question and rail', async ({page}) => {
  const s = await serveDocument({
    goal: 42,
    goal_emphasis: 7,
    trail: 'not-an-array',
    revisions: {label: 'r1'},
    artifacts: 'nope',
    ledger: 'nope',
    placement: {rows: 'nope'},
    gates: {items: 'nope'},
    decision_map: {settled: 'nope', open: 'nope', verdict: {lines: 'nope'}},
    questions: [{id: 'q-1', prompt: 'Pick one', selection_mode: 'single', options: [{id: 'a', label: 'A'}]}],
  });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(s.url);
    await expect(page.getByText('Pick one')).toBeVisible();
    expect(errors).toEqual([]);
  } finally {
    s.child.kill();
  }
});


test('requirements remain beside shapes and only agent-settled forks unlock', async ({page}) => {
  const state = await mkdtemp(join(tmpdir(), 'mold-requirements-'));
  const input = join(state, 'revision.json');
  const document = {
    goal: 'Shape the full specification',
    requirements: [
      {id: 'R-1', text: 'WHEN the review opens THE SYSTEM SHALL retain the complete settled requirement text.', status: 'settled'},
      {id: 'R-2', text: 'WHEN a fork is open THE SYSTEM SHALL show the complete draft requirement text.', status: 'draft', fork_ids: ['F-1', 'F-3']},
      {id: 'R-3', text: 'WHEN another fork is independent THE SYSTEM SHALL keep its draft requirement visible.', status: 'draft', fork_ids: ['F-2']},
    ],
    questions: [
      {id: 'F-1', prompt: 'Choose storage', options: [{id: 'sqlite', label: 'SQLite'}]},
      {id: 'F-2', prompt: 'Choose display', options: [{id: 'plain', label: 'Plain text'}]},
      {id: 'F-3', prompt: 'Choose migration', depends_on: ['F-1'], options: [{id: 'migrate', label: 'Migrate'}]},
    ],
  };
  await writeFile(input, JSON.stringify(document));
  execFileSync('python3', [archive, 'review', 'publish', '--state-dir', state, '--input', input], {cwd: root});
  const s = await serve(state);
  try {
    await page.goto(s.url);
    const requirements = page.getByRole('region', {name: 'Requirements'});
    const conversation = page.getByRole('complementary', {name: 'Conversation'});
    await expect(requirements).toBeVisible();
    for (const requirement of document.requirements) {
      await expect(requirements.getByText(requirement.text)).toBeVisible();
    }
    await expect(requirements.getByText('settled', {exact: true})).toHaveCount(1);
    await expect(requirements.getByText('draft', {exact: true})).toHaveCount(2);
    await expect(requirements.locator('.mc-requirement-head strong')).toHaveText(['R-2', 'R-3', 'R-1']);
    await expect(requirements).toContainText('Choose storage');
    await expect(requirements).toContainText('F-3 · Choose migration · waiting for F-1');
    await tab(page, 'diagram').click();
    await expect(requirements.getByText(document.requirements[0].text)).toBeVisible();
    await tab(page, 'all').click();
    const boxes = await Promise.all([requirements.boundingBox(), conversation.boundingBox()]);
    expect(boxes[0].x + boxes[0].width).toBeLessThanOrEqual(boxes[1].x);
    const migration = conversation.getByRole('group', {name: 'Choose migration'});
    await expect(migration.getByRole('radio', {name: 'Migrate'})).toBeDisabled();
    await conversation.getByRole('radio', {name: 'SQLite'}).check();
    await expect(migration.getByRole('radio', {name: 'Migrate'})).toBeDisabled();
    await conversation.getByRole('radio', {name: 'Plain text'}).check();
    const sent = submitResponse(page);
    await page.getByRole('button', {name: 'Send to agent'}).click();
    await sent;
    expect(poll(state).feedback.answers).toEqual({
      'F-1': {selected: ['sqlite'], other: '', selection_mode: 'single'},
      'F-2': {selected: ['plain'], other: '', selection_mode: 'single'},
    });
    await expect(migration.getByRole('radio', {name: 'Migrate'})).toBeDisabled();
    document.questions = document.questions.filter(question => question.id !== 'F-1');
    document.settled_fork_ids = ['F-1'];
    await writeFile(input, JSON.stringify(document));
    execFileSync('python3', [archive, 'review', 'publish', '--state-dir', state, '--input', input, '--base-revision', '1'], {cwd: root});
    await page.getByRole('button', {name: /new revision available/i}).click();
    await expect(migration.getByRole('radio', {name: 'Migrate'})).toBeEnabled();
    await expect(requirements).toContainText('F-1 · settled');
    await expect(requirements).not.toContainText('unresolved reference');
    for (const requirement of document.requirements) {
      await expect(requirements.getByText(requirement.text)).toBeVisible();
    }
  } finally {
    s.child.kill();
  }
});


test('declared settlement does not unlock an open prerequisite', async ({page}) => {
  const state = await mkdtemp(join(tmpdir(), 'mold-open-prerequisite-'));
  const input = join(state, 'revision.json');
  const document = {
    settled_fork_ids: ['F-1'],
    questions: [
      {id: 'F-1', prompt: 'Open prerequisite', options: [{id: 'keep', label: 'Keep open'}]},
      {id: 'F-2', prompt: 'Dependent fork', depends_on: ['F-1'], options: [{id: 'go', label: 'Go'}]},
    ],
  };
  await writeFile(input, JSON.stringify(document));
  execFileSync('python3', [archive, 'review', 'publish', '--state-dir', state, '--input', input], {cwd: root});
  const s = await serve(state);
  try {
    await page.goto(s.url);
    const conversation = page.getByRole('complementary', {name: 'Conversation'});
    const dependent = conversation.getByRole('group', {name: 'Dependent fork'});
    await expect(dependent).toContainText('waiting for F-1');
    await expect(dependent.getByRole('radio', {name: 'Go'})).toBeDisabled();
    await conversation.getByRole('radio', {name: 'Keep open'}).check();
    const sent = submitResponse(page);
    await page.getByRole('button', {name: 'Send to agent'}).click();
    await sent;
    expect(poll(state).feedback.answers).toEqual({'F-1': {selected: ['keep'], other: '', selection_mode: 'single'}});
    document.questions = document.questions.filter(question => question.id !== 'F-1');
    await writeFile(input, JSON.stringify(document));
    execFileSync('python3', [archive, 'review', 'publish', '--state-dir', state, '--input', input, '--base-revision', '1'], {cwd: root});
    await page.getByRole('button', {name: /new revision available/i}).click();
    await expect(dependent.getByRole('radio', {name: 'Go'})).toBeEnabled();
  } finally {
    s.child.kill();
  }
});

test('narrow requirements and conversation never overlap, even with a long list', async ({page}) => {
  const requirements = Array.from({length: 24}, (_, index) => ({
    id: `R-${index + 1}`,
    text: `WHEN event ${index + 1} occurs THE SYSTEM SHALL keep its full requirement text visible in the scrollable list.`,
    status: index % 2 ? 'draft' : 'settled',
  }));
  const s = await serveDocument({requirements, questions: [{id: 'F-1', prompt: 'Choose one', options: [{id: 'a', label: 'A'}]}]});
  try {
    await page.setViewportSize({width: 390, height: 844});
    await page.goto(s.url);
    const pane = page.getByRole('region', {name: 'Requirements'});
    const conversation = page.getByRole('complementary', {name: 'Conversation'});
    await expect(pane.getByText(requirements[0].text)).toBeVisible();
    await expect(conversation).toHaveCSS('position', 'static');
    const [paneBox, conversationBox] = await Promise.all([pane.boundingBox(), conversation.boundingBox()]);
    expect(paneBox.y + paneBox.height).toBeLessThanOrEqual(conversationBox.y);
    expect(await pane.locator('.mc-requirements-scroll').evaluate(node => node.scrollHeight > node.clientHeight)).toBe(true);
    await pane.locator('.mc-requirements-scroll').evaluate(node => { node.scrollTop = node.scrollHeight; });
    await expect(pane.getByText(requirements[23].text)).toBeVisible();
    await tab(page, 'diagram').click();
    await conversation.getByRole('radio', {name: 'A'}).check();
    const sent = submitResponse(page);
    await page.getByRole('button', {name: 'Send to agent'}).click();
    await sent;
    await expect(page.getByText(/Submitted/)).toBeVisible();
    const [paneAfter, conversationAfter] = await Promise.all([pane.boundingBox(), conversation.boundingBox()]);
    expect(paneAfter.y + paneAfter.height).toBeLessThanOrEqual(conversationAfter.y);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  } finally {
    s.child.kill();
  }
});

test('short phone keeps a requirement and a whole question card usable under a long goal', async ({page}) => {
  const s = await serveDocument({
    goal: 'Give the agent CLI a file-only database: no server, one directory, safe under concurrent agent writes.',
    summary: 'Three shapes survive the shape check. A facade keeps the crust to two exports; per-entity repositories add one export per kind.',
    requirements: Array.from({length: 6}, (_, index) => ({
      id: `R-${index + 1}`,
      text: `WHEN event ${index + 1} occurs THE SYSTEM SHALL keep its full requirement text visible.`,
      status: index < 3 ? 'settled' : 'draft',
    })),
    questions: [{id: 'F-1', prompt: 'Which shape does the public interface take?', options: [
      {id: 'facade', label: 'Store facade', tradeoff: 'two exports, one lock owner'},
      {id: 'repos', label: 'Repository per entity', tradeoff: 'one export per kind'},
      {id: 'raw', label: 'Raw sqlite3 connection', tradeoff: 'every caller owns the lock'},
    ]}],
  });
  try {
    await page.setViewportSize({width: 375, height: 667});
    await page.goto(s.url);
    const pane = page.getByRole('region', {name: 'Requirements'});
    const shapes = page.locator('section.mc-shapes');
    const conversation = page.getByRole('complementary', {name: 'Conversation'});
    await expect(conversation.getByRole('group', {name: 'Which shape does the public interface take?'})).toBeAttached();
    const fit = await page.evaluate(() => {
      const scroll = document.querySelector('.mc-requirements-scroll');
      const convo = document.querySelector('.mc-convo-scroll');
      return {
        requirement: scroll.clientHeight - scroll.querySelector('.mc-requirement').offsetHeight,
        question: convo.clientHeight - convo.querySelector('.mc-question').offsetHeight,
      };
    });
    expect(fit.requirement).toBeGreaterThanOrEqual(0);
    expect(fit.question).toBeGreaterThanOrEqual(0);
    const [paneBox, shapesBox, conversationBox] = await Promise.all([pane.boundingBox(), shapes.boundingBox(), conversation.boundingBox()]);
    expect(paneBox.y + paneBox.height).toBeLessThanOrEqual(shapesBox.y);
    expect(shapesBox.y + shapesBox.height).toBeLessThanOrEqual(conversationBox.y);
    expect(conversationBox.height).toBeLessThanOrEqual(667);
    await conversation.getByRole('radio', {name: /Raw sqlite3 connection/}).check({timeout: 5000});
    const sent = submitResponse(page);
    await page.getByRole('button', {name: 'Send to agent'}).click();
    await sent;
    expect(poll(s.state).feedback.answers['F-1'].selected).toEqual(['raw']);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  } finally {
    s.child.kill();
  }
});

test('invalid dependencies report errors and restored waiting answers never submit', async ({page, request}) => {
  const s = await serveDocument({
    requirements: [{id: 'R-1', text: 'WHEN dependencies fail THE SYSTEM SHALL show the invalid state.', status: 'draft', fork_ids: ['F-1', 'missing']}],
    questions: [
      {id: 'F-1', prompt: 'Waiting fork', depends_on: ['F-2'], options: [{id: 'a', label: 'A'}]},
      {id: 'F-2', prompt: 'Cycle fork', depends_on: ['F-1'], options: [{id: 'b', label: 'B'}]},
      {id: 'F-3', prompt: 'Missing fork', depends_on: ['absent'], options: [{id: 'c', label: 'C'}]},
      {id: 'F-4', prompt: 'Malformed fork', depends_on: 'F-1', options: [{id: 'd', label: 'D'}]},
      {id: 'F-5', prompt: 'Independent fork', options: [{id: 'e', label: 'E'}]},
    ],
  });
  try {
    const origin = new URL(s.url).origin;
    const response = await request.post(`${origin}/api/autosave`, {
      headers: {'X-Mold-Token': s.token, 'Content-Type': 'application/json', Origin: origin},
      data: {revision: 1, generation: 0, feedback: {answers: {'F-1': {selected: ['a'], other: ''}, 'F-3': {selected: ['c'], other: ''}}}},
    });
    expect(response.status()).toBe(200);
    await page.goto(s.url);
    const conversation = page.getByRole('complementary', {name: 'Conversation'});
    await expect(conversation.getByRole('group', {name: 'Waiting fork'})).toContainText('waiting for F-2');
    await expect(conversation.getByRole('group', {name: 'Cycle fork'})).toContainText('waiting for F-1');
    for (const prompt of ['Missing fork', 'Malformed fork']) {
      await expect(conversation.getByRole('group', {name: prompt})).toContainText('dependency error');
    }
    const pane = page.getByRole('region', {name: 'Requirements'});
    await expect(pane).toContainText('unresolved reference');
    await expect(pane).toContainText('F-1 · Waiting fork · waiting for F-2');
    for (const name of ['Waiting fork', 'Cycle fork', 'Missing fork', 'Malformed fork']) {
      await expect(conversation.getByRole('group', {name}).getByRole('radio').first()).toBeDisabled();
    }
    await expect(conversation.getByRole('radio', {name: 'A a', exact: true})).not.toBeChecked();
    await expect(conversation.getByRole('radio', {name: 'C c', exact: true})).not.toBeChecked();
    await conversation.getByRole('radio', {name: 'E'}).check();
    const sent = submitResponse(page);
    await page.getByRole('button', {name: 'Send to agent'}).click();
    await sent;
    expect(poll(s.state).feedback.answers).toEqual({'F-5': {selected: ['e'], other: '', selection_mode: 'single'}});
  } finally {
    s.child.kill();
  }
});

test('requirements revision restores feedback after a lowered legacy phone sheet', async ({page}) => {
  const s = await serveDocument({questions: [{id: 'F-1', prompt: 'Choose one', options: [{id: 'a', label: 'A'}]}]});
  try {
    await page.setViewportSize({width: 390, height: 844});
    await page.goto(s.url);
    await page.getByRole('button', {name: 'Lower sheet'}).click();
    await expect(page.getByRole('button', {name: 'Raise sheet'})).toBeVisible();
    const input = join(s.state, 'revision.json');
    await writeFile(input, JSON.stringify({
      requirements: [{id: 'R-1', text: 'THE SYSTEM SHALL keep feedback available.', status: 'draft'}],
      questions: [{id: 'F-1', prompt: 'Choose one', options: [{id: 'a', label: 'A'}]}],
    }));
    execFileSync('python3', [archive, 'review', 'publish', '--state-dir', s.state, '--input', input, '--base-revision', '1'], {cwd: root});
    await page.getByRole('button', {name: /new revision available/i}).click();
    await expect(page.getByRole('region', {name: 'Requirements'})).toBeVisible();
    await page.getByRole('radio', {name: 'A a', exact: true}).check();
    const sent = submitResponse(page);
    await page.getByRole('button', {name: 'Send to agent'}).click();
    await sent;
    expect(poll(s.state).feedback.answers['F-1'].selected).toEqual(['a']);
  } finally {
    s.child.kill();
  }
});

test('malformed requirement records preserve valid requirements and feedback', async ({page}) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const s = await serveDocument({
    requirements: [null, false, 'invalid', {id: {}, text: {}, status: {}, fork_ids: [{}]},
      {id: 'R-2', text: 'THE SYSTEM SHALL ignore non-string fork links.', status: 'draft', fork_ids: [{}, 'F-1']},
      {id: 'R-3', text: 'THE SYSTEM SHALL drop an unknown status.', status: 'bogus'},
      {id: 'R-1', text: 'THE SYSTEM SHALL preserve valid requirements.', status: 'settled'}],
    questions: [{id: 'F-1', prompt: 'Choose one', options: [{id: 'a', label: 'A'}]}],
  });
  try {
    await page.goto(s.url);
    const pane = page.getByRole('region', {name: 'Requirements'});
    await expect(pane).toContainText('THE SYSTEM SHALL preserve valid requirements.');
    await expect(pane).toContainText('F-1 · Choose one');
    await expect(pane.locator('.mc-requirement-fork')).toHaveCount(1);
    await expect(pane).not.toContainText('THE SYSTEM SHALL drop an unknown status.');
    await page.getByRole('radio', {name: 'A a', exact: true}).check();
    const sent = submitResponse(page);
    await page.getByRole('button', {name: 'Send to agent'}).click();
    await sent;
    expect(poll(s.state).feedback.answers['F-1'].selected).toEqual(['a']);
    expect(errors).toEqual([]);
  } finally {
    s.child.kill();
  }
});
