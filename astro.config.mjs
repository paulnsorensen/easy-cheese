// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import { cheeselordTheme } from '@cheeselord/design/starlight';
import { sidebar } from './src/sidebar.mjs';

export default defineConfig({
  site: 'https://paulnsorensen.github.io',
  base: '/easy-cheese',
  output: 'static',
  integrations: [
    starlight({
      title: '🧀 easy-cheese',
      plugins: [cheeselordTheme({ flavor: 'easy-cheese' })],
      description:
        'Harness-agnostic Agent Skills (agentskills.io) — the cheese-making pipeline that ages raw curds into shippable wheels of code.',
      sidebar,
      components: {
        Sidebar: './src/components/Sidebar.astro',
        SiteTitle: './src/components/SiteTitle.astro',
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
