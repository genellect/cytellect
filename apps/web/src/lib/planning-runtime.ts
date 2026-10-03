// Public memos stay compatible with the immutable package currently advertised.
// Advance this public value only alongside an accepted matching release.
export const PUBLISHED_PLANNING_VERSION="2.0.0" as const;
export const LATEST_PLANNING_VERSION="2.1.0" as const;
export function planningVersion(local:boolean,apiConfigured:boolean){
 return local||apiConfigured?LATEST_PLANNING_VERSION:PUBLISHED_PLANNING_VERSION;
}
