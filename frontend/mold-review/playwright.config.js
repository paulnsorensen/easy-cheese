import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'tests',fullyParallel:false,timeout:60000,use:{browserName:'chromium',headless:true},reporter:'line'});
