import { useSyncExternalStore } from 'react';
import { engine, type UI } from './Engine';
import type { ToolsUI } from './tools';

// Subscribe to engine state. The selector must return a value that only changes when it should
// (a field of the state, or a primitive), not a new object on every call.
export function useEngine<T>(sel: (s: UI) => T): T {
  return useSyncExternalStore(engine.subscribe, () => sel(engine.s));
}
export const useUI = () => useEngine(s => s);
export { engine };

// Subscribe to the toolbar tools' state (engine/tools.ts), same rules as useEngine.
export function useTools<T>(sel: (s: ToolsUI) => T): T {
  return useSyncExternalStore(engine.tools.subscribe, () => sel(engine.tools.s));
}
export const tools = engine.tools;
