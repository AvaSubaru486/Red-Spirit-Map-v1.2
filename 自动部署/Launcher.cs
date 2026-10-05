// Small native Windows GUI launcher, compiled with the installed .NET Framework.
// No self-extracting Python runtime and no files unpacked to the C: drive.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

internal static class Launcher
{
    private static readonly string Deploy = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
    private static readonly string Root = Directory.GetParent(Deploy).FullName;
    private static readonly string Cache = Path.Combine(Deploy, "cache");

    // Windows CommandLineToArgvW quoting, including spaces and trailing slashes.
    private static string Quote(string value)
    {
        var output = new StringBuilder("\"");
        int slashes = 0;
        foreach (char c in value)
        {
            if (c == '\\') { slashes++; continue; }
            if (c == '"') { output.Append('\\', slashes * 2 + 1); output.Append(c); }
            else { output.Append('\\', slashes); output.Append(c); }
            slashes = 0;
        }
        output.Append('\\', slashes * 2);
        output.Append('"');
        return output.ToString();
    }

    private static ProcessStartInfo Info(string executable, string arguments)
    {
        var info = new ProcessStartInfo(executable, arguments);
        info.WorkingDirectory = Root;
        info.UseShellExecute = false;
        info.CreateNoWindow = true;
        info.RedirectStandardOutput = true;
        info.RedirectStandardError = true;
        info.StandardOutputEncoding = Encoding.UTF8;
        info.StandardErrorEncoding = Encoding.UTF8;
        info.EnvironmentVariables["PYTHONUTF8"] = "1";
        info.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
        info.EnvironmentVariables["TEMP"] = Path.Combine(Cache, "tmp");
        info.EnvironmentVariables["TMP"] = Path.Combine(Cache, "tmp");
        info.EnvironmentVariables["PIP_CACHE_DIR"] = Path.Combine(Cache, "pip");
        return info;
    }

    private static IEnumerable<string> PythonCandidates()
    {
        if (File.Exists(Path.Combine(Root, "PACKAGE_INFO.json")))
        {
            string bundled = Path.Combine(Root, "runtime", "python.exe");
            if (!File.Exists(bundled)) throw new InvalidOperationException("便携包缺少 runtime\\python.exe。请完整解压整个压缩包，不要单独移动启动器。不会调用系统 Python 或联网安装依赖。");
            yield return bundled;
            yield break;
        }
        yield return Path.Combine(Root, "runtime", "python.exe");
        yield return Path.Combine(Root, ".venv", "Scripts", "python.exe");
        string config = Path.Combine(Root, ".venv", "pyvenv.cfg");
        if (File.Exists(config))
        {
            foreach (string line in File.ReadAllLines(config))
            {
                int split = line.IndexOf('=');
                if (split < 0) continue;
                string key = line.Substring(0, split).Trim();
                string value = line.Substring(split + 1).Trim();
                if (key == "base-executable" || key == "executable") yield return value;
                if (key == "home") yield return Path.Combine(value, "python.exe");
            }
        }
        // Registered Python is often installed without a PATH entry by PyCharm users.
        foreach (RegistryKey hive in new[] { Registry.CurrentUser, Registry.LocalMachine })
        {
            using (RegistryKey versions = hive.OpenSubKey(@"Software\Python\PythonCore"))
            {
                if (versions == null) continue;
                foreach (string version in versions.GetSubKeyNames())
                {
                    using (RegistryKey path = versions.OpenSubKey(version + @"\InstallPath"))
                    {
                        if (path == null) continue;
                        string executable = path.GetValue("ExecutablePath") as string;
                        if (!String.IsNullOrEmpty(executable)) yield return executable;
                        string folder = path.GetValue(null) as string;
                        if (!String.IsNullOrEmpty(folder)) yield return Path.Combine(folder, "python.exe");
                    }
                }
            }
        }
        foreach (string folder in (Environment.GetEnvironmentVariable("PATH") ?? "").Split(';'))
        {
            if (String.IsNullOrWhiteSpace(folder) || folder.IndexOf("WindowsApps", StringComparison.OrdinalIgnoreCase) >= 0) continue;
            yield return Path.Combine(folder.Trim('"'), "python.exe");
        }
    }

    private static string FindPython()
    {
        foreach (string candidate in PythonCandidates())
        {
            if (!File.Exists(candidate)) continue;
            try
            {
                using (Process probe = Process.Start(Info(candidate, "-c \"import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)\"")))
                {
                    if (!probe.WaitForExit(10000)) { probe.Kill(); continue; }
                    if (probe.ExitCode == 0) return candidate;
                }
            }
            catch { }
        }
        if (File.Exists(Path.Combine(Root, "PACKAGE_INFO.json")))
            throw new InvalidOperationException("便携运行时无法启动。请确认使用 Windows 10/11 x64 并重新完整解压压缩包；不会调用系统 Python 或联网安装依赖。");
        throw new InvalidOperationException("未找到可运行的 Python 3.10+。请先安装 Python，或在 PyCharm 中为此项目配置解释器。\n不会自动安装到 C 盘。");
    }

    private static int Run(string[] args, Action<string> progress)
    {
        try
        {
            Directory.CreateDirectory(Path.Combine(Cache, "tmp"));
            Directory.CreateDirectory(Path.Combine(Deploy, "logs"));
            string script = Path.Combine(Deploy, "deploy.py");
            if (!File.Exists(script)) throw new FileNotFoundException("缺少 deploy.py，请保留自动部署文件夹的完整内容。", script);
            string python = FindPython();
            var arguments = new StringBuilder("-X utf8 -u " + Quote(script));
            foreach (string arg in args) arguments.Append(" " + Quote(arg));
            using (Process process = new Process())
            {
                process.StartInfo = Info(python, arguments.ToString());
                process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs e) { if (e.Data != null) progress(e.Data); };
                process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs e) { if (e.Data != null) progress(e.Data); };
                process.Start();
                process.BeginOutputReadLine();
                process.BeginErrorReadLine();
                process.WaitForExit();
                return process.ExitCode;
            }
        }
        catch (Exception error)
        {
            progress(error.Message);
            try { File.WriteAllText(Path.Combine(Deploy, "logs", "last-error.txt"), error.ToString(), Encoding.UTF8); } catch { }
            return 1;
        }
    }

    [STAThread]
    private static int Main(string[] args)
    {
        if (Array.IndexOf(args, "--no-dialog") >= 0) return Run(args, delegate(string text) { });
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        int exitCode = 1;
        bool finished = false;
        using (var form = new Form())
        using (var label = new Label())
        using (var bar = new ProgressBar())
        {
            form.Text = "红色精神 · 本地网站启动器";
            form.ClientSize = new Size(490, 150);
            form.StartPosition = FormStartPosition.CenterScreen;
            form.FormBorderStyle = FormBorderStyle.FixedDialog;
            form.MaximizeBox = false;
            form.MinimizeBox = false;
            form.Font = new Font("Microsoft YaHei UI", 10);
            label.Text = "正在检查运行环境，请稍候…";
            label.SetBounds(24, 22, 440, 72);
            bar.SetBounds(24, 112, 440, 12);
            bar.Style = ProgressBarStyle.Marquee;
            form.Controls.Add(label);
            form.Controls.Add(bar);
            form.FormClosing += delegate(object sender, FormClosingEventArgs e) { if (!finished) e.Cancel = true; };
            form.Shown += delegate
            {
                ThreadPool.QueueUserWorkItem(delegate
                {
                    exitCode = Run(args, delegate(string message)
                    {
                        if (!form.IsDisposed) form.BeginInvoke((Action)delegate { label.Text = message; });
                    });
                    form.BeginInvoke((Action)delegate
                    {
                        finished = true;
                        if (exitCode != 0)
                        {
                            bar.Style = ProgressBarStyle.Blocks;
                            MessageBox.Show(form, label.Text + "\n\n详细日志：\n" + Path.Combine(Deploy, "logs"),
                                            "启动未完成", MessageBoxButtons.OK, MessageBoxIcon.Error);
                        }
                        form.Close();
                    });
                });
            };
            Application.Run(form);
        }
        return exitCode;
    }
}
