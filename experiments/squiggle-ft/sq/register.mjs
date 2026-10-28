// node --import ./sq/register.mjs …  (SQUIGGLE_DIR = a checkout of KealJones/squiggle)
import { register } from 'node:module';
import { pathToFileURL } from 'node:url';
import path from 'node:path';

const dir = process.env.SQUIGGLE_DIR;
if (!dir) throw new Error('Set SQUIGGLE_DIR to a checkout of KealJones/squiggle.');
const appSrc = pathToFileURL(path.resolve(dir, 'app', 'src')).href + '/';
register('./hooks.mjs', import.meta.url, { data: { appSrc } });
