import DemoWorkspace from "@/components/DemoWorkspace";
import { LandingAnalytics } from "@/components/LandingAnalytics";

export default function DemoPage() {
  return <div data-cytellect-public-page="/demo" style={{ display: "contents" }}><LandingAnalytics page="/demo" /><DemoWorkspace /></div>;
}
