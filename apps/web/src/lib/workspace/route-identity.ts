export interface WorkspaceRouteIdentity {route: string; initial: string; generation: number}
export function routeIdentity(route: string): WorkspaceRouteIdentity {return {route, initial: route, generation: 0};}
export function navigateIdentity(current: WorkspaceRouteIdentity, route: string): WorkspaceRouteIdentity {
  return current.route === route ? current : {route, initial: route, generation: current.generation + 1};
}
/** Local creation changes the address without discarding the files being uploaded. */
export function promoteIdentity(current: WorkspaceRouteIdentity, route: string): WorkspaceRouteIdentity {
  return {...current, route};
}
