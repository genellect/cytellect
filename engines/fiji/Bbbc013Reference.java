import com.google.gson.*;
import ij.IJ;
import ij.ImagePlus;
import ij.io.FileSaver;
import ij.process.*;
import ij.plugin.filter.ThresholdToSelection;
import java.nio.file.*;
import java.nio.*;
import java.util.*;
import loci.formats.in.InCell3000Reader;
import loci.formats.FormatTools;

/** Public-data validation utility; not reachable from the research upload API. */
public class Bbbc013Reference {
    public static void main(String[] args) throws Exception {
        JsonObject request=JsonParser.parseString(Files.readString(Path.of(args[0]))).getAsJsonObject();
        Path output=Path.of(request.get("output").getAsString());
        if(request.get("mode").getAsString().equals("convert")) {
            InCell3000Reader reader=new InCell3000Reader();
            try {
                reader.setId(request.get("input").getAsString());
                JsonObject info=new JsonObject();
                info.addProperty("reader",reader.getClass().getName());
                info.addProperty("format",reader.getFormat());
                info.addProperty("width",reader.getSizeX());info.addProperty("height",reader.getSizeY());
                info.addProperty("size_c",reader.getSizeC());info.addProperty("size_z",reader.getSizeZ());
                info.addProperty("size_t",reader.getSizeT());info.addProperty("planes",reader.getImageCount());
                info.addProperty("pixel_type",FormatTools.getPixelTypeString(reader.getPixelType()));
                JsonArray planes=new JsonArray();
                for(int index=0;index<reader.getImageCount();index++) {
                    byte[] bytes=reader.openBytes(index);
                    ImageProcessor processor;
                    if(reader.getPixelType()==FormatTools.UINT16) {
                        short[] values=new short[bytes.length/2];
                        ByteBuffer.wrap(bytes).order(reader.isLittleEndian()?ByteOrder.LITTLE_ENDIAN:ByteOrder.BIG_ENDIAN).asShortBuffer().get(values);
                        processor=new ShortProcessor(reader.getSizeX(),reader.getSizeY(),values,null);
                    } else if(reader.getPixelType()==FormatTools.UINT8) processor=new ByteProcessor(reader.getSizeX(),reader.getSizeY(),bytes,null);
                    else throw new IllegalArgumentException("unsupported_native_type");
                    Path plane=output.resolve("plane-"+index+".tif");
                    new FileSaver(new ImagePlus("native",processor)).saveAsTiff(plane.toString());
                    planes.add(plane.getFileName().toString());
                }
                info.add("output_planes",planes);
                Files.writeString(output.resolve("conversion.json"),new GsonBuilder().setPrettyPrinting().create().toJson(info));
            } finally {reader.close();}
        } else {
            ImagePlus image=IJ.openImage(request.get("input").getAsString());
            ImagePlus labels=IJ.openImage(request.get("labels").getAsString());
            ImageProcessor pixelLabels=labels.getProcessor();
            int w=image.getWidth(),h=image.getHeight();
            Set<Integer> ids=new TreeSet<>();
            for(int i=0;i<w*h;i++) if(pixelLabels.getf(i)>0) ids.add((int)pixelLabels.getf(i));
            JsonArray results=new JsonArray();
            for(int id:ids) {
                ByteProcessor mask=new ByteProcessor(w,h);
                for(int i=0;i<w*h;i++) if(pixelLabels.getf(i)==id) mask.set(i,255);
                mask.setThreshold(255,255,ImageProcessor.NO_LUT_UPDATE);
                ij.gui.Roi roi=new ThresholdToSelection().convert(mask);
                image.setRoi(roi);
                ImageStatistics statistics=image.getStatistics(ij.measure.Measurements.AREA|ij.measure.Measurements.MEAN|ij.measure.Measurements.MEDIAN|ij.measure.Measurements.INTEGRATED_DENSITY);
                JsonObject row=new JsonObject();
                row.addProperty("id",id);row.addProperty("count",statistics.pixelCount);
                row.addProperty("mean",statistics.mean);row.addProperty("median",statistics.median);
                row.addProperty("integrated",statistics.mean*statistics.pixelCount);
                results.add(row);
            }
            Files.writeString(output.resolve("imagej-reference.json"),new GsonBuilder().setPrettyPrinting().create().toJson(results));
        }
    }
}
