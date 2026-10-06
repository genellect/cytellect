import com.google.gson.*;
import de.csbdresden.stardist.StarDist2D;
import ij.IJ;
import ij.ImagePlus;
import ij.io.FileSaver;
import ij.plugin.filter.GaussianBlur;
import ij.plugin.filter.EDM;
import ij.process.*;
import inra.ijpb.binary.BinaryImages;
import java.nio.file.*;
import java.util.*;
import net.imagej.Dataset;
import net.imagej.ImageJ;
import net.imglib2.RandomAccess;
import net.imglib2.type.numeric.RealType;

/** Fixed CPU-only bridge. No submitted scripts, network/model URLs, GUI, or pixel mutation. */
public class CytellectEngine {
    static { net.imagej.patcher.LegacyInjector.preinit(); }
    static float[] pixels(ImagePlus imp) { return (float[])imp.getProcessor().convertToFloatProcessor().getPixels(); }
    static double number(JsonObject p, String key) { return p.get(key).getAsDouble(); }
    static void save(float[] p, int w, int h, Path file) {
        if (!new FileSaver(new ImagePlus("labels",new FloatProcessor(w,h,p))).saveAsTiff(file.toString()))
            throw new IllegalStateException("label_write_failed");
    }
    public static void main(String[] args) {
        try { execute(Path.of(args[0])); System.exit(0); }
        catch (Throwable failure) { failure.printStackTrace(); System.exit(2); }
    }
    static void verifyRois(JsonObject root) throws Exception {
        try(java.util.zip.ZipFile zip=new java.util.zip.ZipFile(root.get("roi_zip").getAsString())) {
            JsonObject metadata=JsonParser.parseString(new String(zip.getInputStream(zip.getEntry("cytellect-roi.json")).readAllBytes(),java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
            int h=metadata.getAsJsonArray("shape").get(0).getAsInt(),w=metadata.getAsJsonArray("shape").get(1).getAsInt();
            int[] labels=new int[w*h];
            for(JsonElement entry:metadata.getAsJsonArray("entries")) {
                String name=entry.getAsJsonObject().get("name").getAsString();
                long label=entry.getAsJsonObject().get("label").getAsLong();
                byte[] bytes=zip.getInputStream(zip.getEntry(name)).readAllBytes();
                ij.gui.Roi roi=new ij.io.RoiDecoder(bytes,name).getRoi();
                java.awt.Rectangle box=roi.getBounds();
                if(roi.getType()!=ij.gui.Roi.RECTANGLE) throw new IllegalArgumentException("unsupported_roi");
                for(int y=box.y;y<box.y+box.height;y++) for(int x=box.x;x<box.x+box.width;x++) {
                    if(roi.contains(x,y)) labels[y*w+x]=(int)label;
                }
            }
            java.nio.ByteBuffer raw=java.nio.ByteBuffer.allocate(w*h*4).order(java.nio.ByteOrder.LITTLE_ENDIAN);
            for(int label:labels) raw.putInt(label);
            Files.write(Path.of(root.get("roi_output").getAsString()),raw.array());
        }
    }
    static void execute(Path request) throws Exception {
        execute(request, binary -> BinaryImages.componentsLabeling(binary,8,32));
    }
    static void detectSignal(JsonObject root, java.util.function.Function<ByteProcessor,ImageProcessor> labelComponents) throws Exception {
        Path out=Path.of(root.get("directory").getAsString());
        JsonObject parameters=root.getAsJsonObject("detector");
        ImagePlus image=IJ.openImage(out.resolve("signal.tif").toString());
        if(image==null) throw new IllegalArgumentException("signal_input_missing");
        int w=image.getWidth(),h=image.getHeight(),size=w*h;
        FloatProcessor detection=image.getProcessor().convertToFloatProcessor();
        double sigma=number(parameters,"smoothing_sigma_px");
        if(sigma>0) new GaussianBlur().blurGaussian(detection,sigma,sigma,0.01);
        float[] signal=(float[])detection.getPixels();
        float low=Float.POSITIVE_INFINITY,high=Float.NEGATIVE_INFINITY;
        for(float value:signal) {low=Math.min(low,value);high=Math.max(high,value);}
        String method=parameters.get("threshold_method").getAsString();
        boolean otsuMethod=method.equals("otsu");
        if(!otsuMethod && !method.equals("manual")) throw new IllegalArgumentException("unknown_signal_threshold");
        boolean indeterminate=otsuMethod && low==high;
        int otsu=0;
        if(otsuMethod && !indeterminate) {
            int[] histogram=new int[256];
            for(float value:signal) histogram[Math.min(255,(int)((value-low)*256/(high-low)))]++;
            otsu=new AutoThresholder().getThreshold(AutoThresholder.Method.Otsu,histogram);
        }
        ByteProcessor binary=new ByteProcessor(w,h);
        if(!indeterminate) for(int i=0;i<size;i++) {
            boolean selected=otsuMethod?Math.min(255,(int)((signal[i]-low)*256/(high-low)))>otsu:
                signal[i]>number(parameters,"threshold");
            if(selected) binary.set(i,255);
        }
        if(parameters.get("split_touching").getAsBoolean()) new EDM().toWatershed(binary);
        ImageProcessor components=labelComponents.apply(binary);
        Map<Integer,Integer> areas=new TreeMap<>();
        for(int i=0;i<size;i++) {int id=(int)components.getf(i);if(id>0) areas.merge(id,1,Integer::sum);}
        Map<Integer,Integer> ids=new HashMap<>();int next=1;
        for(Map.Entry<Integer,Integer> entry:areas.entrySet())
            if(entry.getValue()>=parameters.get("minimum_area_px").getAsInt()) ids.put(entry.getKey(),next++);
        float[] labels=new float[size];
        for(int i=0;i<size;i++) {Integer id=ids.get((int)components.getf(i));if(id!=null) labels[i]=id;}
        save(labels,w,h,out.resolve("regions.tif"));
        JsonObject info=new JsonObject();
        info.addProperty("operation","signal-only");
        info.addProperty("engine","Fiji / ImageJ / MorphoLibJ");
        info.addProperty("java_version",System.getProperty("java.version"));
        info.addProperty("headless",java.awt.GraphicsEnvironment.isHeadless());
        info.add("parameters",parameters.deepCopy());
        info.addProperty("status",indeterminate?"indeterminate":ids.isEmpty()?"no_candidate":"candidate");
        info.addProperty("threshold_method",method);
        info.addProperty("histogram_bins",256);
        info.addProperty("detection_minimum",low);info.addProperty("detection_maximum",high);
        if(otsuMethod && !indeterminate) info.addProperty("otsu_bin",otsu);
        info.addProperty("selection_rule",otsuMethod?"floor(min(255, (signal-min)*256/(max-min))) > otsu_bin":"signal > threshold");
        info.addProperty("connectivity",8);
        info.addProperty("biological_positivity_established",false);
        Files.writeString(out.resolve("engine-result.json"),new GsonBuilder().serializeNulls().setPrettyPrinting().create().toJson(info));
    }
    // Package-private dependency boundary permits a fixed test helper to make a
    // component operation fail. CLI/API requests cannot replace this function.
    static void execute(Path request, java.util.function.Function<ByteProcessor,ImageProcessor> labelComponents) throws Exception {
        JsonObject root=JsonParser.parseString(Files.readString(request)).getAsJsonObject();
        if(root.has("roi_zip")) { verifyRois(root); return; }
        if(root.has("mode") && root.get("mode").getAsString().equals("signal-only")) {detectSignal(root,labelComponents);return;}
        boolean nuclearOnly=root.has("mode") && root.get("mode").getAsString().equals("nuclear-only");
        if(root.has("mode") && !nuclearOnly) throw new IllegalArgumentException("unknown_operation");
        JsonObject recipe=root.getAsJsonObject(nuclearOnly?"detector":"recipe");
        Path out=Path.of(root.get("directory").getAsString());
        String nuclearInput=nuclearOnly?"nuclear.tif":"dapi.tif";
        ImagePlus dapi=IJ.openImage(out.resolve(nuclearInput).toString());
        boolean hasNcl=!nuclearOnly && (!root.has("has_ncl") || root.get("has_ncl").getAsBoolean());
        ImagePlus ncl=hasNcl?IJ.openImage(out.resolve("ncl.tif").toString()):null;
        int w=dapi.getWidth(),h=dapi.getHeight(),size=w*h;
        int tiles=1;
        while((long)w*h>262144L*tiles) tiles*=4;
        float[] nuclei;
        if (root.get("reuse_nuclei").getAsBoolean()) nuclei=pixels(IJ.openImage(out.resolve("nuclei-input.tif").toString()));
        else {
            ImageJ ij=new ImageJ();
            try {
                Dataset image=(Dataset)ij.io().open(out.resolve(nuclearInput).toString());
                Map<String,Object> params=new HashMap<>();
                params.put("input",image);
                // Embedded, checked model. Never accept modelChoice/modelURL from clients.
                params.put("modelChoice","Versatile (fluorescent nuclei)");
                params.put("normalizeInput",true);
                params.put("percentileBottom",number(recipe,"percentile_low"));
                params.put("percentileTop",number(recipe,"percentile_high"));
                params.put("probThresh",number(recipe,"probability"));
                params.put("nmsThresh",number(recipe,"nms"));
                params.put("outputType","Label Image");
                params.put("nTiles",tiles);
                params.put("excludeBoundary",0);
                params.put("roiPosition","Automatic");
                params.put("showCsbdeepProgress",false);
                params.put("showProbAndDist",false);
                params.put("verbose",false);
                Dataset result=(Dataset)ij.command().run(StarDist2D.class,false,params).get().getOutput("label");
                if (result==null) throw new IllegalStateException("nucleus_detection_failed");
                nuclei=new float[size];
                RandomAccess<?> access=result.getImgPlus().randomAccess();
                for(int y=0;y<h;y++) for(int x=0;x<w;x++) {
                    access.setPosition(x,0);access.setPosition(y,1);
                    nuclei[y*w+x]=((RealType<?>)access.get()).getRealFloat();
                }
            } finally { ij.context().dispose(); }
        }
        if(nuclearOnly) {
            save(nuclei,w,h,out.resolve("nuclei.tif"));
            JsonObject info=new JsonObject();
            info.addProperty("operation","nuclear-only");
            info.addProperty("engine","Fiji / StarDist 2D");
            info.addProperty("java_version",System.getProperty("java.version"));
            info.addProperty("headless",java.awt.GraphicsEnvironment.isHeadless());
            info.addProperty("n_tiles",tiles);
            info.addProperty("model","Versatile (fluorescent nuclei)");
            info.add("parameters",recipe.deepCopy());
            Files.writeString(out.resolve("engine-result.json"),new GsonBuilder().setPrettyPrinting().create().toJson(info));
            return;
        }
        Map<Integer,int[]> bounds=new TreeMap<>();
        for(int y=0;y<h;y++) for(int x=0;x<w;x++) {
            int label=(int)nuclei[y*w+x];if(label==0) continue;
            int[] box=bounds.get(label);
            if(box==null) {box=new int[]{x,y,x,y};bounds.put(label,box);}
            box[0]=Math.min(box[0],x);box[1]=Math.min(box[1],y);
            box[2]=Math.max(box[2],x);box[3]=Math.max(box[3],y);
        }
        boolean dapiLow=recipe.get("nucleolar_method").getAsString().equals("dapi-low");
        boolean controlled=recipe.has("compartment_threshold_method");
        String thresholdMethod=controlled?recipe.get("compartment_threshold_method").getAsString():"otsu";
        if(controlled && (!root.get("reuse_nuclei").getAsBoolean() || dapiLow || !hasNcl
                || !(thresholdMethod.equals("otsu") || thresholdMethod.equals("manual"))))
            throw new IllegalArgumentException("invalid_compartment_threshold_mode");
        boolean manual=controlled && thresholdMethod.equals("manual");
        double maximumArea=controlled && recipe.has("maximum_area_px") && !recipe.get("maximum_area_px").isJsonNull()
            ? number(recipe,"maximum_area_px") : Double.POSITIVE_INFINITY;
        FloatProcessor detection=(dapiLow||!hasNcl?dapi:ncl).getProcessor().convertToFloatProcessor();
        double sigma=number(recipe,"smoothing_sigma_px");
        if(sigma>0) new GaussianBlur().blurGaussian(detection,sigma,sigma,0.01);
        float[] signal=(float[])detection.getPixels(), nucleoli=new float[size];
        int next=1;
        JsonObject statuses=new JsonObject();
        JsonObject thresholds=new JsonObject();
        for(Map.Entry<Integer,int[]> nucleus:bounds.entrySet()) {
            int label=nucleus.getKey();int[] box=nucleus.getValue();
            if(!hasNcl) {statuses.addProperty(""+label,"not_applicable_no_ncl");continue;}
            int x0=box[0],y0=box[1],cw=box[2]-x0+1,ch=box[3]-y0+1;
            try {
            float[] values=new float[cw*ch];int count=0;
            float low=Float.POSITIVE_INFINITY,high=Float.NEGATIVE_INFINITY;
            for(int y=0;y<ch;y++) for(int x=0;x<cw;x++) {
                int i=(y0+y)*w+x0+x;
                if(nuclei[i]==label) {values[count++]=signal[i];low=Math.min(low,signal[i]);high=Math.max(high,signal[i]);}
            }
            JsonObject details=new JsonObject();
            if(controlled) {
                details.addProperty("method",thresholdMethod);
                details.addProperty("detection_minimum",low);details.addProperty("detection_maximum",high);
                details.addProperty("threshold_units","input intensity after optional detection-only Gaussian blur");
                thresholds.add(""+label,details);
            }
            if(low==high && !manual) {
                if(controlled) details.addProperty("missing_reason","uniform_signal");
                statuses.addProperty(""+label,"indeterminate");continue;
            }
            double threshold=0;int otsu=0;
            if(manual) {
                threshold=number(recipe,"compartment_threshold");
                details.addProperty("threshold",threshold);
                details.addProperty("selection_rule","signal > threshold");
            } else if(dapiLow) {
                Arrays.sort(values,0,count);double position=(count-1)*number(recipe,"dapi_low_percentile")/100;
                int lower=(int)Math.floor(position),upper=(int)Math.ceil(position);
                threshold=values[lower]+(position-lower)*(values[upper]-values[lower]);
            } else {
                int[] histogram=new int[256];
                for(int i=0;i<count;i++) histogram[Math.min(255,(int)((values[i]-low)*256/(high-low)))]++;
                otsu=new AutoThresholder().getThreshold(AutoThresholder.Method.Otsu,histogram);
                if(controlled) {
                    details.addProperty("histogram_bins",256);details.addProperty("otsu_bin",otsu);
                    details.addProperty("source_bin_boundary",low+(otsu+1)*(double)(high-low)/256.0);
                    details.addProperty("selection_rule","floor(min(255, (signal-min)*256/(max-min))) > otsu_bin");
                }
            }
            ByteProcessor binary=new ByteProcessor(cw,ch);
            for(int y=0;y<ch;y++) for(int x=0;x<cw;x++) {
                int i=(y0+y)*w+x0+x;
                if(nuclei[i]==label) {
                    boolean selected=manual?signal[i]>threshold:dapiLow?signal[i]<threshold:Math.min(255,(int)((signal[i]-low)*256/(high-low)))>otsu;
                    if(selected) binary.set(x,y,255);
                }
            }
            if(recipe.get("split_touching").getAsBoolean()) new EDM().toWatershed(binary);
            ImageProcessor components=labelComponents.apply(binary);
            Map<Integer,Integer> area=new TreeMap<>();
            for(int i=0;i<cw*ch;i++) {int id=(int)components.getf(i);if(id>0) area.merge(id,1,Integer::sum);}
            Map<Integer,Integer> ids=new HashMap<>();
            for(Map.Entry<Integer,Integer> entry:area.entrySet()) if(entry.getValue()>=recipe.get("minimum_area_px").getAsInt()
                    && entry.getValue()<=maximumArea) ids.put(entry.getKey(),next++);
            for(int y=0;y<ch;y++) for(int x=0;x<cw;x++) {
                Integer id=ids.get((int)components.getf(x,y));if(id!=null) nucleoli[(y0+y)*w+x0+x]=id;
            }
            statuses.addProperty(""+label,ids.isEmpty()?"no_candidate":"candidates");
            } catch (RuntimeException recoverable) {
                // Never report an unfinished candidate mask as biological absence.
                // Errors such as OOM, input loading, and StarDist failure remain fatal.
                for(int y=0;y<ch;y++) for(int x=0;x<cw;x++) {
                    int i=(y0+y)*w+x0+x;if(nuclei[i]==label) nucleoli[i]=0;
                }
                statuses.addProperty(""+label,"processing_failed");
            }
        }
        save(nuclei,w,h,out.resolve("nuclei.tif"));save(nucleoli,w,h,out.resolve("nucleoli.tif"));
        JsonObject info=new JsonObject();
        info.addProperty("engine","Fiji / StarDist 2D / ImageJ / MorphoLibJ");
        info.addProperty("java_version",System.getProperty("java.version"));
        info.addProperty("headless",java.awt.GraphicsEnvironment.isHeadless());
        info.addProperty("n_tiles",root.get("reuse_nuclei").getAsBoolean()?0:tiles);
        info.addProperty("model","Versatile (fluorescent nuclei)");
        info.addProperty("nucleolar_algorithm",!hasNcl?"not_applicable_no_ncl":dapiLow?"DAPI low percentile; MorphoLibJ 8-connectivity":"ImageJ 256-bin per-nucleus Otsu; MorphoLibJ 8-connectivity");
        info.addProperty("nuclei_reused",root.get("reuse_nuclei").getAsBoolean());
        info.addProperty("nucleolar_status_protocol_version","1.1.0");
        info.add("nucleolar_status",statuses);
        if(controlled) {
            info.addProperty("nucleolar_detector_protocol_version","1.1.0");
            info.addProperty("nucleolar_algorithm",manual?"Explicit per-nucleus NCL threshold; MorphoLibJ 8-connectivity":"ImageJ 256-bin per-nucleus NCL Otsu; MorphoLibJ 8-connectivity");
            info.add("nucleolar_thresholds",thresholds);
            info.addProperty("smoothing_scope","full defining plane, detection only; threshold and components restricted to parent nucleus");
            info.addProperty("area_filter_stage","after optional ImageJ EDM watershed");
        }
        Files.writeString(out.resolve("engine-result.json"),new GsonBuilder().setPrettyPrinting().create().toJson(info));
    }
}
