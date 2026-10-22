import { existsSync } from "node:fs";
import path from "node:path";

/** Product footage shown in the LP hero. */
export type HeroMedia = {
  video: string;
  poster: string;
  /** A separate still for narrow screens; when set, phones show this still instead of the video. */
  mobilePoster?: string;
  mobileWidth?: number;
  mobileHeight?: number;
  width: number;
  height: number;
  alt: string;
};

const SHOWCASE: HeroMedia = {
  video: "/marketing/showcase-hero.mp4",
  poster: "/marketing/showcase-hero.webp",
  width: 1600,
  height: 1000,
  alt: "公開デモで、公開画像を解析するCytellectの画面",
};

const RECORDED_WORKSPACE: HeroMedia = {
  video: "/marketing/workspace-public.mp4",
  poster: "/marketing/workspace-public.png",
  mobilePoster: "/marketing/workspace-public-mobile.png",
  mobileWidth: 680,
  mobileHeight: 858,
  width: 1520,
  height: 744,
  alt: "公開蛍光画像を読み込んだCytellectの解析画面。3視野で検出した核の輪郭と、核ごとの測定値を確認できる。",
};

/**
 * The hero uses the showcase recording once both files are committed, and the
 * earlier workspace recording until then. The landing page is prerendered, so
 * this check runs at build time and the browser never requests a missing file.
 */
export function heroMedia(): HeroMedia {
  const present = (url: string) => existsSync(path.join(process.cwd(), "public", ...url.split("/").filter(Boolean)));
  return present(SHOWCASE.video) && present(SHOWCASE.poster) ? SHOWCASE : RECORDED_WORKSPACE;
}
