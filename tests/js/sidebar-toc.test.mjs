import { test } from 'node:test';
import assert from 'node:assert/strict';
import { injectToc, isSkillPageHref } from '../../src/components/sidebar-toc.mjs';

const isActive = (entry) => entry.isCurrent;

function skillLink(href, { isCurrent = false, label = 'label' } = {}) {
	return { type: 'link', label, href, isCurrent, badge: undefined, attrs: {} };
}

test('active skill link with h2s expands into a group excluding the synthetic _top node', () => {
	const sidebar = [
		{
			type: 'group',
			label: 'Skills',
			entries: [skillLink('/skills/age/', { isCurrent: true, label: '/age' })],
		},
	];
	const tocItems = [
		{ depth: 2, slug: '_top', text: 'Overview' },
		{ depth: 2, slug: 'voice', text: 'Voice' },
		{ depth: 2, slug: 'formatting', text: 'Formatting' },
	];

	const result = injectToc(sidebar, tocItems, isActive);

	const group = result[0].entries[0];
	assert.equal(group.type, 'group');
	assert.equal(group.label, '/age');
	assert.equal(group.entries.length, 3);
	assert.deepEqual(group.entries[0], skillLink('/skills/age/', { isCurrent: true, label: '/age' }));
	assert.deepEqual(group.entries[1], {
		type: 'link',
		label: 'Voice',
		href: '/skills/age/#voice',
		isCurrent: false,
		badge: undefined,
		attrs: {},
	});
	assert.deepEqual(group.entries[2], {
		type: 'link',
		label: 'Formatting',
		href: '/skills/age/#formatting',
		isCurrent: false,
		badge: undefined,
		attrs: {},
	});
	assert.ok(!group.entries.some((e) => e.href?.endsWith('#_top')));
});

test('page with no h2s leaves the tree unchanged', () => {
	const sidebar = [
		{
			type: 'group',
			label: 'Skills',
			entries: [skillLink('/skills/age/', { isCurrent: true, label: '/age' })],
		},
	];

	const result = injectToc(sidebar, [], isActive);

	assert.deepEqual(result, sidebar);
});

test('undefined toc items does not throw and leaves the tree unchanged', () => {
	const sidebar = [
		{
			type: 'group',
			label: 'Skills',
			entries: [skillLink('/skills/age/', { isCurrent: true, label: '/age' })],
		},
	];

	const result = injectToc(sidebar, undefined, isActive);

	assert.deepEqual(result, sidebar);
});

test('non-active links stay flat even when h2s exist', () => {
	const sidebar = [
		{
			type: 'group',
			label: 'Skills',
			entries: [skillLink('/skills/age/', { isCurrent: false, label: '/age' })],
		},
	];
	const tocItems = [{ depth: 2, slug: 'voice', text: 'Voice' }];

	const result = injectToc(sidebar, tocItems, isActive);

	assert.deepEqual(result, sidebar);
});

test('active README-style page with h2s is not expanded (skill pages only, ADR-002)', () => {
	const sidebar = [
		{
			type: 'group',
			label: 'Project',
			entries: [skillLink('/readme/', { isCurrent: true, label: 'README' })],
		},
	];
	const tocItems = [{ depth: 2, slug: 'install', text: 'Install' }];

	const result = injectToc(sidebar, tocItems, isActive);

	assert.deepEqual(result, sidebar);
	assert.equal(isSkillPageHref('/readme/'), false);
	assert.equal(isSkillPageHref('/skills/age/'), true);
	assert.equal(isSkillPageHref('/skills/'), false);
});