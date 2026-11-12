import { BridgeError } from '../../shared/errors.js';
import { contentState } from '../state.js';

export function executeSelectOption(ref: string, optionTextOrValue: string): void {
  const el = contentState.getElement(ref);
  if (!el || !(el instanceof HTMLSelectElement)) {
    throw new BridgeError('not_found', `Select element with ref ${ref} not found`);
  }

  const query = optionTextOrValue.trim().toLowerCase();
  let found = false;

  for (let i = 0; i < el.options.length; i++) {
    const opt = el.options[i]!;
    if (opt.value.toLowerCase() === query || opt.text.trim().toLowerCase() === query) {
      el.selectedIndex = i;
      found = true;
      break;
    }
  }

  if (!found) {
    throw new BridgeError('option_not_found', `Option "${optionTextOrValue}" not found in select`);
  }

  el.dispatchEvent(new Event('input', { bubbles: true }));
  el.dispatchEvent(new Event('change', { bubbles: true }));
}
