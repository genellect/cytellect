import type {Metadata} from "next";
import ReviewWorkspace from "@/components/workspace/review/ConnectedWorkspace";

export const metadata: Metadata = {title: "ワークスペース操作確認 | Cytellect", robots: {index: false, follow: false}};
export default function Page() { return <ReviewWorkspace/>; }
