import { useSyncExternalStore } from 'react';
import { engine, type UI } from './Engine';

// Subscribe to engine state. The selector must return a value that only changes when it should
// (a field of the state, or a primitive), not a new object on every call.
export function useEngine<T>(sel: (s: UI) => T): T {
  return useSyncExternalStore(engine.subscribe, () => sel(engine.s));
}
export const useUI = () => useEngine(s => s);
export { engine };
