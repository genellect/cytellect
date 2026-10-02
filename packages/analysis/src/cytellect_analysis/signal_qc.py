"""Warning-only native signal diagnostics; never mutate measurements or selection."""
import math

SIGNAL_COMPARTMENTS = (
    ("ncl_nucleus", "ncl"), ("ncl_nucleoli", "ncl"),
    ("ncl_nucleoplasm", "ncl"), ("gfp", "gfp"),
)


def native_signal_quality(row, minimum_ratio):
    """Mean minus confirmed background median, divided by robust background MAD.

    This is a spatial background-dispersion diagnostic, not a photon-noise SNR
    estimate or a validated biological threshold. Undefined values stay missing.
    """
    result = {"signal_qc_protocol_version": "1.0.0", "native_signal_qc_minimum_ratio": minimum_ratio}
    for prefix, channel in SIGNAL_COMPARTMENTS:
        value = row.get(f"{prefix}_mean_corrected")
        sigma = row.get(f"{channel}_background_sigma")
        ratio = weak = None
        if not row.get("channel_availability", {}).get(channel, False):
            reason = "channel_not_acquired"
        elif channel == "ncl" and row.get("recipe_id") == "gfp-nuclear-2d":
            reason = "recipe_not_measured"
        elif prefix in ("ncl_nucleoli", "ncl_nucleoplasm") and row.get("nucleolar_status") == "processing_failed":
            reason = "nucleolar_processing_failed"
        elif value is None:
            reason = "compartment_empty"
        elif sigma is None or not math.isfinite(sigma) or sigma < 0:
            reason = "background_dispersion_invalid"
        elif sigma == 0:
            reason = "background_dispersion_zero"
        else:
            candidate = value / sigma
            if not math.isfinite(candidate):
                reason = "ratio_nonfinite"
            else:
                ratio = float(candidate)
                if minimum_ratio is None:
                    reason = "threshold_not_set"
                else:
                    weak = ratio < minimum_ratio
                    reason = "below_threshold" if weak else "at_or_above_threshold"
        result[f"{prefix}_signal_to_background"] = ratio
        result[f"{prefix}_weak_signal"] = weak
        result[f"{prefix}_signal_qc_reason"] = reason
    return result
