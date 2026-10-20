import type { ParseOptions } from './parse.ts';

/**
 * For filtering synthetic training data: only clean, modern, pu-style toki pona
 * passes. Everything the default mode merely warns about becomes an error,
 * except unofficial names, which translated stories need.
 */
export const STRICT: ParseOptions = {
  allowedCategories: ['core', 'common'],
  severityOverrides: {
    'uncommon-word': 'error',
    'deprecated-word': 'error',
    hyphenated: 'error',
    'stray-symbol': 'error',
    'bare-name': 'error',
    'pi-single-word': 'error',
    'pi-without-head': 'error',
    'li-after-mi-sina': 'error',
    'en-outside-subject': 'error',
    'name-phonotactics': 'error',
  },
};
