import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
 testDir:"./tests",fullyParallel:false,workers:1,timeout:900000,
 expect:{timeout:20000},retries:0,
 use:{actionTimeout:30000,baseURL:process.env.CYTELLECT_WEB_URL||"http://localhost:3000",...devices["Desktop Chrome"],viewport:{width:1440,height:1000},trace:"off",screenshot:"off",video:"off",
  ...(process.env.CYTELLECT_CHROMIUM_EXECUTABLE?{launchOptions:{executablePath:process.env.CYTELLECT_CHROMIUM_EXECUTABLE}}:{})},
 reporter:"list",
});
