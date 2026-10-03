export interface paths {
    "/v1/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_v1_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/invitations/redeem": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Redeem */
        post: operations["redeem_v1_invitations_redeem_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/session": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Session */
        get: operations["session_v1_session_get"];
        put?: never;
        post?: never;
        /** Logout */
        delete: operations["logout_v1_session_delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Workspaces */
        get: operations["list_workspaces_v1_workspaces_get"];
        put?: never;
        /** New Workspace */
        post: operations["new_workspace_v1_workspaces_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{wid}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Workspace */
        get: operations["get_workspace_v1_workspaces__wid__get"];
        put?: never;
        post?: never;
        /** Delete Workspace */
        delete: operations["delete_workspace_v1_workspaces__wid__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{wid}/touch": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Keep Alive */
        post: operations["keep_alive_v1_workspaces__wid__touch_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{wid}/fields": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Fields */
        get: operations["list_fields_v1_workspaces__wid__fields_get"];
        put?: never;
        /** Upload Field */
        post: operations["upload_field_v1_workspaces__wid__fields_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{wid}/synthetic": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Synthetic */
        post: operations["synthetic_v1_workspaces__wid__synthetic_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/fields/{fid}/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Preview */
        get: operations["preview_v1_fields__fid__preview_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{wid}/analyses": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start Analysis */
        post: operations["start_analysis_v1_workspaces__wid__analyses_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{wid}/revisions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Revisions */
        get: operations["list_revisions_v1_workspaces__wid__revisions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/revisions/{rid}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Revision */
        get: operations["get_revision_v1_revisions__rid__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/revisions/{rid}/measurements": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Measurements */
        get: operations["measurements_v1_revisions__rid__measurements_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/revisions/{rid}/fields/{fid}/masks": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Masks */
        get: operations["get_masks_v1_revisions__rid__fields__fid__masks_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/revisions/{rid}/edits": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Edit */
        post: operations["edit_v1_revisions__rid__edits_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{wid}/current": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Choose Revision */
        post: operations["choose_revision_v1_workspaces__wid__current_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/revisions/{rid}/review": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Review */
        post: operations["review_v1_revisions__rid__review_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/revisions/{rid}/statistics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Statistics */
        post: operations["statistics_v1_revisions__rid__statistics_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/revisions/{rid}/export": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Export */
        post: operations["export_v1_revisions__rid__export_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/revisions/{rid}/reconfigure": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reconfigure */
        post: operations["reconfigure_v1_revisions__rid__reconfigure_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/revisions/{rid}/resegment": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Resegment */
        post: operations["resegment_v1_revisions__rid__resegment_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/jobs/{jid}/retry": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Retry */
        post: operations["retry_v1_jobs__jid__retry_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{wid}/tables": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Tables */
        get: operations["list_tables_v1_workspaces__wid__tables_get"];
        put?: never;
        /** Import Table */
        post: operations["import_table_v1_workspaces__wid__tables_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/tables/{tid}/statistics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Table Statistics */
        post: operations["table_statistics_v1_tables__tid__statistics_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{wid}/jobs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Jobs */
        get: operations["list_jobs_v1_workspaces__wid__jobs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/jobs/{jid}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Job */
        get: operations["get_job_v1_jobs__jid__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/jobs/{jid}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancel */
        post: operations["cancel_v1_jobs__jid__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/jobs/{jid}/result": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Job Result */
        get: operations["job_result_v1_jobs__jid__result_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/jobs/{jid}/files/{name}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Job File */
        get: operations["job_file_v1_jobs__jid__files__name__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{wid}/region-fields": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Region Fields */
        get: operations["list_region_fields_v1_workspaces__wid__region_fields_get"];
        put?: never;
        /** Upload Region Field */
        post: operations["upload_region_field_v1_workspaces__wid__region_fields_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/region-fields/{fid}/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Preview */
        get: operations["preview_v1_region_fields__fid__preview_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{wid}/region-analyses": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start */
        post: operations["start_v1_workspaces__wid__region_analyses_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/revisions/{rid}/region-measurements": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Measurements */
        get: operations["measurements_v1_revisions__rid__region_measurements_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/revisions/{rid}/region-masks": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Masks */
        get: operations["masks_v1_revisions__rid__region_masks_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/revisions/{rid}/region-edits": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Edit */
        post: operations["edit_v1_revisions__rid__region_edits_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/revisions/{rid}/region-reconfigure": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Reconfigure */
        post: operations["reconfigure_v1_revisions__rid__region_reconfigure_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/revisions/{rid}/region-metadata": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Metadata */
        post: operations["metadata_v1_revisions__rid__region_metadata_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/revisions/{rid}/descriptive": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Descriptive */
        post: operations["descriptive_v1_revisions__rid__descriptive_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/revisions/{rid}/region-comparisons": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Compare */
        post: operations["compare_v1_revisions__rid__region_comparisons_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/jobs/{jid}/region-comparison": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Result */
        get: operations["result_v1_jobs__jid__region_comparison_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/plans/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preview Plan */
        post: operations["preview_plan_v1_plans_preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** AcquisitionReview */
        AcquisitionReview: {
            /**
             * Confirmed
             * @constant
             */
            confirmed: true;
            /**
             * Basis
             * @enum {string}
             */
            basis: "same-settings" | "calibrated-area";
            /** Field Batches */
            field_batches?: {
                [key: string]: string;
            };
            /**
             * Spatial Sampling Confirmed
             * @default false
             */
            spatial_sampling_confirmed: boolean;
        };
        /** AdoptedPlan */
        AdoptedPlan: {
            input: components["schemas"]["PlanInput"];
            decision: components["schemas"]["PlanDecision"];
            /** Sha256 */
            sha256: string;
            /**
             * Adoption Version
             * @default 1.0.0
             * @constant
             */
            adoption_version: "1.0.0";
            /**
             * Selected Candidate Id
             * @enum {string}
             */
            selected_candidate_id: "regions-manual" | "regions-imported" | "regions-nuclei" | "legacy-gfp-nuclear" | "legacy-ncl";
            /** Accepted At */
            accepted_at: number;
            /**
             * Scope
             * @default planning-intent-only
             * @constant
             */
            scope: "planning-intent-only";
        };
        /** AnalysisRequest */
        AnalysisRequest: {
            /** Field Ids */
            field_ids?: string[] | null;
            /** Reuse Revision */
            reuse_revision?: string | null;
            recipe?: components["schemas"]["Recipe"];
            /** Backgrounds */
            backgrounds?: {
                [key: string]: components["schemas"]["Background"];
            };
            /** Exclusions */
            exclusions?: components["schemas"]["Exclusion"][];
            plan_resolution?: components["schemas"]["PlanResolution"] | null;
        };
        /** AreaBackgroundProvenance */
        AreaBackgroundProvenance: {
            /**
             * Status
             * @default not_measured
             * @constant
             */
            status: "not_measured";
            /**
             * Reason
             * @default not_required_for_area
             * @constant
             */
            reason: "not_required_for_area";
        };
        /** Background */
        Background: {
            /** Polygon */
            polygon: [
                number,
                number
            ][];
            /**
             * Confirmed
             * @default false
             */
            confirmed: boolean;
        };
        /** Body_import_table_v1_workspaces__wid__tables_post */
        Body_import_table_v1_workspaces__wid__tables_post: {
            /** File */
            file: string;
        };
        /** Body_upload_field_v1_workspaces__wid__fields_post */
        Body_upload_field_v1_workspaces__wid__fields_post: {
            /** Metadata */
            metadata: string;
            /**
             * Legacy
             * @default false
             */
            legacy: boolean;
            /** Dapi */
            dapi?: string | null;
            /** Ncl */
            ncl?: string | null;
            /** Gfp */
            gfp?: string | null;
            /** Ome */
            ome?: string | null;
            /**
             * Mapping
             * @default [0,1,2]
             */
            mapping: string;
            /**
             * Channel Roles
             * @default ["dapi","ncl","gfp"]
             */
            channel_roles: string;
        };
        /** Body_upload_region_field_v1_workspaces__wid__region_fields_post */
        Body_upload_region_field_v1_workspaces__wid__region_fields_post: {
            /** Specification */
            specification: string;
            /** Ch0 */
            ch0: string;
            /** Ch1 */
            ch1?: string | null;
            /** Ch2 */
            ch2?: string | null;
            /** Labels */
            labels?: string | null;
        };
        /** Calibration2D */
        Calibration2D: {
            /** Pixel Size X Um */
            pixel_size_x_um: number;
            /** Pixel Size Y Um */
            pixel_size_y_um: number;
            /**
             * Confirmed
             * @constant
             */
            confirmed: true;
        };
        /** ChannelProvenance */
        ChannelProvenance: {
            channel: components["schemas"]["ChannelSpec"];
            /**
             * Dtype
             * @enum {string}
             */
            dtype: "uint8" | "uint16";
            /** Pixel Sha256 */
            pixel_sha256: string;
            /** Background Mask Sha256 */
            background_mask_sha256: string;
            /** Background Revision Id */
            background_revision_id: string;
            /** Background Pixel Count */
            background_pixel_count: number;
            /** Background Median */
            background_median: number;
            /** Storage Maximum */
            storage_maximum: number;
        };
        /** ChannelProvenanceV2 */
        ChannelProvenanceV2: {
            channel: components["schemas"]["ChannelSpec"];
            /**
             * Dtype
             * @enum {string}
             */
            dtype: "uint8" | "uint16";
            /** Pixel Sha256 */
            pixel_sha256: string;
            /**
             * Storage Maximum
             * @enum {integer}
             */
            storage_maximum: 255 | 65535;
            background: components["schemas"]["AreaBackgroundProvenance"];
        };
        /** ChannelSpec */
        ChannelSpec: {
            /** Channel Id */
            channel_id: string;
            /** Label */
            label: string;
            /** Stain */
            stain?: string | null;
            /**
             * Identity Confirmed
             * @constant
             */
            identity_confirmed: true;
            /** Acquisition Saturation Value */
            acquisition_saturation_value?: number | null;
            /**
             * Acquisition Saturation Confirmed
             * @default false
             */
            acquisition_saturation_confirmed: boolean;
        };
        /** ComparisonDesign */
        ComparisonDesign: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "independent" | "paired";
            /**
             * Confirmed
             * @constant
             */
            confirmed: true;
            /** Unit Definition */
            unit_definition: string;
            /** Pairing Basis */
            pairing_basis?: string | null;
        };
        /** ComparisonFamily */
        ComparisonFamily: {
            /** Family Id */
            family_id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "control" | "planned";
            /** Control */
            control?: string | null;
            /** Contrasts */
            contrasts: string[][];
        };
        /** ContourView */
        ContourView: {
            /** Id */
            id: number;
            /** Points */
            points: [
                number,
                number
            ][];
        };
        /** DescriptiveFigurePolicy */
        DescriptiveFigurePolicy: {
            /**
             * Version
             * @constant
             */
            version: "2.0.0";
            /**
             * Layout
             * @constant
             */
            layout: "field-pages";
        };
        /** DescriptivePlot */
        DescriptivePlot: {
            /**
             * Preset
             * @default nature-single
             * @enum {string}
             */
            preset: "custom" | "nature-single" | "nature-double";
            /**
             * Kind
             * @default distribution
             * @constant
             */
            kind: "distribution";
            /**
             * Language
             * @default en
             * @enum {string}
             */
            language: "en" | "ja";
            /**
             * Width Inches
             * @default 7
             */
            width_inches: number;
            /**
             * Height Inches
             * @default 3
             */
            height_inches: number;
            /**
             * Font Size
             * @default 7
             */
            font_size: number;
            /**
             * X Label
             * @default
             */
            x_label: string;
            /**
             * Y Label
             * @default
             */
            y_label: string;
            /** Group Order */
            group_order?: string[];
        };
        /** DescriptiveRequest */
        DescriptiveRequest: {
            /**
             * Mode
             * @constant
             */
            mode: "descriptive";
            /** Selection */
            selection: components["schemas"]["LegacySelection"] | components["schemas"]["RegionSelection"] | components["schemas"]["NumericalSelection"];
            /**
             * Group By
             * @default field
             * @constant
             */
            group_by: "field";
            plot?: components["schemas"]["DescriptivePlot"];
        };
        /** Exclusion */
        Exclusion: {
            /** Field Id */
            field_id: string;
            /** Nucleus Id */
            nucleus_id?: number | null;
            /** Reason */
            reason: string;
        };
        /** FieldMetadata */
        FieldMetadata: {
            /** Condition */
            condition: string;
            /** Experimental Unit */
            experimental_unit: string;
            /** Sample */
            sample: string;
            /** Acquisition Date */
            acquisition_date: string;
            /** Pair */
            pair?: string | null;
            /** Repeat Length */
            repeat_length?: number | null;
            /** Pixel Size Um */
            pixel_size_um?: number | null;
        };
        /** FieldView */
        FieldView: {
            /** Id */
            id: string;
            /** Workspace Id */
            workspace_id: string;
            metadata: components["schemas"]["FieldMetadata"];
            image_info: components["schemas"]["ImageInfo"];
            /** Synthetic */
            synthetic: boolean;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** ImageInfo */
        ImageInfo: {
            /** Shape */
            shape: number[];
            /** Dtype */
            dtype: string;
            /** Legacy */
            legacy: boolean;
            /** Inputs */
            inputs: {
                [key: string]: {
                    [key: string]: unknown;
                };
            };
            /** Axes */
            axes: string;
            /** Channel Mapping */
            channel_mapping: (string | number)[];
            /** Channel Roles */
            channel_roles?: ("dapi" | "ncl" | "gfp")[];
            /** Channel Dtypes */
            channel_dtypes?: {
                [key: string]: string;
            };
        };
        /** InviteInput */
        InviteInput: {
            /** Token */
            token: string;
        };
        /** JobView */
        JobView: {
            /** Id */
            id: string;
            /** Revision Id */
            revision_id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "analysis" | "statistics" | "table-statistics" | "export";
            /**
             * State
             * @enum {string}
             */
            state: "queued" | "running" | "succeeded" | "failed" | "cancelled";
            /** Created */
            created: number;
            /** Error */
            error: string | null;
            /** Attempts */
            attempts: number;
            /** Analysis Mode */
            analysis_mode?: ("experimental-unit" | "exploratory" | "descriptive" | "region-experimental-unit") | null;
        };
        /** LegacyParameters */
        LegacyParameters: {
            /**
             * Version
             * @default 1.0.0
             * @constant
             */
            version: "1.0.0";
            /**
             * Target Long Dimension Px
             * @default 320
             */
            target_long_dimension_px: number;
            /**
             * Nucleus Area Min Scaled Px
             * @default 300
             */
            nucleus_area_min_scaled_px: number;
            /**
             * Nucleus Area Max Scaled Px
             * @default 6000
             */
            nucleus_area_max_scaled_px: number;
            /**
             * Dapi Snr Min
             * @default 2
             */
            dapi_snr_min: number;
            /**
             * Saturation Fraction Max
             * @default 0.25
             */
            saturation_fraction_max: number;
            /**
             * Apply Quality Exclusions
             * @default true
             */
            apply_quality_exclusions: boolean;
            /**
             * Gfp Mode
             * @default otsu-qc-batch
             * @enum {string}
             */
            gfp_mode: "otsu-qc-batch" | "recipe";
        };
        /** LegacySelection */
        LegacySelection: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            source: "legacy-cell";
            /**
             * Metric
             * @enum {string}
             */
            metric: "ncl_nucleus_mean" | "ncl_nucleus_median" | "ncl_nucleus_integrated" | "ncl_nucleus_mean_corrected" | "ncl_nucleus_median_corrected" | "ncl_nucleus_integrated_corrected" | "ncl_nucleoli_mean" | "ncl_nucleoli_median" | "ncl_nucleoli_integrated" | "ncl_nucleoli_mean_corrected" | "ncl_nucleoli_median_corrected" | "ncl_nucleoli_integrated_corrected" | "ncl_nucleoplasm_mean" | "ncl_nucleoplasm_median" | "ncl_nucleoplasm_integrated" | "ncl_nucleoplasm_mean_corrected" | "ncl_nucleoplasm_median_corrected" | "ncl_nucleoplasm_integrated_corrected" | "gfp_mean" | "gfp_median" | "gfp_integrated" | "gfp_mean_corrected" | "gfp_median_corrected" | "gfp_integrated_corrected" | "nucleus_area_px" | "nucleus_area_um2" | "nucleolar_area_px" | "nucleolar_area_um2" | "nucleoplasm_area_px" | "nucleoplasm_area_um2" | "nucleolar_count" | "nucleolar_area_fraction" | "ncl_nucleoplasm_over_nucleoli" | "ncl_log2_nucleoplasm_over_nucleoli" | "ncl_legacy_release";
        };
        /** MaskEdit */
        MaskEdit: {
            /** Field Id */
            field_id: string;
            /**
             * Layer
             * @enum {string}
             */
            layer: "nuclei" | "nucleoli" | "manual";
            /**
             * Operation
             * @enum {string}
             */
            operation: "add" | "replace" | "delete" | "merge" | "split";
            /** Ids */
            ids?: number[];
            /** Polygon */
            polygon?: [
                number,
                number
            ][];
            /** Parent Id */
            parent_id?: number | null;
        };
        /** MasksView */
        MasksView: {
            /** Nuclei */
            nuclei: components["schemas"]["ContourView"][];
            /** Nucleoli */
            nucleoli: components["schemas"]["ContourView"][];
            /** Manual */
            manual: components["schemas"]["ContourView"][];
        };
        /**
         * NuclearDetectorSpec
         * @description Allowlisted, offline nucleus model; never an arbitrary image classifier.
         */
        NuclearDetectorSpec: {
            /**
             * Engine
             * @default fiji-stardist-2d
             * @constant
             */
            engine: "fiji-stardist-2d";
            /**
             * Model
             * @default Versatile (fluorescent nuclei)
             * @constant
             */
            model: "Versatile (fluorescent nuclei)";
            /**
             * Probability
             * @default 0.5
             */
            probability: number;
            /**
             * Nms
             * @default 0.3
             */
            nms: number;
            /**
             * Percentile Low
             * @default 1
             */
            percentile_low: number;
            /**
             * Percentile High
             * @default 99.8
             */
            percentile_high: number;
        };
        /** NumericalSelection */
        NumericalSelection: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            source: "numerical";
            /**
             * Metric
             * @default value
             * @constant
             */
            metric: "value";
        };
        /** PagedDescriptiveRequest */
        PagedDescriptiveRequest: {
            /**
             * Mode
             * @constant
             */
            mode: "descriptive";
            /** Selection */
            selection: components["schemas"]["LegacySelection"] | components["schemas"]["RegionSelection"] | components["schemas"]["NumericalSelection"];
            /**
             * Group By
             * @default field
             * @constant
             */
            group_by: "field";
            plot?: components["schemas"]["DescriptivePlot"];
            figure_policy: components["schemas"]["DescriptiveFigurePolicy"];
        };
        /** PlanAnswers */
        PlanAnswers: {
            /**
             * Measurement
             * @default unknown
             * @enum {string}
             */
            measurement: "unknown" | "area" | "mean" | "integrated" | "ncl-ratio";
            /**
             * Region
             * @default unknown
             * @enum {string}
             */
            region: "unknown" | "nucleus" | "nucleolus" | "nucleoplasm" | "custom";
            /**
             * Definition
             * @default unknown
             * @enum {string}
             */
            definition: "unknown" | "manual" | "imported" | "nuclear-stain" | "ncl-enrichment";
            /**
             * Signal
             * @default unknown
             * @enum {string}
             */
            signal: "unknown" | "ncl" | "gfp" | "other";
            /**
             * Input
             * @default unknown
             * @enum {string}
             */
            input: "unknown" | "grayscale-2d" | "rgb" | "zt";
            /**
             * Nuclear Stain
             * @default unknown
             * @enum {string}
             */
            nuclear_stain: "unknown" | "yes" | "no";
            /**
             * Background
             * @default unknown
             * @enum {string}
             */
            background: "unknown" | "yes" | "no";
            /**
             * Acquisition
             * @default unknown
             * @enum {string}
             */
            acquisition: "unknown" | "matched" | "different";
            /**
             * Comparison
             * @default unknown
             * @enum {string}
             */
            comparison: "unknown" | "descriptive" | "independent" | "paired";
            /**
             * Allocation
             * @default unknown
             * @enum {string}
             */
            allocation: "unknown" | "biological" | "fields";
            /**
             * Gating
             * @default none
             * @enum {string}
             */
            gating: "none" | "negative-control" | "exploratory";
        };
        /** PlanCandidate */
        PlanCandidate: {
            /**
             * Id
             * @enum {string}
             */
            id: "regions-manual" | "regions-imported" | "regions-nuclei" | "legacy-gfp-nuclear" | "legacy-ncl";
            /** Label */
            label: string;
            /**
             * Workflow
             * @enum {string}
             */
            workflow: "regions" | "nuclear";
            /**
             * Recipe Id
             * @enum {string}
             */
            recipe_id: "region-2d" | "ncl-native-2d" | "gfp-nuclear-2d";
            /**
             * Recipe Version
             * @enum {string}
             */
            recipe_version: "1.0.0" | "1.1.0";
            /** Source */
            source: ("manual" | "imported" | "stardist_nuclear") | null;
            /**
             * Selection Source
             * @enum {string}
             */
            selection_source: "region" | "legacy-cell";
            /** Allowed Metrics */
            allowed_metrics: ("area_px" | "area_um2" | "mean" | "mean_corrected" | "integrated" | "integrated_corrected" | "gfp_mean" | "gfp_mean_corrected" | "gfp_integrated" | "gfp_integrated_corrected" | "ncl_nucleus_mean" | "ncl_nucleus_mean_corrected" | "ncl_nucleus_integrated" | "ncl_nucleus_integrated_corrected" | "ncl_nucleoli_mean" | "ncl_nucleoli_mean_corrected" | "ncl_nucleoli_integrated" | "ncl_nucleoli_integrated_corrected" | "ncl_nucleoplasm_mean" | "ncl_nucleoplasm_mean_corrected" | "ncl_nucleoplasm_integrated" | "ncl_nucleoplasm_integrated_corrected" | "nucleus_area_px" | "nucleus_area_um2" | "nucleolar_area_px" | "nucleolar_area_um2" | "nucleoplasm_area_px" | "nucleoplasm_area_um2" | "ncl_nucleoplasm_over_nucleoli" | "ncl_log2_nucleoplasm_over_nucleoli")[];
            /** Required Channel Roles */
            required_channel_roles: ("image" | "measurement" | "nuclear-stain" | "ncl" | "gfp")[];
            /** Actual Review Required */
            actual_review_required: ("native-input" | "channel-mapping" | "nuclear-stain" | "background-rois" | "region-definition" | "metric-selection" | "mask-quality" | "gfp-gate" | "calibration-for-physical-area")[];
            measurement?: components["schemas"]["RegionMeasurementPolicy"] | null;
        };
        /** PlanDecision */
        PlanDecision: {
            /**
             * Version
             * @default 2.0.0
             * @enum {string}
             */
            version: "2.0.0" | "2.1.0";
            /**
             * Status
             * @default planning-only-not-adopted
             * @constant
             */
            status: "planning-only-not-adopted";
            /** Candidates */
            candidates: components["schemas"]["PlanCandidate"][];
            /**
             * Comparison Intent
             * @enum {string}
             */
            comparison_intent: "undetermined" | "descriptive" | "independent-candidate" | "paired-candidate";
            /**
             * Descriptive Allowed
             * @default true
             * @constant
             */
            descriptive_allowed: true;
            /** Questions */
            questions: components["schemas"]["PlanFinding"][];
            /** Decisions */
            decisions: components["schemas"]["PlanFinding"][];
            /** Limits */
            limits: components["schemas"]["PlanFinding"][];
            /** References */
            references: components["schemas"]["PlanReference"][];
        };
        /** PlanFinding */
        PlanFinding: {
            /** Id */
            id: string;
            /** Title */
            title: string;
            /** Detail */
            detail: string;
            /**
             * Reference
             * @enum {string}
             */
            reference: "senft-2023" | "kodiha-2011" | "waters-2009" | "lazic-2018" | "lord-2020" | "schmied-2024";
        };
        /** PlanInput */
        PlanInput: {
            /**
             * Format
             * @default cytellect-analysis-plan
             * @constant
             */
            format: "cytellect-analysis-plan";
            /**
             * Version
             * @enum {string}
             */
            version: "2.0.0" | "2.1.0";
            answers: components["schemas"]["PlanAnswers"];
        };
        /** PlanReference */
        PlanReference: {
            /**
             * Id
             * @enum {string}
             */
            id: "senft-2023" | "kodiha-2011" | "waters-2009" | "lazic-2018" | "lord-2020" | "schmied-2024";
            /** Label */
            label: string;
            /** Url */
            url: string;
        };
        /** PlanResolution */
        PlanResolution: {
            /**
             * Version
             * @default 1.0.0
             * @enum {string}
             */
            version: "1.0.0" | "1.1.0";
            /** Plan Sha256 */
            plan_sha256: string;
            /**
             * Candidate Id
             * @enum {string}
             */
            candidate_id: "regions-manual" | "regions-imported" | "regions-nuclei" | "legacy-gfp-nuclear" | "legacy-ncl";
            /** Metric */
            metric: string;
            /** Channel Id */
            channel_id?: string | null;
            /**
             * Changes Acknowledged
             * @default false
             */
            changes_acknowledged: boolean;
            measurement?: components["schemas"]["RegionMeasurementPolicy"] | null;
        };
        /** PlanSnapshot */
        PlanSnapshot: {
            input: components["schemas"]["PlanInput"];
            decision: components["schemas"]["PlanDecision"];
            /** Sha256 */
            sha256: string;
        };
        /** PlotSpec */
        PlotSpec: {
            /**
             * Preset
             * @default nature-single
             * @enum {string}
             */
            preset: "custom" | "nature-single" | "nature-double";
            /**
             * Kind
             * @default distribution
             * @enum {string}
             */
            kind: "distribution" | "scatter" | "paired";
            /**
             * Language
             * @default en
             * @enum {string}
             */
            language: "en" | "ja";
            /**
             * Width Inches
             * @default 7
             */
            width_inches: number;
            /**
             * Height Inches
             * @default 3
             */
            height_inches: number;
            /**
             * Font Size
             * @default 7
             */
            font_size: number;
            /**
             * X Label
             * @default
             */
            x_label: string;
            /**
             * Y Label
             * @default
             */
            y_label: string;
            /** Group Order */
            group_order?: string[];
        };
        /** Recipe */
        Recipe: {
            /**
             * Id
             * @default ncl-native-2d
             * @enum {string}
             */
            id: "ncl-native-2d" | "ncl-legacy-rgb" | "gfp-nuclear-2d";
            /**
             * Version
             * @default 1.0.0
             * @constant
             */
            version: "1.0.0";
            /**
             * Probability
             * @default 0.5
             */
            probability: number;
            /**
             * Nms
             * @default 0.3
             */
            nms: number;
            /**
             * Percentile Low
             * @default 1
             */
            percentile_low: number;
            /**
             * Percentile High
             * @default 99.8
             */
            percentile_high: number;
            /**
             * Nucleolar Method
             * @default ncl-otsu
             * @enum {string}
             */
            nucleolar_method: "ncl-otsu" | "dapi-low";
            /**
             * Smoothing Sigma Px
             * @default 0
             */
            smoothing_sigma_px: number;
            /**
             * Minimum Area Px
             * @default 1
             */
            minimum_area_px: number;
            /**
             * Split Touching
             * @default false
             */
            split_touching: boolean;
            /**
             * Dapi Low Percentile
             * @default 10
             */
            dapi_low_percentile: number;
            /**
             * Gfp Gate
             * @default none
             * @enum {string}
             */
            gfp_gate: "none" | "manual" | "otsu-batch" | "negative-control";
            /** Gfp Threshold */
            gfp_threshold?: number | null;
            /** Gfp Negative Control Fields */
            gfp_negative_control_fields?: string[];
            /**
             * Gfp Negative Control Confirmed
             * @default false
             */
            gfp_negative_control_confirmed: boolean;
            /** Gfp Maximum */
            gfp_maximum?: number | null;
            /** Native Signal Qc Minimum Ratio */
            native_signal_qc_minimum_ratio?: number | null;
            /**
             * Seed
             * @default 0
             */
            seed: number;
            legacy?: components["schemas"]["LegacyParameters"];
        };
        /** RegionAnalysisRequest */
        RegionAnalysisRequest: {
            /** Field Ids */
            field_ids?: string[] | null;
            /** Reuse Revision */
            reuse_revision?: string | null;
            plan_resolution?: components["schemas"]["PlanResolution"] | null;
            measurement?: components["schemas"]["RegionMeasurementPolicy"] | null;
            /** Recipe */
            recipe: components["schemas"]["RegionRecipe"] | components["schemas"]["RegionNuclearRecipe"];
            /** Backgrounds */
            backgrounds?: {
                [key: string]: {
                    [key: string]: components["schemas"]["RegionBackground"];
                };
            };
            /** Exclusions */
            exclusions?: components["schemas"]["RegionExclusion"][];
        };
        /** RegionBackground */
        RegionBackground: {
            /** Polygon */
            polygon: number[][];
            /**
             * Confirmed
             * @constant
             */
            confirmed: true;
        };
        /** RegionComparisonPlot */
        RegionComparisonPlot: {
            /**
             * Preset
             * @default nature-single
             * @enum {string}
             */
            preset: "custom" | "nature-single" | "nature-double";
            /**
             * Kind
             * @default distribution
             * @enum {string}
             */
            kind: "distribution" | "paired";
            /**
             * Language
             * @default en
             * @enum {string}
             */
            language: "en" | "ja";
            /**
             * Width Inches
             * @default 7
             */
            width_inches: number;
            /**
             * Height Inches
             * @default 3
             */
            height_inches: number;
            /**
             * Font Size
             * @default 7
             */
            font_size: number;
            /**
             * X Label
             * @default
             */
            x_label: string;
            /**
             * Y Label
             * @default
             */
            y_label: string;
            /** Group Order */
            group_order?: string[];
        };
        /** RegionComparisonRequest */
        RegionComparisonRequest: {
            /**
             * Mode
             * @constant
             */
            mode: "region-experimental-unit";
            /**
             * Version
             * @default 1.0.0
             * @constant
             */
            version: "1.0.0";
            selection: components["schemas"]["RegionSelection"];
            design: components["schemas"]["ComparisonDesign"];
            /** Conditions */
            conditions: string[];
            comparison_family: components["schemas"]["ComparisonFamily"];
            acquisition_review: components["schemas"]["AcquisitionReview"];
            /**
             * Missingness Confirmed
             * @constant
             */
            missingness_confirmed: true;
            /**
             * Aggregation
             * @default field-median_sample-mean_unit-mean-v1
             * @constant
             */
            aggregation: "field-median_sample-mean_unit-mean-v1";
            /**
             * Missingness Policy
             * @default available-observations_require-unexcluded-units-v1
             * @constant
             */
            missingness_policy: "available-observations_require-unexcluded-units-v1";
            plot?: components["schemas"]["RegionComparisonPlot"];
        };
        /** RegionComparisonView */
        RegionComparisonView: {
            /**
             * Analysis Kind
             * @default region-comparison
             * @constant
             */
            analysis_kind: "region-comparison";
            /**
             * Source Kind
             * @default region-2d
             * @constant
             */
            source_kind: "region-2d";
            /**
             * Region Comparison Version
             * @default 1.0.0
             * @constant
             */
            region_comparison_version: "1.0.0";
            /** Inference Version */
            inference_version: string;
            /** Revision Id */
            revision_id: string;
            /** Source Fingerprint */
            source_fingerprint: string;
            spec: components["schemas"]["RegionComparisonRequest"];
            /** Metric */
            metric: string;
            /** Unit */
            unit: string;
            /** Region */
            region: {
                [key: string]: unknown;
            };
            /** Channel */
            channel: {
                [key: string]: unknown;
            } | null;
            /** Source Fields */
            source_fields: {
                [key: string]: unknown;
            }[];
            /** Source Field Ledger */
            source_field_ledger: {
                [key: string]: unknown;
            }[];
            /** Observation Ledger */
            observation_ledger: {
                [key: string]: unknown;
            }[];
            /** Plot Data */
            plot_data: {
                [key: string]: unknown;
            }[];
            /** Field Summary */
            field_summary: {
                [key: string]: unknown;
            }[];
            /** Sample Summary */
            sample_summary: {
                [key: string]: unknown;
            }[];
            /** Unit Summary */
            unit_summary: {
                [key: string]: unknown;
            }[];
            /** Unit Ledger */
            unit_ledger: {
                [key: string]: unknown;
            }[];
            /** Pair Ledger */
            pair_ledger: {
                [key: string]: unknown;
            }[];
            /** Counts */
            counts: {
                [key: string]: unknown;
            }[];
            /** Selection */
            selection: {
                [key: string]: unknown;
            };
            /** Missingness */
            missingness: {
                [key: string]: unknown;
            }[];
            /** Excluded Failed Fields */
            excluded_failed_fields: {
                [key: string]: unknown;
            }[];
            /** Acquisition */
            acquisition: {
                [key: string]: unknown;
            };
            /** Comparisons */
            comparisons: {
                [key: string]: unknown;
            }[];
            /** Means */
            means: {
                [key: string]: unknown;
            }[];
            /** Warnings */
            warnings: string[];
            /** Figure */
            figure: {
                [key: string]: unknown;
            };
        };
        /** RegionExcludedFailure */
        RegionExcludedFailure: {
            /** Field Id */
            field_id: string;
            /** Reason */
            reason: string;
            /** Error */
            error: string;
        };
        /** RegionExclusion */
        RegionExclusion: {
            /** Field Id */
            field_id: string;
            /** Region Id */
            region_id?: number | null;
            /** Reason */
            reason: string;
        };
        /** RegionFieldFailure */
        RegionFieldFailure: {
            /** Field Id */
            field_id: string;
            /** Reason */
            reason: string;
        };
        /** RegionFieldMask */
        RegionFieldMask: {
            /** Mask Revision Id */
            mask_revision_id: string;
            /** Mask Sha256 */
            mask_sha256: string;
            /** Region Set Id */
            region_set_id: string;
            /**
             * Source
             * @enum {string}
             */
            source: "manual" | "imported" | "stardist_nuclear";
            /** Shape */
            shape: number[];
            file: components["schemas"]["RegionStoredFile"];
        };
        /** RegionFieldMetadata */
        RegionFieldMetadata: {
            /** Condition */
            condition?: string | null;
            /** Experimental Unit */
            experimental_unit?: string | null;
            /** Sample */
            sample?: string | null;
            /** Acquisition Date */
            acquisition_date?: string | null;
            /** Pair */
            pair?: string | null;
            /** Repeat Length */
            repeat_length?: number | null;
        };
        /** RegionFieldView */
        RegionFieldView: {
            /** Id */
            id: string;
            /** Workspace Id */
            workspace_id: string;
            metadata: components["schemas"]["RegionFieldMetadata"];
            image_info: components["schemas"]["RegionImageInfo"];
            /** Synthetic */
            synthetic: boolean;
        };
        /** RegionImageInfo */
        RegionImageInfo: {
            /**
             * Kind
             * @default region-2d
             * @constant
             */
            kind: "region-2d";
            /** Shape */
            shape: number[];
            /**
             * Axes
             * @default YX
             * @constant
             */
            axes: "YX";
            /** Channels */
            channels: components["schemas"]["ChannelSpec"][];
            /** Inputs */
            inputs: {
                [key: string]: components["schemas"]["RegionStoredFile"];
            };
            /** Channel Arrays */
            channel_arrays: {
                [key: string]: components["schemas"]["RegionStoredFile"];
            };
            labels_array?: components["schemas"]["RegionStoredFile"] | null;
            calibration?: components["schemas"]["Calibration2D"] | null;
        };
        /** RegionMaskEdit */
        RegionMaskEdit: {
            /** Field Id */
            field_id: string;
            /** Region Set Id */
            region_set_id: string;
            /**
             * Operation
             * @enum {string}
             */
            operation: "add" | "replace" | "delete" | "merge" | "split";
            /** Ids */
            ids?: number[];
            /** Polygon */
            polygon?: number[][];
            /** Expected Mask Revision Id */
            expected_mask_revision_id?: string | null;
        };
        /** RegionMeasurementPolicy */
        RegionMeasurementPolicy: {
            /**
             * Version
             * @constant
             */
            version: "1.0.0";
            /**
             * Mode
             * @constant
             */
            mode: "area_only";
        };
        /** RegionMeasurementRow */
        RegionMeasurementRow: {
            /** Field Id */
            field_id: string;
            /** Analysis Revision Id */
            analysis_revision_id: string;
            /** Region Set Id */
            region_set_id: string;
            /** Mask Revision Id */
            mask_revision_id: string;
            /** Region Id */
            region_id: number;
            /** Channel Id */
            channel_id: string;
            /** Area Px */
            area_px: number;
            /** Area Um2 */
            area_um2: number | null;
            /** Area Missing Reason */
            area_missing_reason: "calibration_unknown" | null;
            /** Mean */
            mean: number;
            /** Median */
            median: number;
            /** Integrated */
            integrated: number;
            /** Mean Corrected */
            mean_corrected: number;
            /** Median Corrected */
            median_corrected: number;
            /** Integrated Corrected */
            integrated_corrected: number;
            /** Storage Limit Fraction */
            storage_limit_fraction: number;
            /** Acquisition Saturation Fraction */
            acquisition_saturation_fraction: number | null;
            /** Acquisition Saturation Missing Reason */
            acquisition_saturation_missing_reason: "acquisition_limit_unknown" | null;
            /** Touches Border */
            touches_border: boolean;
        };
        /** RegionMeasurementRowV2 */
        RegionMeasurementRowV2: {
            /** Field Id */
            field_id: string;
            /** Analysis Revision Id */
            analysis_revision_id: string;
            /** Region Set Id */
            region_set_id: string;
            /** Mask Revision Id */
            mask_revision_id: string;
            /** Region Id */
            region_id: number;
            /** Channel Id */
            channel_id: string;
            /** Area Px */
            area_px: number;
            /** Area Um2 */
            area_um2: number | null;
            /** Area Missing Reason */
            area_missing_reason: "calibration_unknown" | null;
            /** Mean */
            mean: null;
            /** Median */
            median: null;
            /** Integrated */
            integrated: null;
            /** Mean Corrected */
            mean_corrected: null;
            /** Median Corrected */
            median_corrected: null;
            /** Integrated Corrected */
            integrated_corrected: null;
            /**
             * Intensity Missing Reason
             * @constant
             */
            intensity_missing_reason: "not_requested";
            /** Storage Limit Fraction */
            storage_limit_fraction: null;
            /**
             * Storage Limit Missing Reason
             * @constant
             */
            storage_limit_missing_reason: "not_requested";
            /** Acquisition Saturation Fraction */
            acquisition_saturation_fraction: null;
            /**
             * Acquisition Saturation Missing Reason
             * @constant
             */
            acquisition_saturation_missing_reason: "not_requested";
            /** Touches Border */
            touches_border: boolean;
        };
        /** RegionMeasurementTable */
        RegionMeasurementTable: {
            /**
             * Protocol Version
             * @default 1.0.0
             * @constant
             */
            protocol_version: "1.0.0";
            /**
             * Status
             * @enum {string}
             */
            status: "measured" | "no_regions";
            /** Field Id */
            field_id: string;
            /** Analysis Revision Id */
            analysis_revision_id: string;
            region_set: components["schemas"]["RegionSetSpec"];
            /** Shape Yx */
            shape_yx: [
                number,
                number
            ];
            /** Mask Sha256 */
            mask_sha256: string;
            /**
             * Hash Format
             * @default cytellect-array-v1
             * @constant
             */
            hash_format: "cytellect-array-v1";
            calibration: components["schemas"]["Calibration2D"] | null;
            /** Channel Provenance */
            channel_provenance: components["schemas"]["ChannelProvenance"][];
            /** Rows */
            rows: components["schemas"]["RegionMeasurementRow"][];
        };
        /** RegionMeasurementTableV2 */
        RegionMeasurementTableV2: {
            /**
             * Protocol Version
             * @default 2.0.0
             * @constant
             */
            protocol_version: "2.0.0";
            measurement: components["schemas"]["RegionMeasurementPolicy"];
            /**
             * Status
             * @enum {string}
             */
            status: "measured" | "no_regions";
            /** Field Id */
            field_id: string;
            /** Analysis Revision Id */
            analysis_revision_id: string;
            region_set: components["schemas"]["RegionSetSpec"];
            /** Shape Yx */
            shape_yx: [
                number,
                number
            ];
            /** Mask Sha256 */
            mask_sha256: string;
            /**
             * Hash Format
             * @default cytellect-array-v1
             * @constant
             */
            hash_format: "cytellect-array-v1";
            calibration: components["schemas"]["Calibration2D"] | null;
            /** Channel Provenance */
            channel_provenance: components["schemas"]["ChannelProvenanceV2"][];
            /** Rows */
            rows: components["schemas"]["RegionMeasurementRowV2"][];
        };
        /** RegionMetadataEdit */
        RegionMetadataEdit: {
            /**
             * Version
             * @default 1.0.0
             * @constant
             */
            version: "1.0.0";
            /** Fields */
            fields: {
                [key: string]: components["schemas"]["RegionFieldMetadata"];
            };
        };
        /** RegionNuclearRecipe */
        RegionNuclearRecipe: {
            /**
             * Id
             * @default region-2d
             * @constant
             */
            id: "region-2d";
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            version: "1.1.0";
            /** Region Set Id */
            region_set_id: string;
            /** Label */
            label: string;
            /**
             * Source
             * @default stardist_nuclear
             * @constant
             */
            source: "stardist_nuclear";
            /** Defining Channel Id */
            defining_channel_id: string;
            /**
             * Nuclear Stain Confirmed
             * @constant
             */
            nuclear_stain_confirmed: true;
            detector?: components["schemas"]["NuclearDetectorSpec"];
        };
        /** RegionRecipe */
        RegionRecipe: {
            /**
             * Id
             * @default region-2d
             * @constant
             */
            id: "region-2d";
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            version: "1.0.0";
            /** Region Set Id */
            region_set_id: string;
            /** Label */
            label: string;
            /**
             * Source
             * @enum {string}
             */
            source: "manual" | "imported";
            /** Defining Channel Id */
            defining_channel_id?: string | null;
        };
        /**
         * RegionReport
         * @description Validate persisted JSON with model_validate_json, preserving strict tuples.
         *
         *     FastAPI should return that validated instance, rather than asking its Python
         *     response validator to reinterpret tuple-valued science fields from JSON lists.
         */
        RegionReport: {
            /**
             * Analysis Kind
             * @default region-2d
             * @constant
             */
            analysis_kind: "region-2d";
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            protocol_version: "1.0.0";
            /** Revision Id */
            revision_id: string;
            /** Recipe */
            recipe: components["schemas"]["RegionRecipe"] | components["schemas"]["RegionNuclearRecipe"];
            /** Field Tables */
            field_tables: {
                [key: string]: components["schemas"]["RegionMeasurementTable"];
            };
            /** Field Masks */
            field_masks: {
                [key: string]: components["schemas"]["RegionFieldMask"];
            };
            /** Field Outcomes */
            field_outcomes: {
                [key: string]: "measured" | "no_regions" | "failed" | "excluded_failed";
            };
            /** Field Failures */
            field_failures: components["schemas"]["RegionFieldFailure"][];
            /** Excluded Failed Fields */
            excluded_failed_fields: components["schemas"]["RegionExcludedFailure"][];
            /** Exclusions */
            exclusions: components["schemas"]["RegionExclusion"][];
        };
        /**
         * RegionReportV2
         * @description Explicit area-only report; v1 persisted data retains its original model.
         */
        RegionReportV2: {
            /**
             * Analysis Kind
             * @default region-2d
             * @constant
             */
            analysis_kind: "region-2d";
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            protocol_version: "2.0.0";
            measurement: components["schemas"]["RegionMeasurementPolicy"];
            /** Revision Id */
            revision_id: string;
            /** Recipe */
            recipe: components["schemas"]["RegionRecipe"] | components["schemas"]["RegionNuclearRecipe"];
            /** Field Tables */
            field_tables: {
                [key: string]: components["schemas"]["RegionMeasurementTableV2"];
            };
            /** Field Masks */
            field_masks: {
                [key: string]: components["schemas"]["RegionFieldMask"];
            };
            /** Field Outcomes */
            field_outcomes: {
                [key: string]: "measured" | "no_regions" | "failed" | "excluded_failed";
            };
            /** Field Failures */
            field_failures: components["schemas"]["RegionFieldFailure"][];
            /** Excluded Failed Fields */
            excluded_failed_fields: components["schemas"]["RegionExcludedFailure"][];
            /** Exclusions */
            exclusions: components["schemas"]["RegionExclusion"][];
        };
        /** RegionSelection */
        RegionSelection: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            source: "region";
            /** Region Set Id */
            region_set_id: string;
            /**
             * Channel Id
             * @default null
             */
            channel_id: string | null;
            /**
             * Metric
             * @enum {string}
             */
            metric: "area_px" | "area_um2" | "mean" | "median" | "integrated" | "mean_corrected" | "median_corrected" | "integrated_corrected";
        };
        /** RegionSetSpec */
        RegionSetSpec: {
            /** Region Set Id */
            region_set_id: string;
            /** Label */
            label: string;
            /** Mask Revision Id */
            mask_revision_id: string;
            /**
             * Source
             * @enum {string}
             */
            source: "manual" | "imported" | "stardist_nuclear";
            /** Defining Channel Id */
            defining_channel_id?: string | null;
        };
        /** RegionStoredFile */
        RegionStoredFile: {
            /** Sha256 */
            sha256: string;
            /** Bytes */
            bytes: number;
        };
        /** ResegmentInput */
        ResegmentInput: {
            recipe?: components["schemas"]["Recipe"] | null;
            /** Field Ids */
            field_ids: string[];
            /** Backgrounds */
            backgrounds?: {
                [key: string]: components["schemas"]["Background"];
            } | null;
            /** Exclusions */
            exclusions?: components["schemas"]["Exclusion"][] | null;
            plan_resolution?: components["schemas"]["PlanResolution"] | null;
        };
        /** ReviewInput */
        ReviewInput: {
            /** Accept Invalidated Fields */
            accept_invalidated_fields?: string[];
        };
        /** RevisionInput */
        RevisionInput: {
            /** Revision Id */
            revision_id: string;
        };
        /** RevisionView */
        RevisionView: {
            /** Id */
            id: string;
            /** Workspace Id */
            workspace_id: string;
            /** Parent Id */
            parent_id: string | null;
            /** Config */
            config: {
                [key: string]: unknown;
            };
            /**
             * State
             * @enum {string}
             */
            state: "queued" | "running" | "succeeded" | "failed" | "cancelled";
            /** Reviewed */
            reviewed: boolean;
            /** Created */
            created: number;
        };
        /** StatisticsRequest */
        StatisticsRequest: {
            /**
             * Metric
             * @default ncl_log2_nucleoplasm_over_nucleoli
             * @enum {string}
             */
            metric: "ncl_nucleus_mean" | "ncl_nucleus_median" | "ncl_nucleus_integrated" | "ncl_nucleus_mean_corrected" | "ncl_nucleus_median_corrected" | "ncl_nucleus_integrated_corrected" | "ncl_nucleoli_mean" | "ncl_nucleoli_median" | "ncl_nucleoli_integrated" | "ncl_nucleoli_mean_corrected" | "ncl_nucleoli_median_corrected" | "ncl_nucleoli_integrated_corrected" | "ncl_nucleoplasm_mean" | "ncl_nucleoplasm_median" | "ncl_nucleoplasm_integrated" | "ncl_nucleoplasm_mean_corrected" | "ncl_nucleoplasm_median_corrected" | "ncl_nucleoplasm_integrated_corrected" | "gfp_mean" | "gfp_median" | "gfp_integrated" | "gfp_mean_corrected" | "gfp_median_corrected" | "gfp_integrated_corrected" | "nucleus_area_px" | "nucleus_area_um2" | "nucleolar_area_px" | "nucleolar_area_um2" | "nucleoplasm_area_px" | "nucleoplasm_area_um2" | "nucleolar_count" | "nucleolar_area_fraction" | "ncl_nucleoplasm_over_nucleoli" | "ncl_log2_nucleoplasm_over_nucleoli" | "ncl_legacy_release" | "value";
            /**
             * Mode
             * @default experimental-unit
             * @enum {string}
             */
            mode: "experimental-unit" | "exploratory";
            /** Baseline */
            baseline: string;
            /** Comparisons */
            comparisons: [
                string,
                string
            ][];
            /**
             * Paired
             * @default false
             */
            paired: boolean;
            /**
             * Independent Units Confirmed
             * @default false
             */
            independent_units_confirmed: boolean;
            plot?: components["schemas"]["PlotSpec"];
            /**
             * Comparison Family
             * @default all
             * @enum {string}
             */
            comparison_family: "baseline" | "repeat" | "all";
            /**
             * Gfp Transform
             * @default positive-log2
             * @enum {string}
             */
            gfp_transform: "positive-log2" | "legacy-log2p1";
            /** Sensitivity Gfp Thresholds */
            sensitivity_gfp_thresholds?: number[];
            /**
             * Sensitivity Complete Dates
             * @default false
             */
            sensitivity_complete_dates: boolean;
            /** Sensitivity Legacy High Regions */
            sensitivity_legacy_high_regions?: (5 | 10 | 20)[];
            /** Sensitivity Region Revision Ids */
            sensitivity_region_revision_ids?: string[];
        };
        /** ValidationError */
        ValidationError: {
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
            /** Input */
            input?: unknown;
            /** Context */
            ctx?: Record<string, never>;
        };
        /** WorkspaceInput */
        WorkspaceInput: {
            /**
             * Title
             * @default Untitled experiment
             */
            title: string;
            plan?: components["schemas"]["PlanInput"] | null;
            /** Plan Candidate Id */
            plan_candidate_id?: ("regions-manual" | "regions-imported" | "regions-nuclei" | "legacy-gfp-nuclear" | "legacy-ncl") | null;
        };
        /** WorkspaceView */
        WorkspaceView: {
            /** Id */
            id: string;
            /** Owner */
            owner: string;
            /** Title */
            title: string;
            /** Created */
            created: number;
            /** Expires */
            expires: number;
            /** Deleted */
            deleted: boolean;
            /** Active Revision */
            active_revision: string | null;
            /** Bytes */
            bytes: number;
            analysis_plan?: components["schemas"]["AdoptedPlan"] | null;
        };
        /** PreviewPlaneDisplay */
        PreviewPlaneDisplay: {
            /** Channel Id */
            channel_id: string;
            /** Dtype */
            dtype: string;
            /**
             * Value Basis
             * @enum {string}
             */
            value_basis: "native-grayscale" | "legacy-imported";
            /** Source Min */
            source_min: number;
            /** Source Max */
            source_max: number;
            /** Percentile Low Value */
            percentile_low_value: number;
            /** Percentile High Value */
            percentile_high_value: number;
            /** Normalization Span */
            normalization_span: number;
            /** Display Black Value */
            display_black_value: number;
            /** Display White Value */
            display_white_value: number;
            /** Constant Plane */
            constant_plane: boolean;
        };
        /** PreviewDisplayMetadata */
        PreviewDisplayMetadata: {
            /**
             * Version
             * @default 1.0.0
             * @constant
             */
            version: "1.0.0";
            /** Field Id */
            field_id: string;
            /** Requested Channel */
            requested_channel: string;
            /** Composite */
            composite: boolean;
            /**
             * Scope
             * @default whole-plane
             * @constant
             */
            scope: "whole-plane";
            /**
             * Mode
             * @default per-plane-percentile
             * @constant
             */
            mode: "per-plane-percentile";
            /** Low Percentile */
            low_percentile: number;
            /** High Percentile */
            high_percentile: number;
            /** Gain */
            gain: number;
            /** Planes */
            planes: components["schemas"]["PreviewPlaneDisplay"][];
        };
        /** DescriptiveOutputFile */
        DescriptiveOutputFile: {
            /** Sha256 */
            sha256: string;
            /** Bytes */
            bytes: number;
        };
        /** DescriptivePage */
        DescriptivePage: {
            /** Page Index */
            page_index: number;
            files: components["schemas"]["DescriptivePageFiles"];
        };
        /** DescriptivePageFiles */
        DescriptivePageFiles: {
            /** Svg */
            svg: string;
            /** Pdf */
            pdf: string;
            /** Png */
            png: string;
        };
        /** DescriptivePagePlan */
        DescriptivePagePlan: {
            /** Page Index */
            page_index: number;
            /** Field Ids */
            field_ids: string[];
            /** Field Numbers */
            field_numbers: number[];
        };
        /** DescriptiveRenderError */
        DescriptiveRenderError: {
            /**
             * Code
             * @enum {string}
             */
            code: "figure_labels_overlap" | "figure_text_outside_canvas" | "japanese_font_not_installed" | "sans_serif_font_not_installed" | "figure_font_glyphs_unavailable";
            /** Page Index */
            page_index: number | null;
        };
        /** PagedDescriptiveOutput */
        PagedDescriptiveOutput: {
            /**
             * Descriptive Figure Version
             * @constant
             */
            descriptive_figure_version: "2.0.0";
            /**
             * Status
             * @enum {string}
             */
            status: "ready" | "tables_only";
            error: components["schemas"]["DescriptiveRenderError"] | null;
            /** Field Order */
            field_order: string[];
            /** Page Plan */
            page_plan: components["schemas"]["DescriptivePagePlan"][];
            /** Pages */
            pages: components["schemas"]["DescriptivePage"][];
            /** Y Limits */
            y_limits: number[];
            /** Y Ticks */
            y_ticks: number[];
            /** Style */
            style: {
                [key: string]: unknown;
            };
            /** Font Metadata */
            font_metadata: {
                [key: string]: unknown;
            } | null;
            /** Source Result Sha256 */
            source_result_sha256: string;
            /** Source Files */
            source_files: string[];
            /** Files */
            files: {
                [key: string]: components["schemas"]["DescriptiveOutputFile"];
            };
        };
        /** PagedDescriptiveResult */
        PagedDescriptiveResult: {
            /**
             * Analysis Kind
             * @default descriptive
             * @constant
             */
            analysis_kind: "descriptive";
            /**
             * Descriptive Version
             * @default 1.0.0
             * @constant
             */
            descriptive_version: "1.0.0";
            spec: components["schemas"]["PagedDescriptiveRequest"];
            /**
             * Source Kind
             * @enum {string}
             */
            source_kind: "legacy-image-measurements" | "region-2d" | "measured-numerical-assay";
            /**
             * Observation Kind
             * @enum {string}
             */
            observation_kind: "nuclei" | "regions" | "observations";
            /** Metric */
            metric: string;
            /** Unit */
            unit: string;
            /** Metric Definition */
            metric_definition: string;
            /** Plot Data */
            plot_data: {
                [key: string]: unknown;
            }[];
            /** Field Summary */
            field_summary: {
                [key: string]: unknown;
            }[];
            /** Counts */
            counts: {
                [key: string]: unknown;
            };
            /** Selection */
            selection: {
                [key: string]: unknown;
            };
            /** Missingness */
            missingness: {
                [key: string]: unknown;
            }[];
            /** Source Fields */
            source_fields: {
                [key: string]: unknown;
            }[];
            /** Excluded Failed Fields */
            excluded_failed_fields?: {
                [key: string]: unknown;
            }[];
            /** Warnings */
            warnings: string[];
            /**
             * Independence Status
             * @default not_assessed_in_descriptive_analysis
             * @constant
             */
            independence_status: "not_assessed_in_descriptive_analysis";
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    health_v1_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    redeem_v1_invitations_redeem_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["InviteInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    session_v1_session_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    logout_v1_session_delete: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
        };
    };
    list_workspaces_v1_workspaces_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkspaceView"][];
                };
            };
        };
    };
    new_workspace_v1_workspaces_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["WorkspaceInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkspaceView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_workspace_v1_workspaces__wid__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                wid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkspaceView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    delete_workspace_v1_workspaces__wid__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                wid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    keep_alive_v1_workspaces__wid__touch_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                wid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_fields_v1_workspaces__wid__fields_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                wid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FieldView"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_field_v1_workspaces__wid__fields_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                wid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_field_v1_workspaces__wid__fields_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FieldView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    synthetic_v1_workspaces__wid__synthetic_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                wid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    preview_v1_fields__fid__preview_get: {
        parameters: {
            query?: {
                channel?: string;
                low?: number;
                high?: number;
                gain?: number;
            };
            header?: never;
            path: {
                fid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    /** @description ASCII-escaped JSON for the exact rendered PNG; display only. */
                    "X-Cytellect-Preview-Display"?: {
                        "application/json": components["schemas"]["PreviewDisplayMetadata"];
                    };
                    [name: string]: unknown;
                };
                content: {
                    "image/png": string;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_analysis_v1_workspaces__wid__analyses_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                wid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AnalysisRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_revisions_v1_workspaces__wid__revisions_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                wid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RevisionView"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_revision_v1_revisions__rid__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RevisionView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    measurements_v1_revisions__rid__measurements_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_masks_v1_revisions__rid__fields__fid__masks_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rid: string;
                fid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["MasksView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    edit_v1_revisions__rid__edits_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["MaskEdit"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    choose_revision_v1_workspaces__wid__current_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                wid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RevisionInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    review_v1_revisions__rid__review_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rid: string;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["ReviewInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    statistics_v1_revisions__rid__statistics_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StatisticsRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    export_v1_revisions__rid__export_post: {
        parameters: {
            query?: {
                include_raw?: boolean;
            };
            header?: never;
            path: {
                rid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reconfigure_v1_revisions__rid__reconfigure_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AnalysisRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    resegment_v1_revisions__rid__resegment_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ResegmentInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    retry_v1_jobs__jid__retry_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                jid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_tables_v1_workspaces__wid__tables_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                wid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    import_table_v1_workspaces__wid__tables_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                wid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_import_table_v1_workspaces__wid__tables_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    table_statistics_v1_tables__tid__statistics_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                tid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StatisticsRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_jobs_v1_workspaces__wid__jobs_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                wid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobView"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_job_v1_jobs__jid__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                jid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["JobView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    cancel_v1_jobs__jid__cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                jid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    job_result_v1_jobs__jid__result_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                jid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    job_file_v1_jobs__jid__files__name__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                jid: string;
                name: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_region_fields_v1_workspaces__wid__region_fields_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                wid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RegionFieldView"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    upload_region_field_v1_workspaces__wid__region_fields_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                wid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_upload_region_field_v1_workspaces__wid__region_fields_post"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RegionFieldView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    preview_v1_region_fields__fid__preview_get: {
        parameters: {
            query: {
                channel_id: string;
                low?: number;
                high?: number;
                gain?: number;
            };
            header?: never;
            path: {
                fid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    /** @description ASCII-escaped JSON for the exact rendered PNG; display only. */
                    "X-Cytellect-Preview-Display"?: {
                        "application/json": components["schemas"]["PreviewDisplayMetadata"];
                    };
                    [name: string]: unknown;
                };
                content: {
                    "image/png": string;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    start_v1_workspaces__wid__region_analyses_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                wid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RegionAnalysisRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    measurements_v1_revisions__rid__region_measurements_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RegionReport"] | components["schemas"]["RegionReportV2"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    masks_v1_revisions__rid__region_masks_get: {
        parameters: {
            query: {
                field_id: string;
            };
            header?: never;
            path: {
                rid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    edit_v1_revisions__rid__region_edits_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RegionMaskEdit"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    reconfigure_v1_revisions__rid__region_reconfigure_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RegionAnalysisRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    metadata_v1_revisions__rid__region_metadata_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RegionMetadataEdit"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    descriptive_v1_revisions__rid__descriptive_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DescriptiveRequest"] | components["schemas"]["PagedDescriptiveRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    compare_v1_revisions__rid__region_comparisons_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                rid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RegionComparisonRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": unknown;
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    result_v1_jobs__jid__region_comparison_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                jid: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RegionComparisonView"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    preview_plan_v1_plans_preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PlanInput"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlanSnapshot"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
