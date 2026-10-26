import Link from "next/link";
import lp from "./optical-landing.module.css";

const lead = "私たちの体は、約30兆個もの細胞から成り立っている。これらの細胞に生じる変異は、ときにがんや神経変性疾患といった病気の引き金となり、私たちの健康を脅かす。こうした病気の原因を突き止め、がんや認知症などの克服につなげるため、研究者たちは顕微鏡を通して、細胞の内部で何が起きているのかを解き明かそうとしてきた。";

const body = [
  "しかし、生命現象を科学的に解明するには、顕微鏡で細胞を観察するだけでは十分ではない。大量の顕微鏡画像を比較し、そこに共通する特徴や変化を数値として捉えることが不可欠である。そのため、研究者たちは「ImageJ」や「Fiji」といった画像解析ソフトウェアを駆使し、画像から得られる情報を定量化することで、生命現象の解明に取り組んできた。",
  "これらのソフトウェアは高精度な画像解析を可能にする一方、操作が複雑であり、研究者でさえ習熟に苦労する。さらに、解析には多くの手作業が伴い、膨大な時間を要するだけでなく、たとえ同じデータであっても解析者や解析のタイミングによって異なった結論が得られることもある。これは、同じ条件で解析すれば同じ結果が得られるという、科学的な結論の信頼性を支える「再現性」に関わる重大な課題である。",
  "さらに生命科学においては、画像の特徴を数値化するだけでは説得力のある主張をすることができない。研究者は、得られた数値が統計学的に意味のあるものかを検証し、結果をグラフとして示す必要がある。そのため、研究者には生物学や実験手法に関する専門知識だけでなく、画像解析や統計解析に必要な数学的技能、さらには複数の複雑なソフトウェアを使いこなす技術まで求められる。こうした一連の作業は、研究者の貴重な時間を奪うとともに、人為的なミスや再現性の低下を招く要因にもなってきた。",
];

const answer = [
  "Cytellectという名称は、細胞を意味するギリシャ語に由来する「Cyte」と、知性を意味する英語の「Intellect」を組み合わせたものである。Cytellectはその名の通り顕微鏡画像をアップロードするだけで、機械学習モデルが蛍光マーカーで標識された細胞の核や特定の細胞内器官、タンパク質などを自動的に識別し、それぞれの面積や輝度を数値化する。これにより、従来は研究者が手作業と試行錯誤を重ねて行ってきた画像解析を自動化できる。",
  "さらに、Cytellectは画像解析だけでなく、得られたデータの統計解析から論文に使用できる水準のグラフ作成までを一貫して行うことができる。これまで画像解析ソフトウェアに加え、RやExcelなど複数のツールを使い分けなければならなかった一連の解析工程を、単一のワークスペースで完結させることを可能にするのである。",
];

const closing = "Cytellectは、これまで煩雑な手作業や研究者個人の知識・技能に依存してきた解析工程を自動化することで生命科学研究のあり方そのものを変える、次世代の研究者のためのアプリケーションである。";

/** The sentence the second paragraph turns on, set large beside the text. */
const reproducibility = "同じ条件で解析すれば同じ結果が得られるという、科学的な結論の信頼性を支える「再現性」に関わる重大な課題である。";

/** The owner's account of why Cytellect exists, for readers outside the life sciences. Linked quietly from the landing page's footer.
 *  Dark panels open and close the story in the landing page's colors; the text in between is unchanged. */
export function LandingStory() {
  const paragraph = (text: string) => <p key={text.slice(0, 12)}>{text}</p>;
  return <div className={lp.page}>
    <header className={lp.storyHero}>
      <Link href="/" className={lp.wordmark}>cytellect</Link>
      <h1 className={lp.storyTitle} aria-label="Cytellectが生まれた理由">Cytellectが<br />生まれた理由</h1>
    </header>
    <main id="main" className={lp.story}>
      <div className={lp.column}><div className={[lp.prose, lp.storyBody].join(" ")}>
        {paragraph(lead)}
        {paragraph(body[0])}
        {paragraph(body[1])}
        <p className={lp.storyQuote} aria-hidden="true">{reproducibility}</p>
        {paragraph(body[2])}
        <p className={lp.storyTurn}>こうした課題を解決するために開発したのが、「Cytellect」である。</p>
        {answer.map(paragraph)}
      </div></div>
      <section className={lp.storyEnd} aria-label="結び">
        <p className={lp.storyEndText}>{closing}</p>
        <div className={lp.storyActions}>
          <Link href="/demo" className={lp.primary}>デモを体験する <span aria-hidden="true">→</span></Link>
          <Link href="/">トップページへ</Link>
        </div>
      </section>
    </main>
  </div>;
}
