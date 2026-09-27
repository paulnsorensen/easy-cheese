import {test, expect} from '@playwright/test';
import {mkdtemp} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawn, execFileSync} from 'node:child_process';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '../../..');
const archive = join(root, 'skills/mold/scripts/mold.pyz');
const example = name => resolve(here, '../examples', name);

async function serveExample(name) {
  const state = await mkdtemp(join(tmpdir(), 'mold-canvas-'));
  execFileSync('python3', [archive, 'review', 'publish', '--state-dir', state, '--input', example(name)], {cwd: root});
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

function poll(state) {
  return JSON.parse(execFileSync('python3', [archive, 'review', 'poll', '--state-dir', state, '--after', '0', '--timeout', '0'], {cwd: root}).toString());
}

const tab = (page, name) => page.getByRole('button', {name, exact: true});

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

test('annotate mode pins numbered notes and explore mode hides them', async ({page}) => {
  const s = await serveExample('02-sketch.json');
  try {
    await page.goto(s.url);
    const ledger = page.getByRole('region',{name:'Ledger'});
    await ledger.getByRole('button').filter({hasText: 'WAL mode plus a single writer lock file'}).click();
    await page.getByLabel('Note text').fill('Mark [?] until the stale-pid path is validated.');
    await page.getByRole('button', {name: 'queue note'}).click();
    await expect(ledger.getByLabel('note 1')).toBeVisible();
    const queue = page.locator('.mc-queue');
    await expect(queue).toContainText('queued · 1');
    await expect(queue).toContainText('ledger › F-2');
    await expect(page.getByRole('button', {name: 'send to agent · 1'})).toBeVisible();

    await page.getByRole('button', {name: 'explore'}).click();
    await expect(ledger.getByLabel('note 1')).toHaveCount(0);
    await ledger.getByText('Shape of the public interface').click();
    await expect(page.getByLabel('Note text')).toHaveCount(0);

    await page.getByRole('button', {name: 'annotate'}).click();
    await page.getByRole('button', {name: 'Remove note 1'}).click();
    await expect(queue).toHaveCount(0);
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
    await page.getByRole('button', {name: 'send & end'}).click();
    await expect(page.getByText(/Submitted/)).toBeVisible();
    const submitted = poll(s.state);
    expect(submitted.feedback.end_session).toBe(true);
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
