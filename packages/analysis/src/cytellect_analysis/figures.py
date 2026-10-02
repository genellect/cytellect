"""The same Matplotlib figure generates previews and vector exports."""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats

def render_figures(result, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    spec = result["spec"]
    plot = spec["plot"]
    metric = spec["metric"]
    cells = pd.DataFrame(result["plot_data"])
    units = pd.DataFrame(result["unit_summary"])
    observed = list(cells.condition.unique())
    order = plot["group_order"] or observed
    if set(order) != set(observed) or len(order) != len(set(order)):
        raise ValueError("group_order_must_match_groups")
    with plt.rc_context({"font.size":plot["font_size"], "svg.fonttype":"none", "pdf.fonttype":42,
                         "font.family":["Noto Sans CJK JP", "DejaVu Sans"] if plot["language"] == "ja" else ["DejaVu Sans"]}):
        fig, ax = plt.subplots(figsize=(plot["width_inches"],plot["height_inches"]), layout="constrained")
        colors = ["#126c67", "#ca6f36", "#6b5a9b", "#4479a8", "#b74868"]
        rng = np.random.default_rng(0)
        if plot["kind"] == "scatter":
            for i,group in enumerate(order):
                d = cells[cells.condition == group]
                x = d.gfp_mean_corrected.to_numpy()
                y = d[metric].to_numpy()
                valid = np.isfinite(x) & np.isfinite(y)
                x,y = x[valid],y[valid]
                ax.scatter(x,y,s=18,alpha=.5,color=colors[i%len(colors)],label=group)
                if len(x) >= 3 and np.ptp(x)>0:
                    slope,intercept,*_ = stats.linregress(x,y)
                    grid = np.linspace(x.min(),x.max(),100)
                    predicted = intercept+slope*grid
                    residual = np.sqrt(np.sum((y-intercept-slope*x)**2)/(len(x)-2))
                    band = stats.t.ppf(.975,len(x)-2)*residual*np.sqrt(1/len(x)+(grid-x.mean())**2/np.sum((x-x.mean())**2))
                    ax.plot(grid,predicted,color=colors[i%len(colors)])
                    ax.fill_between(grid,predicted-band,predicted+band,color=colors[i%len(colors)],alpha=.12)
            ax.set_xlabel(plot["x_label"] or "GFP mean intensity (background corrected)")
            ax.legend(frameon=False)
        else:
            for i,group in enumerate(order):
                values = cells.loc[cells.condition == group,metric].to_numpy()
                ax.scatter(i+rng.uniform(-.18,.18,len(values)),values,s=10,color="#8b9494",alpha=.35)
                uv = units.loc[units.condition == group,metric].to_numpy()
                ax.scatter(np.full(len(uv),i),uv,s=40,color=colors[i%len(colors)],edgecolor="white",zorder=3)
                m = next(v for v in result["means"] if v["condition"] == group)
                if m["ci_low"] is not None:
                    ax.errorbar(i+.25,m["mean"],yerr=[[m["mean"]-m["ci_low"]],[m["ci_high"]-m["mean"]]],fmt="D",color=colors[i%len(colors)],capsize=3)
            if plot["kind"] == "paired":
                if "pair" not in units or units.pair.isna().any():
                    raise ValueError("paired_plot_requires_pairs")
                for _,pair in units.groupby("pair"):
                    indexed = pair.set_index("condition")
                    present = [g for g in order if g in indexed.index]
                    ax.plot([order.index(g) for g in present],[indexed.loc[g,metric] for g in present],color="#aaa",lw=.7,zorder=0)
            ax.set_xticks(range(len(order)),order)
            ax.set_xlabel(plot["x_label"] or ("条件" if plot["language"]=="ja" else "Condition"))
        ax.set_ylabel(plot["y_label"] or metric)
        ax.spines[["top","right"]].set_visible(False)
        ax.set_title("Exploratory analysis" if spec["mode"]=="exploratory" else "Independent experimental units",loc="left",fontsize=11)
        for suffix in ("svg","pdf","png"):
            fig.savefig(output/f"figure.{suffix}",dpi=200,metadata={"Creator":"Cytellect"})
        plt.close(fig)
    pd.DataFrame(result["plot_data"]).to_csv(output/"plot-data.csv",index=False)
    pd.DataFrame(result["comparisons"]).to_csv(output/"comparisons.csv",index=False)
    pd.DataFrame(result["unit_summary"]).to_csv(output/"experimental-units.csv",index=False)
