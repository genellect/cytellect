import java.util.HashMap;
import java.util.Map;
import java.util.prefs.AbstractPreferences;
import java.util.prefs.Preferences;
import java.util.prefs.PreferencesFactory;

/** Per-process preferences: never retain image paths or settings in user profiles. */
public final class CytellectPreferences implements PreferencesFactory {
    private final Preferences root=new Memory(null,"");
    public Preferences systemRoot() { return root; }
    public Preferences userRoot() { return root; }
    private static final class Memory extends AbstractPreferences {
        private final Map<String,String> values=new HashMap<>();
        private final Map<String,Memory> children=new HashMap<>();
        Memory(AbstractPreferences parent,String name) { super(parent,name); }
        protected void putSpi(String key,String value) { values.put(key,value); }
        protected String getSpi(String key) { return values.get(key); }
        protected void removeSpi(String key) { values.remove(key); }
        protected void removeNodeSpi() { values.clear();children.clear(); }
        protected String[] keysSpi() { return values.keySet().toArray(new String[0]); }
        protected String[] childrenNamesSpi() { return children.keySet().toArray(new String[0]); }
        protected AbstractPreferences childSpi(String name) { return children.computeIfAbsent(name,key->new Memory(this,key)); }
        protected void syncSpi() {}
        protected void flushSpi() {}
    }
}
