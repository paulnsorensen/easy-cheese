// This pure transform adds the H2 table of contents to the left navigation (ADR-002).
// Sidebar.astro supplies the tree, TOC items, and active-page predicate.
// This module only updates the tree. Node's built-in test runner can test it.

// Starlight's generateToC prepends a synthetic depth-2 title node to every page.
// The node is `{depth: 2, slug: '_top', text: 'Overview'}`.
// It is not a content heading.
// Without this filter, it creates a duplicate "Overview -> #_top" entry.
const TOC_TITLE_SLUG = '_top';

// Anchor links use this class for indentation below their skill link.
// The entries stay as siblings, so the skill name appears once.
// A group label would repeat the current link.
export const ANCHOR_CLASS = 'sidebar-h2-anchor';

// ADR-002 limits the table of contents to routes that match `/skills/<name>/`.
// It excludes `/skills/` and other pages with H2 headings.
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
						attrs: { class: ANCHOR_CLASS, 'aria-label': `${entry.label}: ${heading.text}` },
					})),
				];
			}
			return [entry];
		});
	}

	return walk(sidebar);
}
