import {expect, test} from "@playwright/test";

/** Synthetic transport fixture: masks must never be relabelled as another channel's result. */
test("a new target cannot display the previous target mask while running or after failure", async ({page}) => {
  const channels = ["c1", "c2"].map(channel_id => ({channel_id,label:channel_id,stain:null}));
  const field = {id:"field",workspace_id:"mask-identity",metadata:{},image_info:{shape:[32,32],channels}};
  const recipe = {id:"region-2d",version:"1.2.0",source:"stardist_nuclear",region_set_id:"nuclei",label:"核",defining_channel_id:"c1",nuclear_role_source:"user_selected_role"};
  const selection = {version:1,entries:[{id:"entry",field_id:"field",revision_id:"nuclei",target_revisions:{nuclei:"nuclei"},exclusion_reason:null}]};
  let started = false;
  let release: (() => void) | undefined;
  const pending = new Promise<void>(resolve => {release = resolve;});
  await page.route("**/v1/**", async route => {
    const path = new URL(route.request().url()).pathname;
    const headers = {"Access-Control-Allow-Origin":new URL(page.url()).origin,"Access-Control-Allow-Credentials":"true","Access-Control-Allow-Headers":"content-type,x-cytellect-request"};
    const json = (body: unknown, status = 200) => route.fulfill({status,headers,contentType:"application/json",body:JSON.stringify(body)});
    if (route.request().method() === "OPTIONS") return route.fulfill({status:204,headers});
    if (path === "/v1/session") return json({authenticated:true,retention_hours:24,demo:false});
    if (path === "/v1/workspaces/mask-identity") return json({id:"mask-identity",active_revision:"nuclei"});
    if (path.endsWith("/selection")) return json(selection);
    if (path.endsWith("/region-fields")) return json([field]);
    if (path.endsWith("/revisions")) return json([{id:"nuclei",state:"succeeded",created:1,config:{recipe,field_ids:["field"]}}]);
    if (path.endsWith("/jobs")) return json([]);
    if (path.endsWith("/region-measurements")) return json({revision_id:"nuclei",field_failures:[],exclusions:[],field_tables:{field:{rows:channels.map(channel => ({region_id:7,channel_id:channel.channel_id,area_px:64,mean:20,median:20,integrated:1280}))}}});
    if (path.endsWith("/region-masks")) return json({regions:[{id:7,points:[[4,4],[12,4],[12,12],[4,12]]}],metadata:{mask_revision_id:"mask-nuclei"}});
    if (path.endsWith("/preview")) return route.fulfill({headers,contentType:"image/png",body:Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aU1sAAAAASUVORK5CYII=","base64")});
    if (path.endsWith("/region-analyses")) {
      expect(route.request().postDataJSON().recipe).toMatchObject({source:"fiji_positive_regions",defining_channel_id:"c2"});
      started = true; await pending;
      return json({detail:"worker_process_failed"},500);
    }
    return json({detail:"unused_fixture_route"},404);
  });
  await page.goto("/workspace?id=mask-identity");
  const image = page.getByRole("img", {name:"視野 1の画像"});
  await expect(image.locator('[data-region="7"]')).toHaveCount(1);
  const overflow = () => image.evaluate(element => {
    const viewport = element.parentElement!;
    return Math.max(viewport.scrollWidth - viewport.clientWidth, viewport.scrollHeight - viewport.clientHeight);
  });
  await expect.poll(overflow).toBeLessThanOrEqual(2);
  await page.getByRole("button", {name:"統計",exact:true}).click();
  await expect(image).toBeHidden();
  await page.getByRole("button", {name:"画像解析",exact:true}).click();
  await expect(image).toBeVisible();
  await expect.poll(overflow).toBeLessThanOrEqual(2);
  // Region numbers do not blanket the image; the selected number is still identifiable.
  await expect(image.locator("text")).toHaveCount(0);
  await image.locator('[data-region="7"]').click();
  await expect(image.locator("text")).toHaveText("7");
  const method = page.getByRole("region",{name:"解析方法"});
  await method.getByRole("radio",{name:"陽性領域（GFP などの明るい領域）"}).check();
  await method.getByRole("combobox",{name:"チャンネル",exact:true}).selectOption("c2");
  await method.getByRole("button",{name:"代表視野で試す",exact:true}).click();
  await expect.poll(() => started).toBe(true);
  await expect(page.getByRole("radio",{name:"c2",exact:true})).toHaveAttribute("aria-checked","true");
  await expect(image.locator("[data-region]")).toHaveCount(0);
  release!();
  await expect(page.getByRole("button",{name:"視野 1 処理失敗",exact:true})).toBeVisible();
  await expect(image.locator("[data-region]")).toHaveCount(0);
});
