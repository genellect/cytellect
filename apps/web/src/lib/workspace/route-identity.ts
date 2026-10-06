export interface WorkspaceRouteIdentity {route: string; initial: string; generation: number; pendingUrl?: boolean}
export function routeIdentity(route: string): WorkspaceRouteIdentity {return {route, initial: route, generation: 0};}
export function navigateIdentity(current: WorkspaceRouteIdentity, route: string): WorkspaceRouteIdentity {
  return current.route === route ? current : {route, initial: route, generation: current.generation + 1};
}
/** Local creation changes the address without discarding the files being uploaded. */
export function promoteIdentity(current: WorkspaceRouteIdentity, route: string): WorkspaceRouteIdentity {
  return {...current, route, pendingUrl: current.route !== route};
}
/** Resolve the address seen by the router against the session identity.
 *  While a promotion waits for the URL to follow, the session is kept (no remount). */
export function resolveIdentity(current: WorkspaceRouteIdentity, route: string): WorkspaceRouteIdentity {
  if (current.route === route) return current.pendingUrl ? {...current, pendingUrl: false} : current;
  return current.pendingUrl ? current : navigateIdentity(current, route);
}
