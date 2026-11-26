import Link from "next/link";
import { LandingClosingFilm } from "./LandingClosingFilm";
import lp from "./optical-landing.module.css";

/** The page's last invitation, on the footage it opened with: the demo first, the free Windows version next. */
export function LandingInvite() {
  return <section id="start" className={lp.invite} data-tone="dark" aria-labelledby="invite-title">
    <LandingClosingFilm />
    <div className={lp.inviteInner}>
      <h2 id="invite-title" className={lp.inviteTitle} aria-label="その未来を、あなたの研究から。"><span>その未来を、</span><span>あなたの研究から。</span></h2>
      <p className={lp.inviteLead}>画像を入れるところから、結論と考察、論文の図まで。</p>
      <div className={lp.inviteActions}>
        <Link data-lp-event="example" href="/demo" className={lp.primary}>デモを体験する <span aria-hidden="true">→</span></Link>
        <a data-lp-event="download_section" href="#download" className={lp.heroSecondary}>Windows版（無料） <span aria-hidden="true">↓</span></a>
      </div>
      <span className={lp.inviteMark} aria-hidden="true">cytellect</span>
    </div>
  </section>;
}
