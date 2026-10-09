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
    "/v1/tables/{tid}/descriptive": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Table Descriptive */
        post: operations["table_descriptive_v1_tables__tid__descriptive_post"];
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
    "/v1/workspaces/{wid}/region-fields/ome": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Upload Ome */
        post: operations["upload_ome_v1_workspaces__wid__region_fields_ome_post"];
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
    "/v1/revisions/{rid}/region-compartment-status": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Compartment Status */
        get: operations["compartment_status_v1_revisions__rid__region_compartment_status_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{wid}/gfp-gate": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Gfp Gate
         * @description Classify saved nuclei by mean GFP intensity; no new pixel masks are created.
         */
        post: operations["gfp_gate_v1_workspaces__wid__gfp_gate_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/revisions/{rid}/compartment-summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Compartment Summary
         * @description Per-nucleus nucleolar/nucleoplasmic summary computed by the worker (never in the browser).
         */
        get: operations["compartment_summary_v1_revisions__rid__compartment_summary_get"];
        put?: never;
        post?: never;
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
    "/v1/revisions/{rid}/descriptive-preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Descriptive Preview */
        post: operations["descriptive_preview_v1_revisions__rid__descriptive_preview_post"];
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
    "/v1/revisions/{rid}/common-statistics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Calculate */
        post: operations["calculate_v1_revisions__rid__common_statistics_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/jobs/{jid}/common-statistics": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Result */
        get: operations["result_v1_jobs__jid__common_statistics_get"];
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
    "/v1/workspaces/{wid}/proposal-drafts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Draft Proposal */
        post: operations["draft_proposal_v1_workspaces__wid__proposal_drafts_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{wid}/selection": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Selection */
        get: operations["get_selection_v1_workspaces__wid__selection_get"];
        put?: never;
        /** Save Selection */
        post: operations["save_selection_v1_workspaces__wid__selection_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{wid}/channel-assignments": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Assignments */
        get: operations["get_assignments_v1_workspaces__wid__channel_assignments_get"];
        /** Save Assignments */
        put: operations["save_assignments_v1_workspaces__wid__channel_assignments_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{wid}/analysis-spec": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Spec */
        get: operations["get_spec_v1_workspaces__wid__analysis_spec_get"];
        /** Save Spec */
        put: operations["save_spec_v1_workspaces__wid__analysis_spec_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{wid}/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Runs */
        get: operations["list_runs_v1_workspaces__wid__runs_get"];
        put?: never;
        /** Start Run */
        post: operations["start_run_v1_workspaces__wid__runs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{wid}/runs/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Run */
        get: operations["get_run_v1_workspaces__wid__runs__run_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{wid}/runs/{run_id}/accept": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Accept Run */
        post: operations["accept_run_v1_workspaces__wid__runs__run_id__accept_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{wid}/runs/{run_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancel Run */
        post: operations["cancel_run_v1_workspaces__wid__runs__run_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{wid}/field-links": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Links */
        get: operations["get_links_v1_workspaces__wid__field_links_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{wid}/field-links/{fid}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Save Link */
        put: operations["save_link_v1_workspaces__wid__field_links__fid__put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/jobs/{jid}/publication-package": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Publication Package */
        post: operations["publication_package_v1_jobs__jid__publication_package_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/jobs/{jid}/figure-render": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Rendered */
        get: operations["rendered_v1_jobs__jid__figure_render_get"];
        put?: never;
        /** Render */
        post: operations["render_v1_jobs__jid__figure_render_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/revisions/{rid}/workspace-selection": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Saved Selection */
        get: operations["saved_selection_v1_revisions__rid__workspace_selection_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/v1/workspaces/{wid}/region-cohorts": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Assemble */
        post: operations["assemble_v1_workspaces__wid__region_cohorts_post"];
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
        /** AdoptedNuclearRecipe */
        AdoptedNuclearRecipe: {
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
            version: "1.2.0";
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
             * Nuclear Role Source
             * @enum {string}
             */
            nuclear_role_source: "recorded_stain" | "user_selected_role";
            detector?: components["schemas"]["NuclearDetectorSpec"];
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
        /** AnalysisSelectionDraft */
        AnalysisSelectionDraft: {
            /** Field Ids */
            field_ids?: string[];
            /** Gfp */
            gfp?: components["schemas"]["GfpGateFilter"] | components["schemas"]["ExploratoryGfpGateFilter"] | null;
        };
        /** AnalysisSpec */
        AnalysisSpec: {
            /**
             * Schema Version
             * @default 1.0.0
             * @constant
             */
            schema_version: "1.0.0";
            /** Channel Assignment Version */
            channel_assignment_version: number;
            /**
             * Target
             * @default nuclei
             * @enum {string}
             */
            target: "nuclei" | "nucleoli" | "nucleoplasm" | "cell";
            settings?: components["schemas"]["RuntimeSettingsDraft"];
            processing?: components["schemas"]["SavedProcessing"] | null;
            /** Measurement */
            measurement?: components["schemas"]["RawIntensityPolicy"] | components["schemas"]["AutomaticBackgroundPolicy"] | null;
            /** Backgrounds */
            backgrounds?: {
                [key: string]: {
                    [key: string]: components["schemas"]["RegionBackground"];
                };
            };
            /** Confirmed Channel Ids */
            confirmed_channel_ids?: string[];
            /** Metrics */
            metrics?: components["schemas"]["SavedDraftMetric"][];
            selection?: components["schemas"]["AnalysisSelectionDraft"];
            statistics?: components["schemas"]["StatisticsDraft"] | null;
            /** Additional Analyses */
            additional_analyses?: components["schemas"]["SavedDraftStatistics"][];
            /** Figure Proposals */
            figure_proposals?: components["schemas"]["SavedDraftFigure"][];
            figure?: components["schemas"]["FigureDraft"] | null;
        };
        /** AnalysisSpecView */
        AnalysisSpecView: {
            /** Version */
            version: number;
            spec: components["schemas"]["AnalysisSpec"] | null;
        };
        /** AnalysisSpecWrite */
        AnalysisSpecWrite: {
            /** Version */
            version: number;
            spec: components["schemas"]["AnalysisSpec"];
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
        /** AssociationPlot */
        AssociationPlot: {
            style?: components["schemas"]["FigureStyle"] | null;
            axes?: components["schemas"]["FigureAxes"] | null;
            /**
             * Preset
             * @default nature-single
             * @enum {string}
             */
            preset: "custom" | "nature-single" | "nature-double";
            /**
             * Kind
             * @default scatter
             * @constant
             */
            kind: "scatter";
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
            /** Y Min */
            y_min?: number | null;
            /** Y Max */
            y_max?: number | null;
            /** Y Tick Step */
            y_tick_step?: number | null;
            /** Point Size */
            point_size?: number | null;
        };
        /** AssociationView */
        AssociationView: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            analysis_kind: "region-association";
            /**
             * Source Kind
             * @default region-2d
             * @constant
             */
            source_kind: "region-2d";
            /**
             * Region Association Version
             * @default 1.0.0
             * @enum {string}
             */
            region_association_version: "1.0.0" | "1.1.0";
            /** Inference Version */
            inference_version: string;
            /** Revision Id */
            revision_id: string;
            /** Source Fingerprint */
            source_fingerprint: string;
            spec: components["schemas"]["RegionAssociationRequest"];
            /** X Source */
            x_source: {
                [key: string]: unknown;
            };
            /** Y Source */
            y_source: {
                [key: string]: unknown;
            };
            /** Unit Summary */
            unit_summary: {
                [key: string]: unknown;
            }[];
            /** Unit Ledger */
            unit_ledger: {
                [key: string]: unknown;
            }[];
            /** Associations */
            associations: {
                [key: string]: unknown;
            }[];
            /** Counts */
            counts: {
                [key: string]: unknown;
            }[];
            /** Missingness */
            missingness: {
                [key: string]: unknown;
            }[];
            /** Warnings */
            warnings: string[];
            /** Figure */
            figure: {
                [key: string]: unknown;
            };
        };
        /**
         * AutoScaledNuclearRecipe
         * @description Nuclei with a detection copy sized from the estimated nucleus diameter (nuclear-size/1.0.0).
         */
        AutoScaledNuclearRecipe: {
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
            version: "1.7.0";
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
             * Nuclear Role Source
             * @enum {string}
             */
            nuclear_role_source: "recorded_stain" | "user_selected_role";
            /**
             * Detection Scale
             * @default nuclear-size/1.0.0
             * @constant
             */
            detection_scale: "nuclear-size/1.0.0";
            detector?: components["schemas"]["NuclearDetectorSpec"];
        };
        /** AutomaticBackgroundConstants */
        AutomaticBackgroundConstants: {
            /** Tile Size Px */
            tile_size_px: number;
            /** Perinuclear Margin Px */
            perinuclear_margin_px: number;
            /** Margin Metric */
            margin_metric: string;
            /** Min Unexcluded Fraction */
            min_unexcluded_fraction: number;
            /** Bright Rule */
            bright_rule: string;
            /** Bright K */
            bright_k: number;
            /** Bright Mad Floor */
            bright_mad_floor: number;
            /** Mad Scale */
            mad_scale: number;
            /** Tile Median K */
            tile_median_k: number;
            /** Tile Dispersion K */
            tile_dispersion_k: number;
            /** Rejection Passes */
            rejection_passes: number;
            /** Min Tiles */
            min_tiles: number;
            /** Min Quadrants */
            min_quadrants: number;
            /** Quadrant Rule */
            quadrant_rule: string;
        };
        /**
         * AutomaticBackgroundPolicy
         * @description Raw values plus corrections from an automatic, unconfirmed background candidate.
         */
        AutomaticBackgroundPolicy: {
            /**
             * Version
             * @constant
             */
            version: "1.2.0";
            /**
             * Mode
             * @constant
             */
            mode: "automatic_background";
        };
        /** AutomaticBackgroundProvenance */
        AutomaticBackgroundProvenance: {
            /**
             * Status
             * @enum {string}
             */
            status: "established" | "not_established";
            /**
             * Background Source
             * @default automatic_candidate
             * @constant
             */
            background_source: "automatic_candidate";
            /**
             * Confirmed
             * @default false
             * @constant
             */
            confirmed: false;
            /**
             * Algorithm
             * @constant
             */
            algorithm: "cytellect-automatic-background";
            /**
             * Algorithm Version
             * @constant
             */
            algorithm_version: "1.0.0";
            constants: components["schemas"]["AutomaticBackgroundConstants"];
            /** Exclusion Mask Sha256 */
            exclusion_mask_sha256: string;
            /** Additional Exclusion */
            additional_exclusion: boolean;
            /** Bright Threshold */
            bright_threshold: number | null;
            /** Excluded Pixel Count */
            excluded_pixel_count: number;
            /** Eligible Tile Count */
            eligible_tile_count: number;
            /** Median Rejected Tile Count */
            median_rejected_tile_count: number;
            /** Dispersion Rejected Tile Count */
            dispersion_rejected_tile_count: number;
            /** Retained Tile Count */
            retained_tile_count: number;
            /** Quadrants */
            quadrants: number[];
            /** Retained Tile Median Min */
            retained_tile_median_min: number | null;
            /** Retained Tile Median Max */
            retained_tile_median_max: number | null;
            /** Background Mask Sha256 */
            background_mask_sha256: string | null;
            /** Background Pixel Count */
            background_pixel_count: number | null;
            /** Background Median */
            background_median: number | null;
            /** Reason */
            reason: ("automatic_background_insufficient_tiles" | "automatic_background_insufficient_coverage") | null;
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
            /**
             * Mode
             * @default experimental-unit
             * @enum {string}
             */
            mode: "experimental-unit" | "descriptive";
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
        /** Body_upload_ome_v1_workspaces__wid__region_fields_ome_post */
        Body_upload_ome_v1_workspaces__wid__region_fields_ome_post: {
            /** Ome */
            ome: string;
            /** Client Upload Id */
            client_upload_id?: string | null;
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
            /** Ch3 */
            ch3?: string | null;
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
        /** CellDefinitionDraft */
        CellDefinitionDraft: {
            /**
             * Source
             * @default manual
             * @enum {string}
             */
            source: "manual" | "cellpose";
            /**
             * Channel
             * @default
             */
            channel: string;
        };
        /** CellposeDetectorSpec */
        CellposeDetectorSpec: {
            /**
             * Model
             * @default cpsam_v2
             * @constant
             */
            model: "cpsam_v2";
            /**
             * Model Sha256
             * @default 0f1cc3f7ecdd8a037a57c6c48d9d8921391be4cbce3fa9f13c3e3a2e1253c667
             * @constant
             */
            model_sha256: "0f1cc3f7ecdd8a037a57c6c48d9d8921391be4cbce3fa9f13c3e3a2e1253c667";
            /** Diameter Px */
            diameter_px?: number | null;
            /**
             * Normalization Percentile Low
             * @default 1
             */
            normalization_percentile_low: number;
            /**
             * Normalization Percentile High
             * @default 99
             */
            normalization_percentile_high: number;
            /**
             * Flow Threshold
             * @default 0.4
             */
            flow_threshold: number;
            /**
             * Cellprob Threshold
             * @default 0
             */
            cellprob_threshold: number;
            /**
             * Minimum Area Px
             * @default 15
             */
            minimum_area_px: number;
            /**
             * Maximum Size Fraction
             * @default 1
             */
            maximum_size_fraction: number;
            /** Iterations */
            iterations?: number | null;
            /**
             * Batch Size
             * @default 1
             */
            batch_size: number;
            /**
             * Compute Device
             * @default cpu
             * @enum {string}
             */
            compute_device: "cpu" | "auto" | "cuda";
            /**
             * Engine
             * @default cellpose-sam
             * @constant
             */
            engine: "cellpose-sam";
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            protocol_version: "4.0.0";
        };
        /** ChannelAssignment */
        ChannelAssignment: {
            /** Channel Id */
            channel_id: string;
            /** Stain */
            stain: string | null;
            /**
             * Role
             * @enum {string}
             */
            role: "nuclear" | "measure" | "unused";
        };
        /** ChannelAssignmentGroup */
        ChannelAssignmentGroup: {
            /** Id */
            id: string;
            /** Field Ids */
            field_ids: string[];
            /** Channel Ids */
            channel_ids: string[];
            /** Assignments */
            assignments: components["schemas"]["ChannelAssignment"][];
        };
        /** ChannelAssignments */
        ChannelAssignments: {
            /** Version */
            version: number;
            /** Assignments */
            assignments: components["schemas"]["ChannelAssignment"][];
            /** Global Field Ids */
            global_field_ids?: string[];
            /** Groups */
            groups?: components["schemas"]["ChannelAssignmentGroup"][];
        };
        /** ChannelAssignmentsWrite */
        ChannelAssignmentsWrite: {
            /** Version */
            version: number;
            /** Assignments */
            assignments: components["schemas"]["ChannelAssignment"][];
            /** Field Ids */
            field_ids?: string[] | null;
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
            /** Channel */
            channel: components["schemas"]["ChannelSpec"] | components["schemas"]["ObservedChannelSpec"];
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
        /** ChannelProvenanceV3 */
        ChannelProvenanceV3: {
            /** Channel */
            channel: components["schemas"]["ChannelSpec"] | components["schemas"]["ObservedChannelSpec"];
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
            background: components["schemas"]["RawBackgroundProvenance"];
        };
        /** ChannelProvenanceV4 */
        ChannelProvenanceV4: {
            /** Channel */
            channel: components["schemas"]["ChannelSpec"] | components["schemas"]["ObservedChannelSpec"];
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
            background: components["schemas"]["AutomaticBackgroundProvenance"];
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
        /** CohortSource */
        CohortSource: {
            /** Field Id */
            field_id: string;
            /** Revision Id */
            revision_id: string;
        };
        /** CommonComparisonPlot */
        CommonComparisonPlot: {
            style?: components["schemas"]["FigureStyle"] | null;
            axes?: components["schemas"]["FigureAxes"] | null;
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
            kind: "distribution" | "paired" | "histogram" | "box" | "violin";
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
            /** Y Min */
            y_min?: number | null;
            /** Y Max */
            y_max?: number | null;
            /** Y Tick Step */
            y_tick_step?: number | null;
            /** Point Size */
            point_size?: number | null;
            /**
             * Histogram Bins
             * @default 10
             */
            histogram_bins: number;
        };
        /** CommonComparisonView */
        CommonComparisonView: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
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
             * @default 2.0.0
             * @constant
             */
            region_comparison_version: "2.0.0";
            /** Inference Version */
            inference_version: string;
            /** Revision Id */
            revision_id: string;
            /** Source Fingerprint */
            source_fingerprint: string;
            spec: components["schemas"]["RegionComparisonRequestV2"];
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
            /** Omnibus */
            omnibus: {
                [key: string]: unknown;
            } | null;
            /** Method Settings */
            method_settings: {
                [key: string]: unknown;
            };
            /** Figure */
            figure: {
                [key: string]: unknown;
            };
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
        /**
         * CompartmentSummarySelection
         * @description Per-nucleus values from a nucleoplasm revision's compartment-summary.json.
         *
         *     Separately versioned observation source (compartment-summary selection 1.0.0);
         *     the descriptive and inferential protocols that consume it are unchanged.
         *     The log2 ratio is per channel; area fraction and count are channel-neutral.
         */
        CompartmentSummarySelection: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            source: "compartment-summary";
            /**
             * Version
             * @default 1.0.0
             * @constant
             */
            version: "1.0.0";
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
            metric: "log2_nucleoplasm_over_nucleolus" | "nucleolar_area_fraction" | "nucleolar_count";
            /** Gfp Gate */
            gfp_gate?: components["schemas"]["GfpGateFilter"] | components["schemas"]["ExploratoryGfpGateFilter"] | null;
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
            /** @default null */
            style: components["schemas"]["FigureStyle"] | null;
            /** @default null */
            axes: components["schemas"]["FigureAxes"] | null;
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
            /**
             * Y Min
             * @default null
             */
            y_min: number | null;
            /**
             * Y Max
             * @default null
             */
            y_max: number | null;
            /**
             * Y Tick Step
             * @default null
             */
            y_tick_step: number | null;
            /**
             * Point Size
             * @default null
             */
            point_size: number | null;
        };
        /** DescriptiveRequest */
        DescriptiveRequest: {
            /**
             * Mode
             * @constant
             */
            mode: "descriptive";
            /** Selection */
            selection: components["schemas"]["LegacySelection"] | components["schemas"]["RegionSelection"] | components["schemas"]["NumericalSelection"] | components["schemas"]["CompartmentSummarySelection"];
            /**
             * Group By
             * @default field
             * @constant
             */
            group_by: "field";
            plot?: components["schemas"]["DescriptivePlot"];
        };
        /** DraftBackground */
        DraftBackground: {
            /**
             * Mode
             * @enum {string}
             */
            mode: "raw" | "automatic" | "confirmed_roi";
        };
        /** DraftCellProcessing */
        DraftCellProcessing: {
            /** Channel */
            channel: string;
            detector?: components["schemas"]["CellposeDetectorSpec"];
        };
        /** DraftChannel */
        DraftChannel: {
            /** Token */
            token: string;
            /** Stain */
            stain: string | null;
            /**
             * Role
             * @enum {string}
             */
            role: "nuclear" | "measure" | "unused";
            /** Reason */
            reason: string;
        };
        /** DraftFigure */
        DraftFigure: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "field-distribution" | "unit-comparison" | "paired" | "association-scatter";
            /**
             * Metric
             * @enum {string}
             */
            metric: "area" | "mean_raw" | "integral_raw" | "mean_corrected" | "integral_corrected" | "ncl_log2_nucleoplasm_over_nucleoli" | "nucleolar_area_fraction" | "nucleolar_count";
            /** Channel */
            channel: string | null;
            /** Region */
            region?: ("nucleus" | "nucleoli" | "nucleoplasm" | "supplied") | null;
            /**
             * Analysis Index
             * @default 0
             */
            analysis_index: number;
        };
        /** DraftGfpSelection */
        DraftGfpSelection: {
            /** Channel */
            channel: string;
            /**
             * Unit
             * @default nucleus
             * @enum {string}
             */
            unit: "nucleus" | "cell_roi";
            /**
             * Method
             * @enum {string}
             */
            method: "manual" | "batch_otsu" | "negative_control";
            /** Threshold */
            threshold?: number | null;
            /**
             * Values
             * @default raw
             * @enum {string}
             */
            values: "raw" | "corrected";
            /**
             * Keep
             * @default positive
             * @enum {string}
             */
            keep: "positive" | "negative";
            /**
             * Percentile
             * @default 99
             */
            percentile: number;
        };
        /** DraftMetric */
        DraftMetric: {
            /**
             * Metric
             * @enum {string}
             */
            metric: "area" | "mean_raw" | "integral_raw" | "mean_corrected" | "integral_corrected" | "ncl_log2_nucleoplasm_over_nucleoli" | "nucleolar_area_fraction" | "nucleolar_count";
            /** Channel */
            channel: string | null;
            /** Region */
            region?: ("nucleus" | "nucleoli" | "nucleoplasm" | "supplied") | null;
        };
        /** DraftNuclearProcessing */
        DraftNuclearProcessing: {
            /** Channel */
            channel: string;
            /** Detection Max Side Px */
            detection_max_side_px?: number | null;
            detector?: components["schemas"]["NuclearDetectorSpec"];
        };
        /** DraftNucleolarProcessing */
        DraftNucleolarProcessing: {
            /** Channel */
            channel: string;
            /** Detector */
            detector: components["schemas"]["NucleolarDetectorV11"] | components["schemas"]["NucleolarDetectorV20"] | components["schemas"]["NucleolarDetectorV21"] | components["schemas"]["NclObjectDetector"] | components["schemas"]["CellposeDetectorSpec"] | components["schemas"]["NclCellposeDetectorSpec"] | components["schemas"]["NclParentCellposeDetectorSpec"];
        };
        /**
         * DraftProcessing
         * @description Registered execution settings only; not code, masks or biological confirmations.
         */
        DraftProcessing: {
            /**
             * Version
             * @default 1.0.0
             * @constant
             */
            version: "1.0.0";
            nuclei: components["schemas"]["DraftNuclearProcessing"] | null;
            nucleoli: components["schemas"]["DraftNucleolarProcessing"] | null;
            signal: components["schemas"]["DraftSignalProcessing"] | null;
            cells?: components["schemas"]["DraftCellProcessing"] | null;
        };
        /** DraftSignalProcessing */
        DraftSignalProcessing: {
            /** Channel */
            channel: string;
            detector: components["schemas"]["SignalDetectorSpec"];
        };
        /** DraftStatistics */
        DraftStatistics: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "descriptive" | "comparison" | "association";
            /** Test */
            test: ("welch-t" | "paired-t" | "mann-whitney-u" | "wilcoxon") | null;
            /** Omnibus */
            omnibus: ("welch-anova" | "kruskal-wallis") | null;
            /** Association */
            association: ("pearson" | "spearman") | null;
            x?: components["schemas"]["DraftMetric"] | null;
            y?: components["schemas"]["DraftMetric"] | null;
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
        /**
         * ExploratoryGfpGateFilter
         * @description Nuclear-object mean gate; thresholds never classify individual image pixels.
         */
        ExploratoryGfpGateFilter: {
            /**
             * Version
             * @constant
             */
            version: "1.1.0";
            /**
             * Gate Protocol
             * @constant
             */
            gate_protocol: "gfp-gate/3.0.0";
            /** Gfp Channel Id */
            gfp_channel_id: string;
            /**
             * Method
             * @enum {string}
             */
            method: "manual" | "batch_otsu";
            /**
             * Threshold
             * @default null
             */
            threshold: number | null;
            /**
             * Values
             * @default raw
             * @enum {string}
             */
            values: "raw" | "corrected";
            /**
             * Unit
             * @default nucleus
             * @enum {string}
             */
            unit: "nucleus" | "cell_roi";
            /**
             * Keep
             * @enum {string}
             */
            keep: "positive" | "negative";
        };
        /** FieldLinkWrite */
        FieldLinkWrite: {
            /** Version */
            version: number;
            /** Selection Version */
            selection_version: number;
            /**
             * Kind
             * @enum {string}
             */
            kind: "analysis" | "reference";
            /** Reference For Field Id */
            reference_for_field_id?: string | null;
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
        /**
         * FigureAxes
         * @description Versioned display scales and scatter X bounds; never transform source values.
         */
        FigureAxes: {
            /**
             * Version
             * @constant
             */
            version: "1.0.0";
            /**
             * X Scale
             * @default linear
             * @enum {string}
             */
            x_scale: "linear" | "log10" | "log2";
            /**
             * Y Scale
             * @default linear
             * @enum {string}
             */
            y_scale: "linear" | "log10" | "log2";
            /**
             * X Min
             * @default null
             */
            x_min: number | null;
            /**
             * X Max
             * @default null
             */
            x_max: number | null;
            /**
             * X Tick Step
             * @default null
             */
            x_tick_step: number | null;
        };
        /** FigureDraft */
        FigureDraft: {
            /**
             * Metric
             * @default area_px
             */
            metric: ("area_px" | "area_um2" | "mean" | "median" | "integrated" | "mean_corrected" | "median_corrected" | "integrated_corrected") | ("ncl_nucleus_mean" | "ncl_nucleus_median" | "ncl_nucleus_integrated" | "ncl_nucleus_mean_corrected" | "ncl_nucleus_median_corrected" | "ncl_nucleus_integrated_corrected" | "ncl_nucleoli_mean" | "ncl_nucleoli_median" | "ncl_nucleoli_integrated" | "ncl_nucleoli_mean_corrected" | "ncl_nucleoli_median_corrected" | "ncl_nucleoli_integrated_corrected" | "ncl_nucleoplasm_mean" | "ncl_nucleoplasm_median" | "ncl_nucleoplasm_integrated" | "ncl_nucleoplasm_mean_corrected" | "ncl_nucleoplasm_median_corrected" | "ncl_nucleoplasm_integrated_corrected" | "gfp_mean" | "gfp_median" | "gfp_integrated" | "gfp_mean_corrected" | "gfp_median_corrected" | "gfp_integrated_corrected" | "nucleus_area_px" | "nucleus_area_um2" | "nucleolar_area_px" | "nucleolar_area_um2" | "nucleoplasm_area_px" | "nucleoplasm_area_um2" | "nucleolar_count" | "nucleolar_area_fraction" | "ncl_nucleoplasm_over_nucleoli" | "ncl_log2_nucleoplasm_over_nucleoli" | "ncl_legacy_release");
            /** Channel Id */
            channel_id?: string | null;
            /** Plot */
            plot?: components["schemas"]["CommonComparisonPlot"] | components["schemas"]["AssociationPlot"];
        };
        /** FigureRenderRequest */
        FigureRenderRequest: {
            /** Plot */
            plot: {
                [key: string]: unknown;
            };
            /** Request Id */
            request_id: string;
        };
        /**
         * FigureStyle
         * @description Presentation-only extension; omitted style retains historical rendering.
         */
        FigureStyle: {
            /**
             * Version
             * @constant
             */
            version: "1.0.0";
            /** Series Colors */
            series_colors?: {
                [key: string]: string;
            };
            /**
             * Show Legend
             * @default true
             */
            show_legend: boolean;
        };
        /** GfpGateField */
        GfpGateField: {
            /** Field Id */
            field_id: string;
            /** Revision Id */
            revision_id: string;
            /**
             * Control
             * @default false
             */
            control: boolean;
        };
        /**
         * GfpGateFilter
         * @description Optional nucleus filter 1.0.0: keep nuclei by the negative-control GFP gate (gfp-gate/2.0.0).
         *
         *     The percentile is the researcher's recorded choice (50 to <100); it is never
         *     searched or tuned by the software. Control fields supply the per-date
         *     threshold and are never compared observations.
         */
        GfpGateFilter: {
            /**
             * Version
             * @constant
             */
            version: "1.0.0";
            /**
             * Gate Protocol
             * @constant
             */
            gate_protocol: "gfp-gate/2.0.0";
            /** Gfp Channel Id */
            gfp_channel_id: string;
            /**
             * Percentile
             * @default 99
             */
            percentile: number;
            /** Control Field Ids */
            control_field_ids: string[];
            /**
             * Keep
             * @enum {string}
             */
            keep: "positive" | "negative";
        };
        /** GfpGateRequest */
        GfpGateRequest: {
            /** Gfp Channel Id */
            gfp_channel_id: string;
            /**
             * Percentile
             * @default 99
             */
            percentile: number;
            /** Fields */
            fields: components["schemas"]["GfpGateField"][];
            /**
             * Method
             * @default negative_control
             * @enum {string}
             */
            method: "negative_control" | "manual" | "batch_otsu";
            /** Threshold */
            threshold?: number | null;
            /**
             * Values
             * @default raw
             * @enum {string}
             */
            values: "raw" | "corrected";
            /**
             * Unit
             * @default nucleus
             * @enum {string}
             */
            unit: "nucleus" | "cell_roi";
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
            kind: "analysis" | "statistics" | "table-statistics" | "export" | "figure-render" | "publication-package";
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
            analysis_mode?: ("experimental-unit" | "exploratory" | "descriptive" | "region-experimental-unit" | "region-association") | null;
            /** Analysis Version */
            analysis_version?: string | null;
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
        /** NclCellposeDetectorSpec */
        NclCellposeDetectorSpec: {
            /**
             * Model
             * @default cpsam_v2
             * @constant
             */
            model: "cpsam_v2";
            /**
             * Model Sha256
             * @default 0f1cc3f7ecdd8a037a57c6c48d9d8921391be4cbce3fa9f13c3e3a2e1253c667
             * @constant
             */
            model_sha256: "0f1cc3f7ecdd8a037a57c6c48d9d8921391be4cbce3fa9f13c3e3a2e1253c667";
            /** Diameter Px */
            diameter_px?: number | null;
            /**
             * Normalization Percentile Low
             * @default 1
             */
            normalization_percentile_low: number;
            /**
             * Normalization Percentile High
             * @default 99
             */
            normalization_percentile_high: number;
            /**
             * Flow Threshold
             * @default 0.4
             */
            flow_threshold: number;
            /**
             * Cellprob Threshold
             * @default 0
             */
            cellprob_threshold: number;
            /**
             * Minimum Area Px
             * @default 15
             */
            minimum_area_px: number;
            /**
             * Maximum Size Fraction
             * @default 1
             */
            maximum_size_fraction: number;
            /** Iterations */
            iterations?: number | null;
            /**
             * Batch Size
             * @default 1
             */
            batch_size: number;
            /**
             * Compute Device
             * @default cpu
             * @enum {string}
             */
            compute_device: "cpu" | "auto" | "cuda";
            /**
             * Engine
             * @default cellpose-sam-ncl
             * @constant
             */
            engine: "cellpose-sam-ncl";
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            protocol_version: "4.1.0";
            /**
             * Smoothing Sigma Px
             * @default 0.9
             */
            smoothing_sigma_px: number;
            /**
             * Background Radius Px
             * @default 10
             */
            background_radius_px: number;
        };
        /** NclObjectDetector */
        NclObjectDetector: {
            /**
             * Engine
             * @default cytellect-ncl-objects
             * @constant
             */
            engine: "cytellect-ncl-objects";
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            protocol_version: "3.0.0";
            /**
             * Smoothing Sigma Px
             * @default 0.9
             */
            smoothing_sigma_px: number;
            /**
             * Background Radius Px
             * @default 10
             */
            background_radius_px: number;
            /**
             * Coarse Sigma Px
             * @default 1.5
             */
            coarse_sigma_px: number;
            /**
             * Core Contrast
             * @default 36
             */
            core_contrast: number;
            /**
             * Core Coarse Contrast
             * @default 27
             */
            core_coarse_contrast: number;
            /**
             * Minimum Core Area Px
             * @default 6
             */
            minimum_core_area_px: number;
            /**
             * Local Crop Radius Px
             * @default 24
             */
            local_crop_radius_px: number;
            /**
             * Background Inner Radius Px
             * @default 12
             */
            background_inner_radius_px: number;
            /**
             * Background Outer Radius Px
             * @default 22
             */
            background_outer_radius_px: number;
            /**
             * Background Signal Floor
             * @default 15
             */
            background_signal_floor: number;
            /**
             * Minimum Background Pixels
             * @default 40
             */
            minimum_background_pixels: number;
            /**
             * Peak Radius Px
             * @default 2
             */
            peak_radius_px: number;
            /**
             * Minimum Peak Difference
             * @default 30
             */
            minimum_peak_difference: number;
            /**
             * Minimum Peak Ratio
             * @default 1.6
             */
            minimum_peak_ratio: number;
            /**
             * Boundary Fraction
             * @default 0.5
             */
            boundary_fraction: number;
            /**
             * Minimum Area Px
             * @default 28
             */
            minimum_area_px: number;
            /**
             * Maximum Area Px
             * @default 800
             */
            maximum_area_px: number | null;
            /**
             * Minimum Solidity
             * @default 0.8
             */
            minimum_solidity: number;
            /**
             * Minimum Circularity
             * @default 0.5
             */
            minimum_circularity: number;
            /**
             * Hole Fill Max Px
             * @default 64
             */
            hole_fill_max_px: number;
            /**
             * Overlap Suppression Fraction
             * @default 0.5
             */
            overlap_suppression_fraction: number;
        };
        /**
         * NclParentCellposeDetectorSpec
         * @description Parent-conditioned NCL copy; 4.0/4.1 replay is deliberately unchanged.
         */
        NclParentCellposeDetectorSpec: {
            /**
             * Model
             * @default cpsam_v2
             * @constant
             */
            model: "cpsam_v2";
            /**
             * Model Sha256
             * @default 0f1cc3f7ecdd8a037a57c6c48d9d8921391be4cbce3fa9f13c3e3a2e1253c667
             * @constant
             */
            model_sha256: "0f1cc3f7ecdd8a037a57c6c48d9d8921391be4cbce3fa9f13c3e3a2e1253c667";
            /** Diameter Px */
            diameter_px?: number | null;
            /**
             * Normalization Percentile Low
             * @default 1
             */
            normalization_percentile_low: number;
            /**
             * Normalization Percentile High
             * @default 99
             */
            normalization_percentile_high: number;
            /**
             * Flow Threshold
             * @default 0.4
             */
            flow_threshold: number;
            /**
             * Cellprob Threshold
             * @default 0
             */
            cellprob_threshold: number;
            /**
             * Minimum Area Px
             * @default 15
             */
            minimum_area_px: number;
            /**
             * Maximum Size Fraction
             * @default 1
             */
            maximum_size_fraction: number;
            /** Iterations */
            iterations?: number | null;
            /**
             * Batch Size
             * @default 1
             */
            batch_size: number;
            /**
             * Compute Device
             * @default cpu
             * @enum {string}
             */
            compute_device: "cpu" | "auto" | "cuda";
            /**
             * Engine
             * @default cellpose-sam-ncl-parent
             * @constant
             */
            engine: "cellpose-sam-ncl-parent";
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            protocol_version: "4.2.0" | "4.2.1" | "4.3.0";
            /**
             * Smoothing Sigma Px
             * @default 0.9
             */
            smoothing_sigma_px: number;
            /**
             * Parent Background Percentile
             * @default 75
             */
            parent_background_percentile: number;
            /**
             * Nuclear Diameter Fraction
             * @default 0.25
             */
            nuclear_diameter_fraction: number;
            /**
             * Crop Padding Px
             * @default 32
             */
            crop_padding_px: number;
            /**
             * Minimum Contrast Snr
             * @default 5
             */
            minimum_contrast_snr: number;
            /**
             * Local Background Radius Px
             * @default 8
             */
            local_background_radius_px: number;
            /**
             * Maximum Nuclear Coverage
             * @default 0.5
             */
            maximum_nuclear_coverage: number;
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
        /** NucleolarDefinitionDraft */
        NucleolarDefinitionDraft: {
            /**
             * Source
             * @default dapi_poor
             * @enum {string}
             */
            source: "dapi_poor" | "marker" | "ncl";
            /**
             * Marker
             * @default
             */
            marker: string;
            /** Pixelum */
            pixelUm?: number | null;
            /**
             * Relative
             * @default 0.7
             */
            relative: number;
            /** Algorithm */
            algorithm?: ("cellpose" | "objects" | "legacy") | null;
        };
        /** NucleolarDetectorSpec */
        NucleolarDetectorSpec: {
            /**
             * Engine
             * @default fiji-nucleolar-compartments
             * @constant
             */
            engine: "fiji-nucleolar-compartments";
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            protocol_version: "1.0.0";
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
        };
        /**
         * NucleolarDetectorV11
         * @description Opt-in threshold/area controls; the saved 1.0 detector remains unchanged.
         */
        NucleolarDetectorV11: {
            /**
             * Engine
             * @default fiji-nucleolar-compartments
             * @constant
             */
            engine: "fiji-nucleolar-compartments";
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            protocol_version: "1.1.0";
            /**
             * Threshold Method
             * @default otsu
             * @enum {string}
             */
            threshold_method: "otsu" | "manual";
            /** Threshold */
            threshold?: number | null;
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
            /** Maximum Area Px */
            maximum_area_px?: number | null;
            /**
             * Split Touching
             * @default false
             */
            split_touching: boolean;
        };
        /** NucleolarDetectorV20 */
        NucleolarDetectorV20: {
            /**
             * Engine
             * @default cytellect-nucleolar-v2
             * @constant
             */
            engine: "cytellect-nucleolar-v2";
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            protocol_version: "2.0.0";
            /**
             * Source
             * @default dapi_poor
             * @enum {string}
             */
            source: "dapi_poor" | "marker";
            /**
             * Smoothing Sigma Px
             * @default 2
             */
            smoothing_sigma_px: number;
            /**
             * Rim Exclusion Px
             * @default 4
             */
            rim_exclusion_px: number;
            /**
             * Relative Threshold
             * @default 0.7
             */
            relative_threshold: number;
            /**
             * Marker Fraction
             * @default 0.4
             */
            marker_fraction: number;
            /**
             * Background Radius Px
             * @default 10
             */
            background_radius_px: number;
            /**
             * Minimum Area Px
             * @default 4
             */
            minimum_area_px: number;
            /** Maximum Area Px */
            maximum_area_px?: number | null;
            /**
             * Minimum Solidity
             * @default 0.6
             */
            minimum_solidity: number;
        };
        /**
         * NucleolarDetectorV21
         * @description Marker-only revision: the recorded smoothing sigma is the effective value.
         */
        NucleolarDetectorV21: {
            /**
             * Engine
             * @default cytellect-nucleolar-v2
             * @constant
             */
            engine: "cytellect-nucleolar-v2";
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            protocol_version: "2.1.0";
            /**
             * Source
             * @default marker
             * @constant
             */
            source: "marker";
            /**
             * Smoothing Sigma Px
             * @default 0.7
             */
            smoothing_sigma_px: number;
            /**
             * Rim Exclusion Px
             * @default 4
             */
            rim_exclusion_px: number;
            /**
             * Relative Threshold
             * @default 0.7
             */
            relative_threshold: number;
            /**
             * Marker Fraction
             * @default 0.4
             */
            marker_fraction: number;
            /**
             * Background Radius Px
             * @default 10
             */
            background_radius_px: number;
            /**
             * Minimum Area Px
             * @default 4
             */
            minimum_area_px: number;
            /** Maximum Area Px */
            maximum_area_px?: number | null;
            /**
             * Minimum Solidity
             * @default 0.6
             */
            minimum_solidity: number;
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
        /**
         * ObservedChannelSpec
         * @description Recorded import evidence is not a human acquisition confirmation.
         */
        ObservedChannelSpec: {
            /** Channel Id */
            channel_id: string;
            /** Label */
            label: string;
            /** Stain */
            stain?: string | null;
            /** Acquisition Saturation Value */
            acquisition_saturation_value?: number | null;
            /**
             * Acquisition Saturation Confirmed
             * @default false
             */
            acquisition_saturation_confirmed: boolean;
            /**
             * Identity Source
             * @enum {string}
             */
            identity_source: "filename" | "ome_metadata" | "user_entered" | "unresolved";
        };
        /** PagedDescriptiveRequest */
        PagedDescriptiveRequest: {
            /**
             * Mode
             * @constant
             */
            mode: "descriptive";
            /** Selection */
            selection: components["schemas"]["LegacySelection"] | components["schemas"]["RegionSelection"] | components["schemas"]["NumericalSelection"] | components["schemas"]["CompartmentSummarySelection"];
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
            style?: components["schemas"]["FigureStyle"] | null;
            axes?: components["schemas"]["FigureAxes"] | null;
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
            /** Y Min */
            y_min?: number | null;
            /** Y Max */
            y_max?: number | null;
            /** Y Tick Step */
            y_tick_step?: number | null;
            /** Point Size */
            point_size?: number | null;
        };
        /** ProposalChannelLink */
        ProposalChannelLink: {
            /** Token */
            token: string;
            /** Channel Id */
            channel_id: string;
            /** Stain */
            stain: string | null;
        };
        /** ProposalDraft */
        ProposalDraft: {
            /**
             * Recipe
             * @enum {string}
             */
            recipe: "nuclear-intensity" | "nuclear-ncl" | "supplied-regions" | "measured-table" | "none";
            /** Channels */
            channels: components["schemas"]["DraftChannel"][];
            /** Metrics */
            metrics: components["schemas"]["DraftMetric"][];
            statistics: components["schemas"]["DraftStatistics"];
            /** Additional Analyses */
            additional_analyses?: components["schemas"]["DraftStatistics"][];
            /** Figures */
            figures: components["schemas"]["DraftFigure"][];
            /** Missing Information */
            missing_information: string[];
            /** Reference Ids */
            reference_ids: ("senft-2023" | "kodiha-2011" | "waters-2009" | "lazic-2018" | "lord-2020" | "schmied-2024")[];
            /** Rationale */
            rationale: string;
            processing?: components["schemas"]["DraftProcessing"] | null;
            background?: components["schemas"]["DraftBackground"] | null;
            gfp_selection?: components["schemas"]["DraftGfpSelection"] | null;
        };
        /**
         * ProposalDraftRequest
         * @description The only researcher input: an optional goal in their own words.
         *
         *     `transmission_confirmed` records that the researcher has seen what is sent
         *     and enabled it (L03). The UI asks once and remembers; without it nothing
         *     leaves the PC.
         */
        ProposalDraftRequest: {
            /**
             * Goal
             * @default
             */
            goal: string;
            /**
             * Transmission Confirmed
             * @default false
             */
            transmission_confirmed: boolean;
            /**
             * Retry Failed
             * @default false
             */
            retry_failed: boolean;
            /** Field Id */
            field_id?: string | null;
            /** Current Processing */
            current_processing?: {
                [key: string]: unknown;
            } | null;
            /**
             * Previous Goal
             * @default
             */
            previous_goal: string;
            /** Previous Proposal */
            previous_proposal?: {
                [key: string]: unknown;
            } | null;
        };
        /** ProposalDraftResponse */
        ProposalDraftResponse: {
            proposal: components["schemas"]["ValidatedProposal"];
            /** Channels */
            channels: components["schemas"]["ProposalChannelLink"][];
        };
        /** PublicationPackageRequest */
        PublicationPackageRequest: {
            /** Analysis Job Id */
            analysis_job_id: string;
            /** Request Id */
            request_id: string;
        };
        /** RawBackgroundProvenance */
        RawBackgroundProvenance: {
            /**
             * Status
             * @default not_established
             * @constant
             */
            status: "not_established";
            /**
             * Reason
             * @default raw_measurement_only
             * @constant
             */
            reason: "raw_measurement_only";
        };
        /** RawIntensityPolicy */
        RawIntensityPolicy: {
            /**
             * Version
             * @constant
             */
            version: "1.1.0";
            /**
             * Mode
             * @constant
             */
            mode: "raw_intensity";
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
            /** Measurement */
            measurement?: components["schemas"]["RegionMeasurementPolicy"] | components["schemas"]["RawIntensityPolicy"] | components["schemas"]["AutomaticBackgroundPolicy"] | null;
            /** Recipe */
            recipe: components["schemas"]["RegionRecipe"] | components["schemas"]["RegionNuclearRecipe"] | components["schemas"]["AdoptedNuclearRecipe"] | components["schemas"]["ScaledNuclearRecipe"] | components["schemas"]["AutoScaledNuclearRecipe"] | components["schemas"]["RegionSignalRecipe"] | components["schemas"]["RegionCompartmentRecipe"] | components["schemas"]["RegionCellposeRecipe"];
            /** Backgrounds */
            backgrounds?: {
                [key: string]: {
                    [key: string]: components["schemas"]["RegionBackground"];
                };
            };
            /** Confirmed Channel Ids */
            confirmed_channel_ids?: string[];
            /** Exclusions */
            exclusions?: components["schemas"]["RegionExclusion"][];
        };
        /** RegionAssociationRequest */
        RegionAssociationRequest: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            mode: "region-association";
            /**
             * Version
             * @enum {string}
             */
            version: "1.0.0" | "1.1.0";
            x_selection: components["schemas"]["RegionSelection"];
            y_selection: components["schemas"]["RegionSelection"];
            design: components["schemas"]["ComparisonDesign"];
            /** Conditions */
            conditions: string[];
            acquisition_review: components["schemas"]["AcquisitionReview"];
            /**
             * Missingness Confirmed
             * @constant
             */
            missingness_confirmed: true;
            /**
             * Method
             * @enum {string}
             */
            method: "pearson" | "spearman";
            /**
             * Scope
             * @default per-condition
             * @enum {string}
             */
            scope: "per-condition" | "pooled";
            /**
             * Pooling Confirmed
             * @default false
             */
            pooling_confirmed: boolean;
            /**
             * Aggregation
             * @default field-median_sample-mean_unit-mean-v1
             * @constant
             */
            aggregation: "field-median_sample-mean_unit-mean-v1";
            /**
             * Missingness Policy
             * @default require-matched-unexcluded-units-v1
             * @constant
             */
            missingness_policy: "require-matched-unexcluded-units-v1";
            plot?: components["schemas"]["AssociationPlot"];
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
        /** RegionCellposeRecipe */
        RegionCellposeRecipe: {
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
            version: "1.8.0";
            /**
             * Region Set Id
             * @default cell
             * @constant
             */
            region_set_id: "cell";
            /**
             * Label
             * @default 細胞
             */
            label: string;
            /**
             * Source
             * @default cellpose_cell
             * @constant
             */
            source: "cellpose_cell";
            /** Defining Channel Id */
            defining_channel_id: string;
            detector?: components["schemas"]["CellposeDetectorSpec"];
            /** Nuclear Revision Id */
            nuclear_revision_id?: string | null;
            /** Nuclear Channel Id */
            nuclear_channel_id?: string | null;
        };
        /** RegionCohortRequest */
        RegionCohortRequest: {
            /** Sources */
            sources: components["schemas"]["CohortSource"][];
            /** Metadata */
            metadata: {
                [key: string]: components["schemas"]["RegionFieldMetadata"];
            };
            /** Expected Active Revision Id */
            expected_active_revision_id: string | null;
            workspace_selection?: components["schemas"]["WorkspaceSelection"] | null;
        };
        /** RegionComparisonPlot */
        RegionComparisonPlot: {
            style?: components["schemas"]["FigureStyle"] | null;
            axes?: components["schemas"]["FigureAxes"] | null;
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
            /** Y Min */
            y_min?: number | null;
            /** Y Max */
            y_max?: number | null;
            /** Y Tick Step */
            y_tick_step?: number | null;
            /** Point Size */
            point_size?: number | null;
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
        /** RegionComparisonRequestV2 */
        RegionComparisonRequestV2: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            mode: "region-experimental-unit";
            /**
             * Version
             * @constant
             */
            version: "2.0.0";
            /** Selection */
            selection: components["schemas"]["RegionSelection"] | components["schemas"]["CompartmentSummarySelection"];
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
            plot?: components["schemas"]["CommonComparisonPlot"];
            /**
             * Test
             * @enum {string}
             */
            test: "welch-t" | "paired-t" | "mann-whitney-u" | "wilcoxon";
            /** Omnibus */
            omnibus?: ("welch-anova" | "kruskal-wallis") | null;
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
        /** RegionCompartmentRecipe */
        RegionCompartmentRecipe: {
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
            version: "1.4.0";
            /** Region Set Id */
            region_set_id: string;
            /** Label */
            label: string;
            /**
             * Source
             * @default fiji_nuclear_compartment
             * @constant
             */
            source: "fiji_nuclear_compartment";
            /**
             * Compartment
             * @enum {string}
             */
            compartment: "nucleoli" | "nucleoplasm";
            /** Nuclear Revision Id */
            nuclear_revision_id: string;
            /** Nuclear Channel Id */
            nuclear_channel_id: string;
            /** Defining Channel Id */
            defining_channel_id: string;
            /** Detector */
            detector?: components["schemas"]["NucleolarDetectorSpec"] | components["schemas"]["NucleolarDetectorV11"] | components["schemas"]["NucleolarDetectorV20"] | components["schemas"]["NucleolarDetectorV21"] | components["schemas"]["NclObjectDetector"] | components["schemas"]["CellposeDetectorSpec"] | components["schemas"]["NclCellposeDetectorSpec"] | components["schemas"]["NclParentCellposeDetectorSpec"];
            /** Nucleolar Revision Id */
            nucleolar_revision_id?: string | null;
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
            source: "manual" | "imported" | "stardist_nuclear" | "fiji_positive_regions" | "fiji_nuclear_compartment" | "cellpose_cell";
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
             * Input Mode
             * @default native
             * @enum {string}
             */
            input_mode: "native" | "display-rgb";
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
            channels: (components["schemas"]["ChannelSpec"] | components["schemas"]["ObservedChannelSpec"])[];
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
        /** RegionMeasurementRowV3 */
        RegionMeasurementRowV3: {
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
            mean_corrected: null;
            /** Median Corrected */
            median_corrected: null;
            /** Integrated Corrected */
            integrated_corrected: null;
            /** Intensity Missing Reason */
            intensity_missing_reason?: null;
            /** Storage Limit Fraction */
            storage_limit_fraction: number;
            /** Storage Limit Missing Reason */
            storage_limit_missing_reason?: null;
            /** Acquisition Saturation Fraction */
            acquisition_saturation_fraction: number | null;
            /** Acquisition Saturation Missing Reason */
            acquisition_saturation_missing_reason: "acquisition_limit_unknown" | null;
            /** Touches Border */
            touches_border: boolean;
            /**
             * Correction Missing Reason
             * @default background_not_established
             * @constant
             */
            correction_missing_reason: "background_not_established";
        };
        /** RegionMeasurementRowV4 */
        RegionMeasurementRowV4: {
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
            mean_corrected: number | null;
            /** Median Corrected */
            median_corrected: number | null;
            /** Integrated Corrected */
            integrated_corrected: number | null;
            /** Intensity Missing Reason */
            intensity_missing_reason?: null;
            /** Storage Limit Fraction */
            storage_limit_fraction: number;
            /** Storage Limit Missing Reason */
            storage_limit_missing_reason?: null;
            /** Acquisition Saturation Fraction */
            acquisition_saturation_fraction: number | null;
            /** Acquisition Saturation Missing Reason */
            acquisition_saturation_missing_reason: "acquisition_limit_unknown" | null;
            /** Touches Border */
            touches_border: boolean;
            /** Correction Missing Reason */
            correction_missing_reason: ("automatic_background_insufficient_tiles" | "automatic_background_insufficient_coverage") | null;
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
        /** RegionMeasurementTableV3 */
        RegionMeasurementTableV3: {
            /**
             * Protocol Version
             * @default 3.0.0
             * @constant
             */
            protocol_version: "3.0.0";
            measurement: components["schemas"]["RawIntensityPolicy"];
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
            channel_provenance: components["schemas"]["ChannelProvenanceV3"][];
            /** Rows */
            rows: components["schemas"]["RegionMeasurementRowV3"][];
        };
        /** RegionMeasurementTableV4 */
        RegionMeasurementTableV4: {
            /**
             * Protocol Version
             * @default 4.0.0
             * @constant
             */
            protocol_version: "4.0.0";
            measurement: components["schemas"]["AutomaticBackgroundPolicy"];
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
            channel_provenance: components["schemas"]["ChannelProvenanceV4"][];
            /** Rows */
            rows: components["schemas"]["RegionMeasurementRowV4"][];
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
            recipe: components["schemas"]["RegionRecipe"] | components["schemas"]["RegionNuclearRecipe"] | components["schemas"]["AdoptedNuclearRecipe"] | components["schemas"]["ScaledNuclearRecipe"] | components["schemas"]["AutoScaledNuclearRecipe"] | components["schemas"]["RegionSignalRecipe"] | components["schemas"]["RegionCompartmentRecipe"] | components["schemas"]["RegionCellposeRecipe"];
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
            recipe: components["schemas"]["RegionRecipe"] | components["schemas"]["RegionNuclearRecipe"] | components["schemas"]["AdoptedNuclearRecipe"] | components["schemas"]["ScaledNuclearRecipe"] | components["schemas"]["AutoScaledNuclearRecipe"] | components["schemas"]["RegionSignalRecipe"] | components["schemas"]["RegionCompartmentRecipe"] | components["schemas"]["RegionCellposeRecipe"];
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
        /** RegionReportV3 */
        RegionReportV3: {
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
            protocol_version: "3.0.0";
            measurement: components["schemas"]["RawIntensityPolicy"];
            /** Revision Id */
            revision_id: string;
            /** Recipe */
            recipe: components["schemas"]["RegionRecipe"] | components["schemas"]["RegionNuclearRecipe"] | components["schemas"]["AdoptedNuclearRecipe"] | components["schemas"]["ScaledNuclearRecipe"] | components["schemas"]["AutoScaledNuclearRecipe"] | components["schemas"]["RegionSignalRecipe"] | components["schemas"]["RegionCompartmentRecipe"] | components["schemas"]["RegionCellposeRecipe"];
            /** Field Tables */
            field_tables: {
                [key: string]: components["schemas"]["RegionMeasurementTableV3"];
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
         * RegionReportV4
         * @description Raw values plus corrections from automatic, unconfirmed background candidates.
         */
        RegionReportV4: {
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
            protocol_version: "4.0.0";
            measurement: components["schemas"]["AutomaticBackgroundPolicy"];
            /** Revision Id */
            revision_id: string;
            /** Recipe */
            recipe: components["schemas"]["RegionRecipe"] | components["schemas"]["RegionNuclearRecipe"] | components["schemas"]["AdoptedNuclearRecipe"] | components["schemas"]["ScaledNuclearRecipe"] | components["schemas"]["AutoScaledNuclearRecipe"] | components["schemas"]["RegionSignalRecipe"] | components["schemas"]["RegionCompartmentRecipe"] | components["schemas"]["RegionCellposeRecipe"];
            /** Field Tables */
            field_tables: {
                [key: string]: components["schemas"]["RegionMeasurementTableV4"];
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
            /** Gfp Gate */
            gfp_gate?: components["schemas"]["GfpGateFilter"] | components["schemas"]["ExploratoryGfpGateFilter"] | null;
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
            source: "manual" | "imported" | "stardist_nuclear" | "fiji_positive_regions" | "fiji_nuclear_compartment" | "cellpose_cell";
            /** Defining Channel Id */
            defining_channel_id?: string | null;
        };
        /**
         * RegionSignalRecipe
         * @description Exploratory signal-positive areas; never implicitly nuclei or nucleoli.
         */
        RegionSignalRecipe: {
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
            version: "1.3.0";
            /** Region Set Id */
            region_set_id: string;
            /** Label */
            label: string;
            /**
             * Source
             * @default fiji_positive_regions
             * @constant
             */
            source: "fiji_positive_regions";
            /** Defining Channel Id */
            defining_channel_id: string;
            detector?: components["schemas"]["SignalDetectorSpec"];
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
        /**
         * RuntimeSettingsDraft
         * @description Names deliberately match the workspace runtime; null keeps versioned detector defaults.
         */
        RuntimeSettingsDraft: {
            /** Nuclearmaxside */
            nuclearMaxSide?: number | null;
            /**
             * Nuclearprobability
             * @default 0.5
             */
            nuclearProbability: number;
            /**
             * Nuclearnms
             * @default 0.3
             */
            nuclearNms: number;
            nucleolarDefinition?: components["schemas"]["NucleolarDefinitionDraft"];
            cellDefinition?: components["schemas"]["CellDefinitionDraft"];
            /** Nucleolarsigma */
            nucleolarSigma?: number | null;
            /** Nucleolarrim */
            nucleolarRim?: number | null;
            /** Nucleolarminimumarea */
            nucleolarMinimumArea?: number | null;
            /** Nucleolarmaximumarea */
            nucleolarMaximumArea?: number | null;
            /**
             * Background
             * @default raw
             * @enum {string}
             */
            background: "raw" | "automatic" | "confirmed_roi";
        };
        /** SavedCellProcessing */
        SavedCellProcessing: {
            /** Channel */
            channel: string;
            detector?: components["schemas"]["CellposeDetectorSpec"];
        };
        /** SavedDraftFigure */
        SavedDraftFigure: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "field-distribution" | "unit-comparison" | "paired" | "association-scatter";
            /**
             * Metric
             * @enum {string}
             */
            metric: "area" | "mean_raw" | "integral_raw" | "mean_corrected" | "integral_corrected" | "ncl_log2_nucleoplasm_over_nucleoli" | "nucleolar_area_fraction" | "nucleolar_count";
            /** Channel */
            channel: string | null;
            /** Region */
            region?: ("nucleus" | "nucleoli" | "nucleoplasm" | "supplied") | null;
            /**
             * Analysis Index
             * @default 0
             */
            analysis_index: number;
        };
        /** SavedDraftMetric */
        SavedDraftMetric: {
            /** Metric */
            metric: ("area" | "mean_raw" | "integral_raw" | "mean_corrected" | "integral_corrected" | "ncl_log2_nucleoplasm_over_nucleoli" | "nucleolar_area_fraction" | "nucleolar_count") | ("area_px" | "area_um2" | "mean" | "median" | "integrated" | "mean_corrected" | "median_corrected" | "integrated_corrected") | ("ncl_nucleus_mean" | "ncl_nucleus_median" | "ncl_nucleus_integrated" | "ncl_nucleus_mean_corrected" | "ncl_nucleus_median_corrected" | "ncl_nucleus_integrated_corrected" | "ncl_nucleoli_mean" | "ncl_nucleoli_median" | "ncl_nucleoli_integrated" | "ncl_nucleoli_mean_corrected" | "ncl_nucleoli_median_corrected" | "ncl_nucleoli_integrated_corrected" | "ncl_nucleoplasm_mean" | "ncl_nucleoplasm_median" | "ncl_nucleoplasm_integrated" | "ncl_nucleoplasm_mean_corrected" | "ncl_nucleoplasm_median_corrected" | "ncl_nucleoplasm_integrated_corrected" | "gfp_mean" | "gfp_median" | "gfp_integrated" | "gfp_mean_corrected" | "gfp_median_corrected" | "gfp_integrated_corrected" | "nucleus_area_px" | "nucleus_area_um2" | "nucleolar_area_px" | "nucleolar_area_um2" | "nucleoplasm_area_px" | "nucleoplasm_area_um2" | "nucleolar_count" | "nucleolar_area_fraction" | "ncl_nucleoplasm_over_nucleoli" | "ncl_log2_nucleoplasm_over_nucleoli" | "ncl_legacy_release");
            /** Channel */
            channel: string | null;
            /** Region */
            region?: ("nucleus" | "nucleoli" | "nucleoplasm" | "supplied") | null;
        };
        /** SavedDraftStatistics */
        SavedDraftStatistics: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "descriptive" | "comparison" | "association";
            /** Test */
            test: ("welch-t" | "paired-t" | "mann-whitney-u" | "wilcoxon") | null;
            /** Omnibus */
            omnibus: ("welch-anova" | "kruskal-wallis") | null;
            /** Association */
            association: ("pearson" | "spearman") | null;
            x?: components["schemas"]["SavedDraftMetric"] | null;
            y?: components["schemas"]["SavedDraftMetric"] | null;
        };
        /** SavedNuclearProcessing */
        SavedNuclearProcessing: {
            /** Channel */
            channel: string;
            /** Detection Max Side Px */
            detection_max_side_px?: number | null;
            detector?: components["schemas"]["NuclearDetectorSpec"];
        };
        /** SavedNucleolarProcessing */
        SavedNucleolarProcessing: {
            /** Channel */
            channel: string;
            /** Detector */
            detector: components["schemas"]["NucleolarDetectorV11"] | components["schemas"]["NucleolarDetectorV20"] | components["schemas"]["NucleolarDetectorV21"] | components["schemas"]["NclObjectDetector"] | components["schemas"]["CellposeDetectorSpec"] | components["schemas"]["NclCellposeDetectorSpec"] | components["schemas"]["NclParentCellposeDetectorSpec"];
        };
        /** SavedProcessing */
        SavedProcessing: {
            /**
             * Version
             * @default 1.0.0
             * @constant
             */
            version: "1.0.0";
            nuclei: components["schemas"]["SavedNuclearProcessing"] | null;
            nucleoli: components["schemas"]["SavedNucleolarProcessing"] | null;
            signal: components["schemas"]["SavedSignalProcessing"] | null;
            cells?: components["schemas"]["SavedCellProcessing"] | null;
        };
        /** SavedSignalProcessing */
        SavedSignalProcessing: {
            /** Channel */
            channel: string;
            detector: components["schemas"]["SignalDetectorSpec"];
        };
        /** ScaledNuclearRecipe */
        ScaledNuclearRecipe: {
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
            version: "1.5.0";
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
             * Nuclear Role Source
             * @enum {string}
             */
            nuclear_role_source: "recorded_stain" | "user_selected_role";
            /** Detection Max Side Px */
            detection_max_side_px: number;
            detector?: components["schemas"]["NuclearDetectorSpec"];
        };
        /** SignalDetectorSpec */
        SignalDetectorSpec: {
            /**
             * Engine
             * @default fiji-positive-regions
             * @constant
             */
            engine: "fiji-positive-regions";
            /**
             * Protocol Version
             * @default 1.0.0
             * @constant
             */
            protocol_version: "1.0.0";
            /**
             * Threshold Method
             * @enum {string}
             */
            threshold_method: "otsu" | "manual";
            /** Threshold */
            threshold?: number | null;
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
        };
        /** StatisticsDraft */
        StatisticsDraft: {
            method?: components["schemas"]["SavedDraftStatistics"] | null;
            /**
             * Metric
             * @default area_px
             */
            metric: ("area_px" | "area_um2" | "mean" | "median" | "integrated" | "mean_corrected" | "median_corrected" | "integrated_corrected") | ("ncl_nucleus_mean" | "ncl_nucleus_median" | "ncl_nucleus_integrated" | "ncl_nucleus_mean_corrected" | "ncl_nucleus_median_corrected" | "ncl_nucleus_integrated_corrected" | "ncl_nucleoli_mean" | "ncl_nucleoli_median" | "ncl_nucleoli_integrated" | "ncl_nucleoli_mean_corrected" | "ncl_nucleoli_median_corrected" | "ncl_nucleoli_integrated_corrected" | "ncl_nucleoplasm_mean" | "ncl_nucleoplasm_median" | "ncl_nucleoplasm_integrated" | "ncl_nucleoplasm_mean_corrected" | "ncl_nucleoplasm_median_corrected" | "ncl_nucleoplasm_integrated_corrected" | "gfp_mean" | "gfp_median" | "gfp_integrated" | "gfp_mean_corrected" | "gfp_median_corrected" | "gfp_integrated_corrected" | "nucleus_area_px" | "nucleus_area_um2" | "nucleolar_area_px" | "nucleolar_area_um2" | "nucleoplasm_area_px" | "nucleoplasm_area_um2" | "nucleolar_count" | "nucleolar_area_fraction" | "ncl_nucleoplasm_over_nucleoli" | "ncl_log2_nucleoplasm_over_nucleoli" | "ncl_legacy_release");
            /** Channel Id */
            channel_id?: string | null;
            /** X Metric */
            x_metric?: ("area_px" | "area_um2" | "mean" | "median" | "integrated" | "mean_corrected" | "median_corrected" | "integrated_corrected") | null;
            /** X Channel Id */
            x_channel_id?: string | null;
            /** Design */
            design?: ("independent" | "paired") | null;
            /**
             * Unit Definition
             * @default
             */
            unit_definition: string;
            /**
             * Pairing Basis
             * @default
             */
            pairing_basis: string;
            /** Conditions */
            conditions?: string[];
            /** Comparisons */
            comparisons?: string[][];
            /** Field Metadata */
            field_metadata?: {
                [key: string]: components["schemas"]["RegionFieldMetadata"];
            };
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
        /** ValidatedProposal */
        ValidatedProposal: {
            /**
             * Protocol
             * @default 1.1.0
             * @constant
             */
            protocol: "1.1.0";
            /**
             * Origin
             * @default llm-draft
             * @constant
             */
            origin: "llm-draft";
            /**
             * Requires Adoption
             * @default true
             * @constant
             */
            requires_adoption: true;
            draft: components["schemas"]["ProposalDraft"];
            /** Needs Confirmation */
            needs_confirmation: string[];
            /** Model */
            model: string;
            /** Prompt Version */
            prompt_version: string;
            /** Context Sha256 */
            context_sha256: string;
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
        /** WorkspaceRunRequest */
        WorkspaceRunRequest: {
            /** Request Id */
            request_id: string;
            /** Spec Version */
            spec_version: number;
            /**
             * Target
             * @enum {string}
             */
            target: "nuclei" | "nucleoli" | "nucleoplasm" | "cell";
            /**
             * Purpose
             * @default measurement
             * @enum {string}
             */
            purpose: "preview" | "measurement";
            /** Field Ids */
            field_ids: string[];
        };
        /** WorkspaceSelection */
        WorkspaceSelection: {
            /** Version */
            version: number;
            /** Entries */
            entries: components["schemas"]["WorkspaceSelectionEntry"][];
        };
        /** WorkspaceSelectionEntry */
        WorkspaceSelectionEntry: {
            /** Id */
            id: string;
            /** Field Id */
            field_id?: string | null;
            /** Revision Id */
            revision_id?: string | null;
            /** Exclusion Reason */
            exclusion_reason?: string | null;
            /** Target Revisions */
            target_revisions?: {
                [key: string]: string;
            } | null;
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
        /**
         * OriginalRgbPreviewMetadata
         * @description Unscaled display-code samples, not recovered acquisition intensities.
         */
        OriginalRgbPreviewMetadata: {
            /**
             * Version
             * @default 2.0.0
             * @constant
             */
            version: "2.0.0";
            /** Field Id */
            field_id: string;
            /** Requested Channel */
            requested_channel: string;
            /**
             * Composite
             * @default false
             * @constant
             */
            composite: false;
            /**
             * Scope
             * @default whole-plane
             * @constant
             */
            scope: "whole-plane";
            /**
             * Mode
             * @default original-display-rgb
             * @constant
             */
            mode: "original-display-rgb";
            /**
             * Value Basis
             * @default display-rgb-code
             * @constant
             */
            value_basis: "display-rgb-code";
            /**
             * Dtype
             * @default uint8
             * @constant
             */
            dtype: "uint8";
            /**
             * Source Axes
             * @enum {string}
             */
            source_axes: "YXS" | "SYX";
            /** Source Shape */
            source_shape: [
                number,
                number,
                number
            ];
            /** Rendered Shape */
            rendered_shape: [
                number,
                number,
                number
            ];
            /**
             * Color Mode
             * @enum {string}
             */
            color_mode: "RGB" | "RGBA";
            /** Alpha Preserved */
            alpha_preserved: boolean;
            /**
             * Contrast Applied
             * @default false
             * @constant
             */
            contrast_applied: false;
            /**
             * Sample Values Unchanged
             * @default true
             * @constant
             */
            sample_values_unchanged: true;
            /** Source File Sha256 */
            source_file_sha256: string;
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
        /**
         * RegionPreviewDisplayMetadata
         * @description Generic previews distinguish scaled grayscale from original RGB display codes.
         */
        RegionPreviewDisplayMetadata: components["schemas"]["PreviewDisplayMetadata"] | components["schemas"]["OriginalRgbPreviewMetadata"];
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
        /** StatisticalMethodsTemplate */
        StatisticalMethodsTemplate: {
            /**
             * Id
             * @constant
             */
            id: "cytellect-statistical-methods";
            /**
             * Version
             * @constant
             */
            version: "1.0.0";
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
            /** Methods Template */
            methods_template?: components["schemas"]["StatisticalMethodsTemplate"];
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
            /**
             * Source Review
             * @default null
             */
            source_review: "automatic_unreviewed" | null;
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
    table_descriptive_v1_tables__tid__descriptive_post: {
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
    upload_ome_v1_workspaces__wid__region_fields_ome_post: {
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
                "multipart/form-data": components["schemas"]["Body_upload_ome_v1_workspaces__wid__region_fields_ome_post"];
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
                    /** @description Exact PNG display transform, including unscaled original RGB display codes. */
                    "X-Cytellect-Preview-Display"?: {
                        "application/json": components["schemas"]["RegionPreviewDisplayMetadata"];
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
    compartment_status_v1_revisions__rid__region_compartment_status_get: {
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
    gfp_gate_v1_workspaces__wid__gfp_gate_post: {
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
                "application/json": components["schemas"]["GfpGateRequest"];
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
    compartment_summary_v1_revisions__rid__compartment_summary_get: {
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
                    "application/json": components["schemas"]["RegionReport"] | components["schemas"]["RegionReportV2"] | components["schemas"]["RegionReportV3"] | components["schemas"]["RegionReportV4"];
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
    descriptive_preview_v1_revisions__rid__descriptive_preview_post: {
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
    calculate_v1_revisions__rid__common_statistics_post: {
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
                "application/json": components["schemas"]["RegionComparisonRequestV2"] | components["schemas"]["RegionAssociationRequest"];
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
    result_v1_jobs__jid__common_statistics_get: {
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
                    "application/json": components["schemas"]["CommonComparisonView"] | components["schemas"]["AssociationView"];
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
    draft_proposal_v1_workspaces__wid__proposal_drafts_post: {
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
                "application/json": components["schemas"]["ProposalDraftRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProposalDraftResponse"];
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
    get_selection_v1_workspaces__wid__selection_get: {
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
                    "application/json": components["schemas"]["WorkspaceSelection"];
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
    save_selection_v1_workspaces__wid__selection_post: {
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
                "application/json": components["schemas"]["WorkspaceSelection"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["WorkspaceSelection"];
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
    get_assignments_v1_workspaces__wid__channel_assignments_get: {
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
                    "application/json": components["schemas"]["ChannelAssignments"];
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
    save_assignments_v1_workspaces__wid__channel_assignments_put: {
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
                "application/json": components["schemas"]["ChannelAssignmentsWrite"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ChannelAssignments"];
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
    get_spec_v1_workspaces__wid__analysis_spec_get: {
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
                    "application/json": components["schemas"]["AnalysisSpecView"];
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
    save_spec_v1_workspaces__wid__analysis_spec_put: {
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
                "application/json": components["schemas"]["AnalysisSpecWrite"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AnalysisSpecView"];
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
    list_runs_v1_workspaces__wid__runs_get: {
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
    start_run_v1_workspaces__wid__runs_post: {
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
                "application/json": components["schemas"]["WorkspaceRunRequest"];
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
    get_run_v1_workspaces__wid__runs__run_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                wid: string;
                run_id: string;
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
    accept_run_v1_workspaces__wid__runs__run_id__accept_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                wid: string;
                run_id: string;
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
    cancel_run_v1_workspaces__wid__runs__run_id__cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                wid: string;
                run_id: string;
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
    get_links_v1_workspaces__wid__field_links_get: {
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
    save_link_v1_workspaces__wid__field_links__fid__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                wid: string;
                fid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FieldLinkWrite"];
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
    publication_package_v1_jobs__jid__publication_package_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                jid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PublicationPackageRequest"];
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
    rendered_v1_jobs__jid__figure_render_get: {
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
    render_v1_jobs__jid__figure_render_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                jid: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["FigureRenderRequest"];
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
    saved_selection_v1_revisions__rid__workspace_selection_get: {
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
                    "application/json": components["schemas"]["WorkspaceSelection"];
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
    assemble_v1_workspaces__wid__region_cohorts_post: {
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
                "application/json": components["schemas"]["RegionCohortRequest"];
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
}
