import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./e2e',timeout:120_000,expect:{timeout:30_000},workers:1,retries:0,
 reporter:[['list']],use:{baseURL:'http://localhost:5173',headless:true,trace:'retain-on-failure',screenshot:'only-on-failure'},
 outputDir:'test-results'});
