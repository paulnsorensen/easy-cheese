import {defineConfig} from '@playwright/test';
// CI also writes the HTML report that the validate workflow uploads on failure.
const reporter=globalThis.process.env.CI?[['line'],['html',{open:'never'}]]:'line';
export default defineConfig({testDir:'tests',fullyParallel:false,timeout:30000,use:{browserName:'chromium',headless:true},reporter});
