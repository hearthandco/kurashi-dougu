"""毎日の自動実行を登録／解除する。

  python tools/kit/schedule_task.py            … 登録（時刻は config.json の schedule_time。既定 10:00）
  python tools/kit/schedule_task.py --remove   … 解除
  python tools/kit/schedule_task.py --status   … 登録状況の確認

Windows : タスクスケジューラに「RakutenLPKit」という名前で登録（スリープ中なら起こして実行）
Mac     : launchd（~/Library/LaunchAgents/jp.rakutenlpkit.daily.plist）に登録
Linux   : crontab に1行追加（Raspberry Pi などでの運用向け）
"""

import base64
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER = REPO_ROOT / "tools" / "rakuten-lp" / "run_daily.py"
TASK = "RakutenLPKit"
PLIST = Path.home() / "Library" / "LaunchAgents" / "jp.rakutenlpkit.daily.plist"


def schedule_time() -> tuple:
    cfg = json.loads((REPO_ROOT / "tools" / "rakuten-lp" / "config.json").read_text(encoding="utf-8"))
    hh, mm = (cfg.get("schedule_time") or "10:00").split(":")
    return int(hh), int(mm)


def ps(script: str) -> subprocess.CompletedProcess:
    """PowerShellを文字化けなく実行する（UTF-16でエンコードして渡す）。"""
    enc = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc],
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


def windows(action: str) -> int:
    if action == "remove":
        r = ps(f'Unregister-ScheduledTask -TaskName "{TASK}" -Confirm:$false')
        print("自動実行を解除しました。" if r.returncode == 0 else "登録されていませんでした。")
        return 0
    if action == "status":
        r = ps(f'$t = Get-ScheduledTask -TaskName "{TASK}" -ErrorAction SilentlyContinue; if ($t) {{ $i = Get-ScheduledTaskInfo -TaskName "{TASK}"; '
               f'"登録あり / 前回: " + $i.LastRunTime + " / 次回: " + $i.NextRunTime + " / 前回の結果コード: " + $i.LastTaskResult }} else {{ "登録なし" }}')
        print(r.stdout.strip() or r.stderr.strip())
        return 0
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = pyw if pyw.exists() else Path(sys.executable)
    if "WindowsApps" in str(exe):
        print("⚠ Microsoft Store版のPythonが使われています。自動実行が動かないことがあるため、")
        print("  マニュアル第4章の手順で python.org 版のPythonを入れることをおすすめします。")
    hh, mm = schedule_time()
    script = f'''
$ErrorActionPreference = "Stop"
$action = New-ScheduledTaskAction -Execute "{exe}" -Argument '"{RUNNER}" --notify' -WorkingDirectory "{REPO_ROOT}"
$trigger = New-ScheduledTaskTrigger -Daily -At "{hh:02d}:{mm:02d}"
$settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Hours 5) -RestartCount 1 -RestartInterval (New-TimeSpan -Minutes 15)
$settings.DisallowStartIfOnBatteries = $false
$settings.StopIfGoingOnBatteries = $false
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive
Register-ScheduledTask -TaskName "{TASK}" -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
"OK"
'''
    r = ps(script)
    if r.returncode == 0 and "OK" in r.stdout:
        print(f"✅ 毎日 {hh:02d}:{mm:02d} に自動実行するよう登録しました（タスク名: {TASK}）")
        print("   パソコンの電源を切らず、スリープにしておけば自動で起きて実行します。")
        print("   ※ Windowsにサインインしている（ロック画面でもOK）間だけ動きます。")
        return 0
    print("❌ 登録に失敗しました:", (r.stderr or r.stdout).strip()[:400])
    return 1


def mac(action: str) -> int:
    if action == "remove":
        subprocess.run(["launchctl", "unload", str(PLIST)], capture_output=True)
        PLIST.unlink(missing_ok=True)
        print("自動実行を解除しました。")
        return 0
    if action == "status":
        print("登録あり" if PLIST.exists() else "登録なし")
        return 0
    hh, mm = schedule_time()
    log = REPO_ROOT / "tools" / "rakuten-lp" / "logs" / "launchd.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    PLIST.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>jp.rakutenlpkit.daily</string>
  <key>ProgramArguments</key><array><string>{sys.executable}</string><string>{RUNNER}</string><string>--notify</string></array>
  <key>WorkingDirectory</key><string>{REPO_ROOT}</string>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>{hh}</integer><key>Minute</key><integer>{mm}</integer></dict>
  <key>StandardOutPath</key><string>{log}</string><key>StandardErrorPath</key><string>{log}</string>
</dict></plist>
""", encoding="utf-8")
    subprocess.run(["launchctl", "unload", str(PLIST)], capture_output=True)
    r = subprocess.run(["launchctl", "load", str(PLIST)], capture_output=True, text=True)
    if r.returncode == 0:
        print(f"✅ 毎日 {hh:02d}:{mm:02d} に自動実行するよう登録しました")
        print("   Macがスリープ中の場合は、次に起きたときに実行されます（マニュアル第11章）。")
        return 0
    print("❌ 登録に失敗しました:", r.stderr.strip()[:300])
    return 1


def linux(action: str) -> int:
    hh, mm = schedule_time()
    line = f'{mm} {hh} * * * cd "{REPO_ROOT}" && "{sys.executable}" "{RUNNER}" --notify >/dev/null 2>&1  # {TASK}'
    cur = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    kept = "\n".join(l for l in cur.splitlines() if TASK not in l)
    if action == "status":
        print("登録あり" if TASK in cur else "登録なし")
        return 0
    new = kept + ("\n" if kept else "") + (line + "\n" if action == "add" else "")
    subprocess.run(["crontab", "-"], input=new, text=True)
    print("✅ crontab に登録しました" if action == "add" else "自動実行を解除しました。")
    return 0


def main() -> int:
    action = "remove" if "--remove" in sys.argv else "status" if "--status" in sys.argv else "add"
    osname = platform.system()
    if osname == "Windows":
        os.system("")
        return windows(action)
    if osname == "Darwin":
        return mac(action)
    return linux(action)


if __name__ == "__main__":
    sys.exit(main())
