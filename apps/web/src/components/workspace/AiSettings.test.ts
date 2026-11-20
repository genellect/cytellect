import {describe,expect,it} from "vitest";
import {aiStatusText} from "./AiSettings";

describe("AI availability guidance before sending",()=>{
  it("distinguishes configuration, sign-in, pending approval and connection failure",()=>{
    const base={checking:false,failed:false,status:{state:"available",source:"account"} as const,accountState:"allowed"};
    expect(aiStatusText(base)).toContain("設定済み");
    expect(aiStatusText({...base,accountState:"signed_out"})).toContain("ログイン");
    expect(aiStatusText({...base,accountState:"pending_approval"})).toContain("承認待ち");
    expect(aiStatusText({...base,accountState:"revoked"})).toContain("停止");
    expect(aiStatusText({...base,failed:true})).toContain("確認できません");
    expect(aiStatusText({...base,status:{state:"unconfigured",source:"none"}})).toContain("AI は未設定");
    expect(aiStatusText({...base,status:{state:"misconfigured",source:"operator"}})).toContain("サービス設定");
    expect(aiStatusText({...base,status:{state:"available",source:"operator"},accountState:"offline"})).toContain("設定済み");
    expect(aiStatusText({...base,compatibility:{state:"incompatible"}})).toContain("サービス更新");
    expect(aiStatusText({...base,compatibility:{state:"unauthorized"}})).not.toContain("ログイン");
    expect(aiStatusText({...base,compatibility:{state:"compatible"}})).toContain("確認済み");
    expect(aiStatusText({...base,checkingService:true})).toContain("接続と対応を確認中");
  });
});
