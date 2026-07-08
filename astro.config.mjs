// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import mermaid from 'astro-mermaid';
import { sidebar } from './src/sidebar.mjs';

export default defineConfig({
  site: 'https://paulnsorensen.github.io',
  base: '/easy-cheese',
  output: 'static',
  integrations: [
    mermaid({
      autoTheme: true,
      mermaidConfig: {
        flowchart: { curve: 'basis' },
      },
    }),
    starlight({
      title: 'easy-cheese',
      description:
        'Harness-agnostic Agent Skills (agentskills.io) — the cheese-making pipeline that ages raw curds into shippable wheels of code.',
      logo: {
        src: './public/favicon.svg',
        alt: 'easy-cheese',
      },
      sidebar,
      components: {
        Sidebar: './src/components/Sidebar.astro',
      },
      customCss: ['./src/styles/cheese.css'],
      social: [
        {
          icon: 'github',
          label: 'GitHub',
          href: 'https://github.com/paulnsorensen/easy-cheese',
        },
      ],
      editLink: {
        baseUrl: 'https://github.com/paulnsorensen/easy-cheese/edit/main/src/content/docs/',
      },
    }),
  ],
});
