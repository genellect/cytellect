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
        JsonObject root=JsonParser.parseString(Files.readString(request)).getAsJsonObject();
        if(root.has("roi_zip")) { verifyRois(root); return; }
        JsonObject recipe=root.getAsJsonObject("recipe");
        Path out=Path.of(root.get("directory").getAsString());
        ImagePlus dapi=IJ.openImage(out.resolve("dapi.tif").toString());
        boolean hasNcl=!root.has("has_ncl") || root.get("has_ncl").getAsBoolean();
        ImagePlus ncl=hasNcl?IJ.openImage(out.resolve("ncl.tif").toString()):null;
        int w=dapi.getWidth(),h=dapi.getHeight(),size=w*h;
        int tiles=1;
        while((long)w*h>262144L*tiles) tiles*=4;
        float[] nuclei;
        if (root.get("reuse_nuclei").getAsBoolean()) nuclei=pixels(IJ.openImage(out.resolve("nuclei-input.tif").toString()));
        else {
            ImageJ ij=new ImageJ();
            try {
                Dataset image=(Dataset)ij.io().open(out.resolve("dapi.tif").toString());
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
        Map<Integer,int[]> bounds=new TreeMap<>();
        for(int y=0;y<h;y++) for(int x=0;x<w;x++) {
            int label=(int)nuclei[y*w+x];if(label==0) continue;
            int[] box=bounds.get(label);
            if(box==null) {box=new int[]{x,y,x,y};bounds.put(label,box);}
            box[0]=Math.min(box[0],x);box[1]=Math.min(box[1],y);
            box[2]=Math.max(box[2],x);box[3]=Math.max(box[3],y);
        }
        boolean dapiLow=recipe.get("nucleolar_method").getAsString().equals("dapi-low");
        FloatProcessor detection=(dapiLow||!hasNcl?dapi:ncl).getProcessor().convertToFloatProcessor();
        double sigma=number(recipe,"smoothing_sigma_px");
        if(sigma>0) new GaussianBlur().blurGaussian(detection,sigma,sigma,0.01);
        float[] signal=(float[])detection.getPixels(), nucleoli=new float[size];
        int next=1;
        JsonObject statuses=new JsonObject();
        for(Map.Entry<Integer,int[]> nucleus:bounds.entrySet()) {
            int label=nucleus.getKey();int[] box=nucleus.getValue();
            if(!hasNcl) {statuses.addProperty(""+label,"not_applicable_no_ncl");continue;}
            int x0=box[0],y0=box[1],cw=box[2]-x0+1,ch=box[3]-y0+1;
            float[] values=new float[cw*ch];int count=0;
            float low=Float.POSITIVE_INFINITY,high=Float.NEGATIVE_INFINITY;
            for(int y=0;y<ch;y++) for(int x=0;x<cw;x++) {
                int i=(y0+y)*w+x0+x;
                if(nuclei[i]==label) {values[count++]=signal[i];low=Math.min(low,signal[i]);high=Math.max(high,signal[i]);}
            }
            if(low==high) {statuses.addProperty(""+label,"indeterminate");continue;}
            double threshold=0;int otsu=0;
            if(dapiLow) {
                Arrays.sort(values,0,count);double position=(count-1)*number(recipe,"dapi_low_percentile")/100;
                int lower=(int)Math.floor(position),upper=(int)Math.ceil(position);
                threshold=values[lower]+(position-lower)*(values[upper]-values[lower]);
            } else {
                int[] histogram=new int[256];
                for(int i=0;i<count;i++) histogram[Math.min(255,(int)((values[i]-low)*256/(high-low)))]++;
                otsu=new AutoThresholder().getThreshold(AutoThresholder.Method.Otsu,histogram);
            }
            ByteProcessor binary=new ByteProcessor(cw,ch);
            for(int y=0;y<ch;y++) for(int x=0;x<cw;x++) {
                int i=(y0+y)*w+x0+x;
                if(nuclei[i]==label) {
                    boolean selected=dapiLow?signal[i]<threshold:Math.min(255,(int)((signal[i]-low)*256/(high-low)))>otsu;
                    if(selected) binary.set(x,y,255);
                }
            }
            if(recipe.get("split_touching").getAsBoolean()) new EDM().toWatershed(binary);
            ImageProcessor components=BinaryImages.componentsLabeling(binary,8,32);
            Map<Integer,Integer> area=new TreeMap<>();
            for(int i=0;i<cw*ch;i++) {int id=(int)components.getf(i);if(id>0) area.merge(id,1,Integer::sum);}
            Map<Integer,Integer> ids=new HashMap<>();
            for(Map.Entry<Integer,Integer> entry:area.entrySet()) if(entry.getValue()>=recipe.get("minimum_area_px").getAsInt()) ids.put(entry.getKey(),next++);
            for(int y=0;y<ch;y++) for(int x=0;x<cw;x++) {
                Integer id=ids.get((int)components.getf(x,y));if(id!=null) nucleoli[(y0+y)*w+x0+x]=id;
            }
            statuses.addProperty(""+label,ids.isEmpty()?"no_candidate":"candidates");
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
        info.add("nucleolar_status",statuses);
        Files.writeString(out.resolve("engine-result.json"),new GsonBuilder().setPrettyPrinting().create().toJson(info));
    }
}
