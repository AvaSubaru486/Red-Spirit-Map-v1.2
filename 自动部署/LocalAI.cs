using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;
using System.Collections.Generic;
using System.Web.Script.Serialization;
class LocalAI {
 [STAThread] static void Main() {
  try {
   string dir=AppDomain.CurrentDomain.BaseDirectory;
   var p=Process.Start(new ProcessStartInfo("powershell.exe", "-NoProfile -ExecutionPolicy Bypass -File \""+Path.Combine(dir,"setup_ai.ps1")+"\"") {WorkingDirectory=dir,UseShellExecute=false,CreateNoWindow=true});
   Application.EnableVisualStyles();
   var form=new Form {Text="一键部署本地 AI",Width=630,Height=250,StartPosition=FormStartPosition.CenterScreen};
   var label=new Label {Left=20,Top=20,Width=570,Height=90,Text="正在部署本地模型。完整资源包可离线部署，请预留 4 GB 磁盘空间。"};
   var bar=new ProgressBar {Left=20,Top=120,Width=570,Height=24};
   var button=new Button {Left=490,Top=155,Width=100,Text="后台运行"};
   button.Click+=(s,e)=>form.Close();
   form.Controls.AddRange(new Control[]{label,bar,button});
   var timer=new Timer {Interval=750};
   timer.Tick+=(s,e)=> {
    try {
     var state=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(File.ReadAllText(Path.Combine(dir,"logs","ai-state.json")));
     label.Text=Convert.ToString(state["message"]);
     bar.Value=Math.Max(0,Math.Min(100,Convert.ToInt32(state["percent"])));
    } catch {}
    if(p.HasExited) { timer.Stop(); button.Text="关闭"; label.Text=p.ExitCode==0?"本地模型已就绪，网站可自动识别并使用。":p.ExitCode==2?"另一个部署任务正在运行，请在网站测试面板查看进度。":"部署失败，可重新运行重试。详情：logs/ai-state.json\r\n"+label.Text; }
   };
   timer.Start();
   Application.Run(form);
  } catch(Exception e) {MessageBox.Show(e.Message,"本地 AI");}
 }
}
