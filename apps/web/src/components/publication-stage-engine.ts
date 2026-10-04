/** Scroll-linked presentation of an actual 2D exported figure, not a 3D scientific rendering. */
export function mountPublication(element: HTMLDivElement) {
  let frame = 0;
  let visible = false;
  const paint = () => {
    frame = 0;
    if (!visible) return;
    const rect = element.getBoundingClientRect();
    const remaining = Math.max(0, Math.min(1, (rect.top - innerHeight * 0.16) / (innerHeight * 0.8)));
    element.style.setProperty("--paper-angle", `${remaining * 9}deg`);
    element.style.setProperty("--paper-turn", `${remaining * -2}deg`);
  };
  const schedule = () => { if (!frame && visible) frame = requestAnimationFrame(paint); };
  const observer = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; schedule(); });
  observer.observe(element);
  addEventListener("scroll", schedule, { passive: true });
  addEventListener("resize", schedule);
  return () => {
    observer.disconnect();
    removeEventListener("scroll", schedule);
    removeEventListener("resize", schedule);
    cancelAnimationFrame(frame);
    element.style.removeProperty("--paper-angle");
    element.style.removeProperty("--paper-turn");
  };
}
