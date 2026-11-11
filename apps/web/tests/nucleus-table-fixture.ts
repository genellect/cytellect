/** A synthetic nucleus table (nucleus-table/1.0.0) for browser tests whose API is a fixture. Adopted nuclei open on
 * their nucleus table (MV-07), so a fixture that serves adopted nuclei also serves this table. Values are synthetic. */
export function nucleusTableFixture({fieldId,revision,channels,nuclei,areaPx=144,mean=20}:{
  fieldId:string;revision:string;channels:Array<{channel_id:string;label?:string;stain?:string|null}>;nuclei:number[];areaPx?:number;mean?:number|((channel:string)=>number);
}){
  const value=(channel:string)=>typeof mean==="function"?mean(channel):mean;
  return {protocol:"nucleus-table/1.0.0",field_id:fieldId,nuclear_revision_id:revision,nuclear_mask_revision_id:revision,nuclear_mask_sha256:"a".repeat(64),nuclear_adopted:true,
    measurement_protocol_version:"4.0.0",nuclear_channel_id:channels[0]?.channel_id??null,nucleolar_source:null,calibration:null,field_excluded:false,
    channels:channels.map(channel=>({channel_id:channel.channel_id,label:channel.label??channel.channel_id,stain:channel.stain??null,role:channel===channels[0]?"nuclear_stain":"measure"})),
    backgrounds:[],rows:nuclei.map(nucleus_id=>({nucleus_id,excluded:false,exclusion_scope:null,exclusion_reason:null,touches_border:false,nucleus_area_px:areaPx,nucleus_area_um2:null,
      area_missing_reason:"calibration_unknown",channels:channels.map((channel,index)=>({channel_id:channel.channel_id,role:index===0?"nuclear_stain":"measure",mean:value(channel.channel_id),
        integrated:value(channel.channel_id)*areaPx,mean_corrected:null,integrated_corrected:null,intensity_missing_reason:null,correction_missing_reason:"background_not_established",
        storage_limit_fraction:0,acquisition_saturation_fraction:0,acquisition_saturation_missing_reason:null})),
      nucleoli:{status:"missing",reason:"nucleolar_revision_not_selected",count:null,union_area_px:null,union_area_um2:null,union_area_um2_missing_reason:null,area_fraction:null,
        largest_object_area_px:null,largest_object_fraction:null,eccentricity:null,eccentricity_missing_reason:null,excluded_objects:0}}))};
}
