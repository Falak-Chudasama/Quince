import { BridgeError } from '../../shared/errors.js';
import { executeType } from './type.js';

export function executeFillForm(refs: string[], values: string[]): void {
  if (refs.length !== values.length) {
    throw new BridgeError('invalid_argument', 'refs and values arrays must have identical length');
  }

  for (let i = 0; i < refs.length; i++) {
    const ref = refs[i]!;
    const val = values[i]!;
    executeType(ref, val, true, false);
  }
}
