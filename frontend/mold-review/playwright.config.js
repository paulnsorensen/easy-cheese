import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'tests',fullyParallel:false,timeout:30000,use:{browserName:'chromium',headless:true},reporter:'line'});
