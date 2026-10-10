import { Config } from '@remotion/cli/config';

// This machine cannot reach GitHub, so Remotion cannot download its bundled
// Chrome. Point it at the system Chrome instead.
Config.setBrowserExecutable(
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
);
Config.setOverwriteOutput(true);
Config.setVideoImageFormat('jpeg');
Config.setConcurrency(4);
