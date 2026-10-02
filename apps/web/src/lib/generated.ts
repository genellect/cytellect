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
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** AnalysisRequest */
        AnalysisRequest: {
            /** Field Ids */
            field_ids?: string[] | null;
            recipe?: components["schemas"]["Recipe"];
            /** Backgrounds */
            backgrounds?: {
                [key: string]: components["schemas"]["Background"];
            };
            /** Exclusions */
            exclusions?: components["schemas"]["Exclusion"][];
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
            /**
             * Seed
             * @default 0
             */
            seed: number;
            legacy?: components["schemas"]["LegacyParameters"];
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
}
