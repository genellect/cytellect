using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Windows.Forms;

// A small GUI executable provides the Store/Start-menu entry point. CPython,
// Tcl/Tk, native wheels and Fiji are all shipped inside the read-only package.
internal static class Launcher
{
    private static bool diagnostic;
    private static string diagnosticPath;
    private static string reason = "none";

    [DllImport("shell32.dll")]
    private static extern int SHGetKnownFolderPath(ref Guid folder, uint flags, IntPtr token, out IntPtr path);

    private static string LocalAppData()
    {
        var folder = new Guid("F1B32785-6FBA-4FCF-9D55-7B8E7F157091");
        IntPtr path;
        // KF_FLAG_NO_PACKAGE_REDIRECTION: share the ZIP edition's actual folder,
        // including machines whose known folder was relocated by an administrator.
        int error = SHGetKnownFolderPath(ref folder, 0x00010000, IntPtr.Zero, out path);
        try { Marshal.ThrowExceptionForHR(error); return Marshal.PtrToStringUni(path); }
        finally { if (path != IntPtr.Zero) Marshal.FreeCoTaskMem(path); }
    }

    private static void Diagnostic(string phase, int code)
    {
        if (!diagnostic || diagnosticPath == null) return;
        try
        {
            string directory = Path.GetDirectoryName(diagnosticPath);
            if (Directory.Exists(directory) && (File.GetAttributes(directory) & FileAttributes.ReparsePoint) != 0) return;
            if (File.Exists(diagnosticPath) && (File.GetAttributes(diagnosticPath) & FileAttributes.ReparsePoint) != 0) return;
            Directory.CreateDirectory(directory);
            File.WriteAllText(diagnosticPath, "phase=" + phase + "\nreason=" + reason + "\nexit_code=" + code + "\n");
        }
        catch { }
    }

    private static void ReadError(object sender, DataReceivedEventArgs args)
    {
        if (args.Data == null) return;
        foreach (string marker in new[] {"ModuleNotFoundError", "ImportError", "PermissionError", "OSError",
            "ValueError", "RuntimeError", "msix_payload_incomplete", "msix_source_identity_invalid",
            "local_runtime_already_in_use", "msix_startup_failed"})
            if (args.Data.Contains(marker)) reason = marker;
    }

    [STAThread]
    private static int Main(string[] arguments)
    {
        diagnostic = arguments.Length == 1 && arguments[0] == "--diagnostic";
        try
        {
            string package = AppDomain.CurrentDomain.BaseDirectory;
            string local = LocalAppData();
            string userRoot = Path.Combine(local, "Cytellect");
            for (var cursor = new DirectoryInfo(userRoot); cursor != null; cursor = cursor.Parent)
                if (cursor.Exists && (cursor.Attributes & FileAttributes.ReparsePoint) != 0)
                    throw new InvalidOperationException();
            Directory.CreateDirectory(userRoot);
            diagnosticPath = Path.Combine(userRoot, "settings", "msix-diagnostic.txt");
            Diagnostic("native_start", 0);
            var acl = new DirectorySecurity();
            acl.SetSecurityDescriptorSddlForm("D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;" +
                WindowsIdentity.GetCurrent().User.Value + ")", AccessControlSections.Access);
            Directory.SetAccessControl(userRoot, acl);
            var info = new ProcessStartInfo(Path.Combine(package, "runtime", "pythonw.exe"),
                "-I -B -m cytellect_api.msix" + (diagnostic ? " --diagnostic" : ""));
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
            info.EnvironmentVariables["LOCALAPPDATA"] = local;
            info.RedirectStandardError = diagnostic;
            info.RedirectStandardOutput = diagnostic;
            Diagnostic("native_ready", 0);
            using (var process = Process.Start(info))
            {
                if (process == null) throw new InvalidOperationException();
                Diagnostic("python_started", 0);
                if (diagnostic)
                {
                    process.ErrorDataReceived += ReadError;
                    process.OutputDataReceived += delegate { };
                    process.BeginErrorReadLine();
                    process.BeginOutputReadLine();
                }
                process.WaitForExit();
                Diagnostic("python_exited", process.ExitCode);
                return process.ExitCode;
            }
        }
        catch (Exception error)
        {
            reason = error is UnauthorizedAccessException ? "native_access_denied" : "native_exception";
            Diagnostic("native_failed", Marshal.GetHRForException(error));
            if (diagnostic) return 1;
            MessageBox.Show("Cytellectを起動できません。Microsoft Storeから修復または再インストールしてください。",
                "Cytellect", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
