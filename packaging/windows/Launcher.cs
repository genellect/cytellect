using System;
using System.Diagnostics;
using System.IO;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Windows.Forms;

// A small GUI executable provides the Store/Start-menu entry point. CPython,
// Tcl/Tk, native wheels and Fiji are all shipped inside the read-only package.
internal static class Launcher
{
    [STAThread]
    private static int Main()
    {
        try
        {
            string package = AppDomain.CurrentDomain.BaseDirectory;
            string userRoot = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Cytellect");
            for (var cursor = new DirectoryInfo(userRoot); cursor != null; cursor = cursor.Parent)
                if (cursor.Exists && (cursor.Attributes & FileAttributes.ReparsePoint) != 0)
                    throw new InvalidOperationException();
            Directory.CreateDirectory(userRoot);
            var acl = new DirectorySecurity();
            acl.SetSecurityDescriptorSddlForm("D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;" +
                WindowsIdentity.GetCurrent().User.Value + ")", AccessControlSections.Access);
            Directory.SetAccessControl(userRoot, acl);
            var info = new ProcessStartInfo(Path.Combine(package, "runtime", "pythonw.exe"),
                "-I -B -m cytellect_api.msix");
            info.UseShellExecute = false;
            info.CreateNoWindow = true;
            info.WorkingDirectory = package;
            // Neither system Python customization nor shell-supplied service
            // credentials are part of a normal Store launch.
            foreach (string name in new System.Collections.ArrayList(info.EnvironmentVariables.Keys))
                if (name.StartsWith("PYTHON", StringComparison.OrdinalIgnoreCase) ||
                    name.StartsWith("CYTELLECT_", StringComparison.OrdinalIgnoreCase) ||
                    name == "VIRTUAL_ENV" || name == "TCL_LIBRARY" || name == "TK_LIBRARY")
                    info.EnvironmentVariables.Remove(name);
            using (var process = Process.Start(info))
            {
                if (process == null) throw new InvalidOperationException();
                process.WaitForExit();
                return process.ExitCode;
            }
        }
        catch
        {
            MessageBox.Show("Cytellectを起動できません。Microsoft Storeから修復または再インストールしてください。",
                "Cytellect", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
