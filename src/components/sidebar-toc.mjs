// Pure tree-transform for the h2 left-nav TOC override (ADR-002). No Astro /
// Astro.locals access here -- Sidebar.astro supplies the sidebar tree, the
// toc items, and the active-page predicate; this module only mutates the
// tree, so it is testable with node's built-in test runner.

// Starlight's generateToC always prepends a synthetic depth-2 title node
// (`{depth: 2, slug: '_top', text: 'Overview'}`) to every page's toc.items,
// even though it isn't a real content heading. Left in, it renders a
// redundant "Overview -> #_top" entry duplicating the skill link above it.
const TOC_TITLE_SLUG = '_top';

// Anchor links carry this class so the site stylesheet can indent them
// under their skill link; the entries stay siblings rather than a group so
// the skill name renders once (a group label would repeat the current link).
const ANCHOR_CLASS = 'sidebar-h2-anchor';

// ADR-002 scopes the TOC to skill pages (route `/skills/<name>/`), not the
// skills index (`/skills/`) or other pages with h2s (README, Install, ...).
export function isSkillPageHref(href) {
	return /\/skills\/[^/]+\/?$/.test(href ?? '');
}

export function injectToc(sidebar, tocItems, isActive) {
	const h2Headings = (tocItems ?? []).filter(
		(item) => item.depth === 2 && item.slug !== TOC_TITLE_SLUG,
	);

	function walk(entries) {
		return entries.flatMap((entry) => {
			if (entry.type === 'group') {
				return [{ ...entry, entries: walk(entry.entries) }];
			}
			if (
				entry.type === 'link' &&
				isActive(entry) &&
				isSkillPageHref(entry.href) &&
				h2Headings.length > 0
			) {
				return [
					entry,
					...h2Headings.map((heading) => ({
						type: 'link',
						label: heading.text,
						href: `${entry.href}#${heading.slug}`,
						isCurrent: false,
						badge: undefined,
						attrs: { class: ANCHOR_CLASS },
					})),
				];
			}
			return [entry];
		});
	}

	return walk(sidebar);
}
