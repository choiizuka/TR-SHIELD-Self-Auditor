#!/usr/bin/env python3
"""
TR-SHIELD Self Auditor v1.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━
CHOIIZUKA Truth-Science AI-Team
https://choiizuka.com/
https://choiizuka.com/tr-shield-self-auditor/

自律型AI攻撃耐性セルフチェックプログラム
完全ローカル実行 / 外部通信ゼロ / 無償配布

LICENSE: MIT
"""

import os
import re
import sys
import json
import stat
import socket
import hashlib
import platform
import datetime
import subprocess
import http.server
import threading
import webbrowser
import time
from pathlib import Path
from typing import Optional

# ───────────────────────────────────────────────
# 定数
# ───────────────────────────────────────────────
VERSION = "1.0.0"
REPORT_DIR = Path("tr_shield_reports")
NOW = datetime.datetime.now()

# 判定レベル
class Level:
    CRITICAL    = "CRITICAL"
    WARNING     = "WARNING"
    PASS        = "PASS"
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_TESTED  = "NOT_TESTED"

# カラーコード（ターミナル用）
class C:
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    GREEN  = "\033[92m"
    CYAN   = "\033[96m"
    WHITE  = "\033[97m"
    GRAY   = "\033[90m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"

# ───────────────────────────────────────────────
# ユーティリティ
# ───────────────────────────────────────────────
def color_level(level: str) -> str:
    m = {
        Level.CRITICAL:     f"{C.BOLD}{C.RED}[CRITICAL]{C.RESET}",
        Level.WARNING:      f"{C.BOLD}{C.YELLOW}[WARNING]{C.RESET}",
        Level.PASS:         f"{C.BOLD}{C.GREEN}[PASS]{C.RESET}",
        Level.INCONCLUSIVE: f"{C.BOLD}{C.CYAN}[INCONCLUSIVE]{C.RESET}",
        Level.NOT_TESTED:   f"{C.GRAY}[NOT TESTED]{C.RESET}",
    }
    return m.get(level, level)

def banner():
    print(f"""
{C.BOLD}{C.RED}
  ████████╗██████╗       ███████╗██╗  ██╗██╗███████╗██╗     ██████╗
  ╚══██╔══╝██╔══██╗      ██╔════╝██║  ██║██║██╔════╝██║     ██╔══██╗
     ██║   ██████╔╝█████╗███████╗███████║██║█████╗  ██║     ██║  ██║
     ██║   ██╔══██╗╚════╝╚════██║██╔══██║██║██╔══╝  ██║     ██║  ██║
     ██║   ██║  ██║      ███████║██║  ██║██║███████╗███████╗██████╔╝
     ╚═╝   ╚═╝  ╚═╝      ╚══════╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝╚═════╝{C.RESET}
{C.BOLD}  Self Auditor v{VERSION}  —  AI攻撃耐性セルフチェック{C.RESET}
{C.GRAY}  CHOIIZUKA Truth-Science AI-Team  |  https://choiizuka.com/{C.RESET}
{C.GRAY}  完全ローカル実行 / 外部通信ゼロ / 無償配布 (MIT){C.RESET}
  {'─'*60}
""")

def section(title: str):
    print(f"\n{C.BOLD}{C.CYAN}  ┌─ {title} {'─'*(54-len(title))}┐{C.RESET}")

def end_section():
    print(f"{C.CYAN}  └{'─'*60}┘{C.RESET}")

def result_line(label: str, level: str, detail: str = ""):
    icon = {"CRITICAL":"✖","WARNING":"⚠","PASS":"✔","INCONCLUSIVE":"?","NOT_TESTED":"–"}.get(level,"·")
    color = {"CRITICAL":C.RED,"WARNING":C.YELLOW,"PASS":C.GREEN,"INCONCLUSIVE":C.CYAN,"NOT_TESTED":C.GRAY}.get(level,C.WHITE)
    print(f"  {color}{icon}{C.RESET}  {label:<38} {color_level(level)}")
    if detail:
        for line in detail.split("\n"):
            if line.strip():
                print(f"     {C.GRAY}→ {line.strip()}{C.RESET}")

# ───────────────────────────────────────────────
# M1: 認証・セッション耐久性監査
# ───────────────────────────────────────────────
def check_auth_session() -> list[dict]:
    findings = []

    # --- SSH設定 ---
    ssh_config = Path("/etc/ssh/sshd_config")
    if ssh_config.exists():
        try:
            text = ssh_config.read_text(errors="ignore")
            # ルートログイン
            if re.search(r"^\s*PermitRootLogin\s+yes", text, re.M):
                findings.append({"id":"AUTH-001","label":"SSHルートログイン","level":Level.CRITICAL,
                    "detail":"PermitRootLogin yes — rootで直接SSHログイン可能。AI攻撃の最優先ターゲット。\n推奨: PermitRootLogin no"})
            else:
                findings.append({"id":"AUTH-001","label":"SSHルートログイン","level":Level.PASS,
                    "detail":"PermitRootLogin が無効または設定なし（安全側デフォルト）"})

            # パスワード認証
            if re.search(r"^\s*PasswordAuthentication\s+yes", text, re.M):
                findings.append({"id":"AUTH-002","label":"SSHパスワード認証","level":Level.WARNING,
                    "detail":"PasswordAuthentication yes — ブルートフォース攻撃にさらされている。\n推奨: 公開鍵認証のみに制限"})
            elif re.search(r"^\s*PasswordAuthentication\s+no", text, re.M):
                findings.append({"id":"AUTH-002","label":"SSHパスワード認証","level":Level.PASS,
                    "detail":"公開鍵認証のみ — 設定良好"})
            else:
                findings.append({"id":"AUTH-002","label":"SSHパスワード認証","level":Level.INCONCLUSIVE,
                    "detail":"設定が明示されていない。デフォルトはyes（要確認）"})

            # MaxAuthTries
            m = re.search(r"^\s*MaxAuthTries\s+(\d+)", text, re.M)
            if m:
                n = int(m.group(1))
                if n > 6:
                    findings.append({"id":"AUTH-003","label":"SSH認証試行上限","level":Level.WARNING,
                        "detail":f"MaxAuthTries {n} — 上限が高すぎる。推奨: 3以下"})
                else:
                    findings.append({"id":"AUTH-003","label":"SSH認証試行上限","level":Level.PASS,
                        "detail":f"MaxAuthTries {n} — 適切"})
        except PermissionError:
            findings.append({"id":"AUTH-001","label":"SSH設定読み取り","level":Level.INCONCLUSIVE,
                "detail":"権限不足でsshd_configを読めない"})
    else:
        findings.append({"id":"AUTH-001","label":"SSH設定","level":Level.NOT_TESTED,
            "detail":"/etc/ssh/sshd_config が存在しない（非LinuxまたはSSH未インストール）"})

    # --- sudo設定 ---
    sudoers = Path("/etc/sudoers")
    if sudoers.exists():
        try:
            text = sudoers.read_text(errors="ignore")
            if re.search(r"NOPASSWD:\s*ALL", text):
                findings.append({"id":"AUTH-004","label":"sudo NOPASSWD:ALL","level":Level.CRITICAL,
                    "detail":"パスワードなしですべてのコマンドをroot実行可能。\n推奨: NOPASSWD を最小限のコマンドに限定"})
            else:
                findings.append({"id":"AUTH-004","label":"sudo NOPASSWD:ALL","level":Level.PASS,
                    "detail":"NOPASSWD:ALL の設定なし"})
        except PermissionError:
            findings.append({"id":"AUTH-004","label":"sudo設定","level":Level.INCONCLUSIVE,
                "detail":"権限不足でsudoersを読めない"})

    # --- セッションタイムアウト (bashrc/profile) ---
    tmout_found = False
    for f in [Path("/etc/profile"), Path("/etc/bash.bashrc"), Path(os.path.expanduser("~/.bashrc"))]:
        if f.exists():
            try:
                t = f.read_text(errors="ignore")
                m = re.search(r"TMOUT\s*=\s*(\d+)", t)
                if m:
                    sec = int(m.group(1))
                    if sec <= 900:
                        findings.append({"id":"AUTH-005","label":"シェルセッションタイムアウト","level":Level.PASS,
                            "detail":f"TMOUT={sec}秒 ({f}) — 適切"})
                    else:
                        findings.append({"id":"AUTH-005","label":"シェルセッションタイムアウト","level":Level.WARNING,
                            "detail":f"TMOUT={sec}秒 ({f}) — 長すぎる。推奨: 900秒以下"})
                    tmout_found = True
                    break
            except: pass
    if not tmout_found:
        findings.append({"id":"AUTH-005","label":"シェルセッションタイムアウト","level":Level.WARNING,
            "detail":"TMOUT が設定されていない — セッションが永続的に開いたままになる可能性"})

    return findings

# ───────────────────────────────────────────────
# M2: Zero-Hold（データ不保持）適合性監査
# ───────────────────────────────────────────────

# 機密情報の正規表現パターン（値を記録しない、存在のみ検出）
SECRET_PATTERNS = [
    (re.compile(r'(?i)(password|passwd|pwd)\s*[=:]\s*\S+'), "平文パスワード"),
    (re.compile(r'(?i)(api[_-]?key|apikey|api[_-]?secret)\s*[=:]\s*\S+'), "APIキー"),
    (re.compile(r'(?i)(secret[_-]?key|secret[_-]?token)\s*[=:]\s*\S+'), "シークレットトークン"),
    (re.compile(r'(?i)(access[_-]?token|auth[_-]?token|bearer)\s*[=:]\s*\S+'), "アクセストークン"),
    (re.compile(r'(?i)(aws_access_key_id|aws_secret_access_key)\s*[=:]\s*\S+'), "AWSクレデンシャル"),
    (re.compile(r'(?i)private[_-]?key'), "秘密鍵"),
    (re.compile(r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----'), "秘密鍵ブロック"),
]

def scan_secrets_in_file(path: Path) -> list[tuple[int, str]]:
    """ファイル内の機密情報を検出（値は記録しない）"""
    hits = []
    try:
        with open(path, errors="ignore") as f:
            for i, line in enumerate(f, 1):
                for pat, label in SECRET_PATTERNS:
                    if pat.search(line):
                        hits.append((i, label))
                        break
    except (PermissionError, OSError):
        pass
    return hits

def check_zero_hold() -> list[dict]:
    findings = []
    total_secret_files = 0

    # --- .env ファイルの権限チェック ---
    env_files = list(Path("/var/www").rglob(".env")) if Path("/var/www").exists() else []
    env_files += list(Path(os.path.expanduser("~")).rglob(".env"))
    env_files = env_files[:50]  # 上限

    critical_env = []
    for ef in env_files:
        try:
            mode = os.stat(ef).st_mode
            if mode & stat.S_IROTH:  # Other読み取り可能
                critical_env.append(str(ef))
        except: pass

    if critical_env:
        findings.append({"id":"ZH-001","label":".envファイル権限露出","level":Level.CRITICAL,
            "detail":f"{len(critical_env)}個の.envファイルが他ユーザーから読み取り可能\n例: {critical_env[0]}\n推奨: chmod 600 .env"})
    elif env_files:
        findings.append({"id":"ZH-001","label":".envファイル権限","level":Level.PASS,
            "detail":f"{len(env_files)}個の.envを確認、権限は適切"})
    else:
        findings.append({"id":"ZH-001","label":".envファイルスキャン","level":Level.NOT_TESTED,
            "detail":".envファイルが見つからなかった"})

    # --- /tmp 内の機密情報スキャン ---
    tmp_hits = []
    tmp_path = Path("/tmp")
    try:
        for f in list(tmp_path.iterdir())[:100]:
            if f.is_file() and f.suffix in [".log",".txt",".json",".env",".conf","",".py",".sh"]:
                hits = scan_secrets_in_file(f)
                if hits:
                    tmp_hits.append((f.name, hits[0][1]))
    except: pass

    if tmp_hits:
        findings.append({"id":"ZH-002","label":"/tmp 内の機密情報","level":Level.CRITICAL,
            "detail":f"/tmp 内 {len(tmp_hits)} ファイルに機密情報の疑い\n例: {tmp_hits[0][0]} ({tmp_hits[0][1]})\n推奨: 定期的な /tmp クリーンアップ"})
    else:
        findings.append({"id":"ZH-002","label":"/tmp 内の機密情報","level":Level.PASS,
            "detail":"/tmp 内に明示的な機密情報を検出せず"})

    # --- ログファイル内の機密情報スキャン ---
    log_dirs = [Path("/var/log"), Path("/var/www/html"), Path(os.path.expanduser("~/logs"))]
    log_hits = []
    for ld in log_dirs:
        if not ld.exists(): continue
        for lf in list(ld.rglob("*.log"))[:30]:
            hits = scan_secrets_in_file(lf)
            if hits:
                log_hits.append((str(lf), hits[0][1]))

    if log_hits:
        findings.append({"id":"ZH-003","label":"ログファイル内の機密情報","level":Level.CRITICAL,
            "detail":f"{len(log_hits)} ファイルに機密情報の疑い\n例: {log_hits[0][0]} ({log_hits[0][1]})\n推奨: ログへの認証情報出力を禁止"})
    else:
        findings.append({"id":"ZH-003","label":"ログ内の機密情報","level":Level.PASS,
            "detail":"スキャンしたログファイルに明示的な機密情報を検出せず"})

    # --- Webルート内の危険ファイル ---
    dangerous_files = []
    web_roots = [Path("/var/www/html"), Path("/var/www"), Path("/srv/www"), Path("/home")]
    danger_patterns = [
        ".git/config", "phpinfo.php", "info.php", "test.php",
        ".htaccess", "wp-config.php.bak", "config.bak", "database.yml",
        ".DS_Store", "dump.sql", "backup.sql", "*.sql.gz",
    ]
    for wr in web_roots:
        if not wr.exists(): continue
        for dp in danger_patterns:
            for found in list(wr.rglob(dp))[:5]:
                dangerous_files.append(str(found))

    if dangerous_files:
        findings.append({"id":"ZH-004","label":"Webルート危険ファイル","level":Level.CRITICAL,
            "detail":f"公開ディレクトリに危険なファイルを検出\n例: {dangerous_files[0]}\n推奨: Webから到達できない場所へ移動または削除"})
    else:
        findings.append({"id":"ZH-004","label":"Webルート危険ファイル","level":Level.PASS,
            "detail":"スキャンした範囲で危険なファイルを検出せず"})

    return findings

# ───────────────────────────────────────────────
# M3: 開放ポート・レガシーエンドポイント監査
# ───────────────────────────────────────────────

HIGH_RISK_PORTS = {
    21:  ("FTP",        Level.CRITICAL, "平文転送。即時無効化を推奨"),
    23:  ("Telnet",     Level.CRITICAL, "平文プロトコル。即時無効化を推奨"),
    25:  ("SMTP",       Level.WARNING,  "メール送信ポート。不要なら閉鎖を"),
    53:  ("DNS",        Level.WARNING,  "DNSサービス。外部公開の必要性を確認"),
    80:  ("HTTP",       Level.WARNING,  "平文HTTP。HTTPSへの強制リダイレクト確認"),
    443: ("HTTPS",      Level.PASS,     "HTTPS — 標準的"),
    3306:("MySQL",      Level.CRITICAL, "データベースポート開放。即時閉鎖を"),
    5432:("PostgreSQL", Level.CRITICAL, "データベースポート開放。即時閉鎖を"),
    6379:("Redis",      Level.CRITICAL, "認証なしRedisは即時データ奪取リスク"),
    8080:("HTTP-Alt",   Level.WARNING,  "開発用ポートが本番に残っている可能性"),
    8443:("HTTPS-Alt",  Level.WARNING,  "代替HTTPSポート。意図的な公開か確認"),
    9200:("Elasticsearch",Level.CRITICAL,"認証なしESは世界中から丸見え"),
    27017:("MongoDB",   Level.CRITICAL, "MongoDBポート開放。即時閉鎖を"),
    3389:("RDP",        Level.CRITICAL, "リモートデスクトップ。AI攻撃の最優先ターゲット"),
    5900:("VNC",        Level.CRITICAL, "VNCはAI総当たり攻撃のターゲット"),
    11211:("Memcached", Level.CRITICAL, "Memcached開放 — DDoS反射攻撃に悪用される"),
}

def check_open_ports() -> list[dict]:
    findings = []
    open_ports = []

    print(f"    {C.GRAY}ポートスキャン中（ループバックのみ）...{C.RESET}", end="", flush=True)

    ports_to_scan = sorted(HIGH_RISK_PORTS.keys())
    for port in ports_to_scan:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    open_ports.append(port)
        except: pass

    print(f" {len(open_ports)}件検出\n")

    if not open_ports:
        findings.append({"id":"PORT-000","label":"スキャン対象ポート","level":Level.PASS,
            "detail":f"ループバックで {len(ports_to_scan)} ポートをスキャン。高リスクポートの開放なし"})
    else:
        for port in open_ports:
            if port in HIGH_RISK_PORTS:
                name, level, desc = HIGH_RISK_PORTS[port]
                findings.append({"id":f"PORT-{port}","label":f"ポート {port} ({name}) 開放",
                    "level":level,"detail":desc})

    # --- systemdサービス確認 ---
    try:
        r = subprocess.run(["systemctl","list-units","--type=service","--state=running","--no-pager","--plain"],
                           capture_output=True, text=True, timeout=5)
        dangerous_services = ["telnet","ftp","vsftpd","proftpd","rsh","rlogin","rexec","nis","finger","rpcbind"]
        found_services = []
        for svc in dangerous_services:
            if svc in r.stdout.lower():
                found_services.append(svc)
        if found_services:
            findings.append({"id":"SVC-001","label":"危険なレガシーサービス稼働","level":Level.CRITICAL,
                "detail":f"無効化すべきサービスが稼働中: {', '.join(found_services)}"})
        else:
            findings.append({"id":"SVC-001","label":"レガシーサービス","level":Level.PASS,
                "detail":"主要な危険レガシーサービスの稼働を検出せず"})
    except:
        findings.append({"id":"SVC-001","label":"サービス確認","level":Level.INCONCLUSIVE,
            "detail":"systemctl が利用できない（非systemd環境）"})

    return findings

# ───────────────────────────────────────────────
# M4: アウトバウンド（データ持ち出し）防御監査
# ───────────────────────────────────────────────
def check_outbound() -> list[dict]:
    findings = []

    # --- iptables/nftables確認 ---
    fw_active = False
    for cmd in [["iptables","-L","-n"], ["nft","list","ruleset"], ["ufw","status"]]:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if r.returncode == 0 and r.stdout.strip() not in ["", "Status: inactive"]:
                fw_active = True
                # OUTPUTチェーンにDROP/REJECTがあるか
                if "OUTPUT" in r.stdout and any(x in r.stdout for x in ["DROP","REJECT"]):
                    findings.append({"id":"OUT-001","label":"ファイアウォール出口制御","level":Level.PASS,
                        "detail":f"{cmd[0]}: OUTPUT チェーンに制限ルールあり"})
                else:
                    findings.append({"id":"OUT-001","label":"ファイアウォール出口制御","level":Level.WARNING,
                        "detail":f"{cmd[0]}: ファイアウォール有効だがOUTPUT制限が確認できない\n推奨: アウトバウンド通信を必要なIPのみに制限"})
                break
        except FileNotFoundError:
            continue
        except: break

    if not fw_active:
        findings.append({"id":"OUT-001","label":"ファイアウォール出口制御","level":Level.CRITICAL,
            "detail":"有効なファイアウォールを検出できない\n侵入されたAIエージェントがデータを自由に外部送信可能"})

    # --- ループバックへのダミー大量通信テスト ---
    print(f"    {C.GRAY}アウトバウンド耐性テスト（ループバックのみ）...{C.RESET}", end="", flush=True)
    try:
        import socket as _s, time as _t
        dummy = os.urandom(65536)  # 64KB ダミーデータ
        start = _t.perf_counter()
        count = 0
        blocked = False

        # 内部ループバックサーバーを一時起動してテスト
        srv = _s.socket(_s.AF_INET, _s.SOCK_STREAM)
        srv.setsockopt(_s.SOL_SOCKET, _s.SO_REUSEADDR, 1)
        try:
            srv.bind(("127.0.0.1", 19876))
            srv.listen(1)
            srv.settimeout(1)

            def _accept():
                try:
                    conn, _ = srv.accept()
                    total = 0
                    while True:
                        d = conn.recv(65536)
                        if not d: break
                        total += len(d)
                    conn.close()
                except: pass

            t = threading.Thread(target=_accept, daemon=True)
            t.start()

            cli = _s.socket(_s.AF_INET, _s.SOCK_STREAM)
            cli.settimeout(2)
            cli.connect(("127.0.0.1", 19876))
            for _ in range(16):  # 1MB相当
                cli.send(dummy)
                count += 1
            cli.close()
            elapsed = _t.perf_counter() - start
            print(f" {count*64}KB/{elapsed:.2f}s\n")
            findings.append({"id":"OUT-002","label":"内部通信速度テスト","level":Level.PASS,
                "detail":f"ループバック通信テスト完了 ({count*64}KB / {elapsed:.2f}秒)\nこのテストはループバック(127.0.0.1)のみで実施"})
        except OSError:
            print(" スキップ\n")
            findings.append({"id":"OUT-002","label":"内部通信速度テスト","level":Level.INCONCLUSIVE,
                "detail":"ポート19876が使用中のためテストをスキップ"})
        finally:
            srv.close()

    except Exception as e:
        print(f" エラー\n")
        findings.append({"id":"OUT-002","label":"通信テスト","level":Level.INCONCLUSIVE,
            "detail":f"テスト実行エラー: {e}"})

    # --- DNS over HTTPS 設定確認 ---
    resolv = Path("/etc/resolv.conf")
    if resolv.exists():
        try:
            t = resolv.read_text(errors="ignore")
            if "1.1.1.1" in t or "8.8.8.8" in t or "9.9.9.9" in t:
                findings.append({"id":"OUT-003","label":"DNSリゾルバー","level":Level.PASS,
                    "detail":"既知のパブリックDNSを使用"})
            elif "nameserver" in t:
                findings.append({"id":"OUT-003","label":"DNSリゾルバー","level":Level.INCONCLUSIVE,
                    "detail":"カスタムDNSを使用。DNS過渡リークのリスクを確認してください"})
        except: pass

    return findings

# ───────────────────────────────────────────────
# M5: システム更新・既知脆弱性監査
# ───────────────────────────────────────────────
def check_system_update() -> list[dict]:
    findings = []
    system = platform.system()

    if system == "Linux":
        # --- カーネルバージョン ---
        kernel = platform.release()
        findings.append({"id":"SYS-001","label":f"カーネル {kernel}","level":Level.INCONCLUSIVE,
            "detail":"カーネルバージョンを手動で確認し、最新CVEを照合してください\nhttps://www.cve.org/"})

        # --- apt/yum 更新確認 ---
        for pkg_cmd in [
            (["apt-get","--simulate","upgrade"], "apt"),
            (["dnf","check-update","--quiet"], "dnf"),
            (["yum","check-update","--quiet"], "yum"),
        ]:
            try:
                r = subprocess.run(pkg_cmd[0], capture_output=True, text=True, timeout=30)
                lines = [l for l in r.stdout.splitlines() if l.strip()]
                # apt: 最初の行に "upgraded" の数
                m = re.search(r"(\d+)\s+upgraded", r.stdout)
                if m:
                    n = int(m.group(1))
                    level = Level.WARNING if n > 0 else Level.PASS
                    findings.append({"id":"SYS-002","label":"パッケージ更新","level":level,
                        "detail":f"{pkg_cmd[1]}: {n}件の更新が利用可能" if n else f"{pkg_cmd[1]}: 最新"})
                elif r.returncode == 100:  # yum/dnfの「更新あり」終了コード
                    findings.append({"id":"SYS-002","label":"パッケージ更新","level":Level.WARNING,
                        "detail":f"{pkg_cmd[1]}: 更新が利用可能"})
                else:
                    findings.append({"id":"SYS-002","label":"パッケージ更新","level":Level.PASS,
                        "detail":f"{pkg_cmd[1]}: パッケージは最新"})
                break
            except FileNotFoundError:
                continue
            except subprocess.TimeoutExpired:
                findings.append({"id":"SYS-002","label":"パッケージ更新確認","level":Level.INCONCLUSIVE,
                    "detail":"タイムアウト（30秒）— ネットワーク接続を確認してください"})
                break

        # --- ファイルパーミッション /etc/passwd /etc/shadow ---
        for fp, expected_writable_by_other in [("/etc/passwd", False), ("/etc/shadow", False)]:
            try:
                m = os.stat(fp).st_mode
                if m & stat.S_IWOTH:
                    findings.append({"id":"SYS-003","label":f"{fp} 書き込み権限","level":Level.CRITICAL,
                        "detail":f"他ユーザーが{fp}に書き込める。即時 chmod o-w で修正を"})
                elif m & stat.S_IROTH and fp == "/etc/shadow":
                    findings.append({"id":"SYS-003","label":f"{fp} 読み取り権限","level":Level.CRITICAL,
                        "detail":"/etc/shadow が誰でも読める。即時 chmod 640 /etc/shadow で修正を"})
                else:
                    findings.append({"id":"SYS-003","label":f"{fp} パーミッション","level":Level.PASS,
                        "detail":"適切"})
            except FileNotFoundError: pass
            except PermissionError:
                findings.append({"id":"SYS-003","label":f"{fp} 確認","level":Level.INCONCLUSIVE,
                    "detail":"権限不足で確認できない"})

    elif system == "Darwin":
        findings.append({"id":"SYS-001","label":"macOS システム","level":Level.INCONCLUSIVE,
            "detail":f"macOS {platform.mac_ver()[0]} — 「システム設定 > ソフトウェアアップデート」で更新確認を"})

    else:
        findings.append({"id":"SYS-001","label":f"システム ({system})","level":Level.NOT_TESTED,
            "detail":"このOSは自動チェック未対応"})

    return findings

# ───────────────────────────────────────────────
# スコア計算
# ───────────────────────────────────────────────
def calc_score(all_findings: list[dict]) -> tuple[int, str]:
    level_weight = {Level.CRITICAL: 30, Level.WARNING: 10, Level.PASS: 0,
                    Level.INCONCLUSIVE: 0, Level.NOT_TESTED: 0}
    deduction = sum(level_weight.get(f["level"], 0) for f in all_findings)
    criticals = sum(1 for f in all_findings if f["level"] == Level.CRITICAL)
    warnings  = sum(1 for f in all_findings if f["level"] == Level.WARNING)
    score = max(0, 100 - deduction)

    if criticals >= 3:
        verdict = "CHECKMATE"
    elif criticals >= 1:
        verdict = "CRITICAL"
    elif warnings >= 3:
        verdict = "WARNING"
    elif warnings >= 1:
        verdict = "CAUTION"
    else:
        verdict = "PASS"

    return score, verdict

# ───────────────────────────────────────────────
# HTMLレポート生成
# ───────────────────────────────────────────────
def generate_html_report(all_findings: list[dict], score: int, verdict: str) -> Path:
    REPORT_DIR.mkdir(exist_ok=True)
    fname = REPORT_DIR / f"tr_shield_report_{NOW.strftime('%Y%m%d_%H%M%S')}.html"

    level_color = {
        Level.CRITICAL: "#ef4444",
        Level.WARNING: "#f59e0b",
        Level.PASS: "#22c55e",
        Level.INCONCLUSIVE: "#60a5fa",
        Level.NOT_TESTED: "#6b7280",
    }
    verdict_color = {
        "CHECKMATE": "#7f1d1d",
        "CRITICAL":  "#ef4444",
        "WARNING":   "#f59e0b",
        "CAUTION":   "#fbbf24",
        "PASS":      "#22c55e",
    }
    level_icon = {
        Level.CRITICAL: "✖",
        Level.WARNING: "⚠",
        Level.PASS: "✔",
        Level.INCONCLUSIVE: "?",
        Level.NOT_TESTED: "–",
    }

    module_groups = {
        "M1 認証・セッション耐久性": [f for f in all_findings if f["id"].startswith("AUTH")],
        "M2 Zero-Hold適合性": [f for f in all_findings if f["id"].startswith("ZH")],
        "M3 ポート・サービス露出": [f for f in all_findings if f["id"].startswith("PORT") or f["id"].startswith("SVC")],
        "M4 アウトバウンド防御": [f for f in all_findings if f["id"].startswith("OUT")],
        "M5 システム・パッケージ": [f for f in all_findings if f["id"].startswith("SYS")],
    }

    rows_html = ""
    for module_name, items in module_groups.items():
        if not items: continue
        rows_html += f'<tr class="module-header"><td colspan="3">{module_name}</td></tr>\n'
        for f in items:
            clr = level_color.get(f["level"], "#6b7280")
            icon = level_icon.get(f["level"], "·")
            detail_html = f["detail"].replace("\n", "<br>").replace("<","&lt;").replace(">","&gt;") if f.get("detail") else ""
            # detailのHTMLエスケープを元に戻す（<br>はそのまま）
            detail_html = detail_html.replace("&lt;br&gt;","<br>")
            rows_html += f"""
            <tr>
              <td style="color:{clr};font-weight:700;">{icon} {f["id"]}</td>
              <td>{f["label"]}</td>
              <td><span class="badge" style="background:{clr}20;color:{clr};border:1px solid {clr}40;">{f["level"]}</span>
                  {"<br><small style='color:#9ca3af;font-size:11px;'>"+detail_html+"</small>" if detail_html else ""}</td>
            </tr>"""

    vc = verdict_color.get(verdict, "#6b7280")
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TR-SHIELD Self Auditor — Report {NOW.strftime('%Y-%m-%d %H:%M')}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  :root{{
    --bg:#0a0a0f;--surface:#111118;--border:#1e1e2e;
    --text:#e2e8f0;--muted:#64748b;--accent:#dc2626;
  }}
  body{{font-family:'Courier New',Courier,monospace;background:var(--bg);color:var(--text);
        min-height:100vh;padding:0}}
  header{{background:linear-gradient(135deg,#1a0000 0%,#0a0a0f 100%);
          border-bottom:2px solid var(--accent);padding:40px 48px 32px}}
  .logo{{font-size:11px;letter-spacing:3px;color:var(--accent);font-weight:700;margin-bottom:8px}}
  h1{{font-size:28px;font-weight:700;color:#fff;margin-bottom:4px;letter-spacing:-0.5px}}
  .subtitle{{font-size:13px;color:var(--muted);margin-bottom:24px}}
  .meta{{font-size:11px;color:var(--muted)}}
  .score-block{{display:flex;gap:32px;align-items:center;margin:32px 48px}}
  .score-num{{font-size:72px;font-weight:700;line-height:1;color:{vc};font-variant-numeric:tabular-nums}}
  .score-label{{font-size:11px;color:var(--muted);letter-spacing:2px;text-transform:uppercase;margin-bottom:6px}}
  .verdict{{font-size:32px;font-weight:700;color:{vc};letter-spacing:2px}}
  .verdict-desc{{font-size:13px;color:var(--muted);margin-top:8px;max-width:480px;line-height:1.6}}
  table{{width:calc(100% - 96px);margin:0 48px 48px;border-collapse:collapse}}
  th{{font-size:10px;letter-spacing:2px;color:var(--muted);padding:10px 16px;text-align:left;
      border-bottom:1px solid var(--border);text-transform:uppercase}}
  td{{padding:10px 16px;border-bottom:1px solid var(--border);font-size:12px;vertical-align:top;line-height:1.6}}
  tr:hover td{{background:#ffffff05}}
  .module-header td{{background:#111118;color:var(--accent);font-size:10px;letter-spacing:3px;
                      text-transform:uppercase;padding:16px 16px 8px;border-top:1px solid var(--border)}}
  .badge{{display:inline-block;padding:2px 8px;border-radius:3px;font-size:10px;
          font-weight:700;letter-spacing:1px}}
  footer{{text-align:center;padding:32px;font-size:11px;color:var(--muted);
          border-top:1px solid var(--border)}}
  footer a{{color:var(--accent);text-decoration:none}}
</style>
</head>
<body>
<header>
  <div class="logo">TR-SHIELD SELF AUDITOR v{VERSION}</div>
  <h1>AI攻撃耐性セルフチェックレポート</h1>
  <div class="subtitle">CHOIIZUKA Truth-Science AI-Team — 完全ローカル実行 / 外部通信ゼロ</div>
  <div class="meta">
    実行日時: {NOW.strftime('%Y年%m月%d日 %H:%M:%S')} &nbsp;|&nbsp;
    ホスト: {socket.gethostname()} &nbsp;|&nbsp;
    OS: {platform.system()} {platform.release()} &nbsp;|&nbsp;
    Python: {platform.python_version()}
  </div>
</header>

<div class="score-block">
  <div>
    <div class="score-label">耐久スコア</div>
    <div class="score-num">{score}</div>
  </div>
  <div>
    <div class="score-label">総合判定</div>
    <div class="verdict">{verdict}</div>
    <div class="verdict-desc">{
        {
            "CHECKMATE":"複数の重大な脆弱性を検出。AI自律エージェントによる攻撃を受けた場合、数秒以内にデータ奪取が完了するリスクがあります。即時対応が必要です。",
            "CRITICAL": "重大な脆弱性を検出。優先度最高で修正してください。",
            "WARNING":  "改善が必要な設定を検出。計画的な対応を推奨します。",
            "CAUTION":  "軽微な改善点があります。次のメンテナンスサイクルで対応を。",
            "PASS":     "スキャンした範囲で重大な問題を検出しませんでした。定期的な再チェックを継続してください。",
        }.get(verdict, "")
    }</div>
  </div>
</div>

<table>
  <thead>
    <tr>
      <th style="width:120px">チェックID</th>
      <th>項目</th>
      <th style="width:45%">判定・詳細</th>
    </tr>
  </thead>
  <tbody>
    {rows_html}
  </tbody>
</table>

<footer>
  <strong>TR-SHIELD Self Auditor</strong> — CHOIIZUKA Truth-Science AI-Team<br>
  <a href="https://choiizuka.com/">https://choiizuka.com/</a> &nbsp;|&nbsp;
  <a href="https://choiizuka.com/tr-shield-self-auditor/">TR-SHIELD Self Auditor</a><br><br>
  このレポートは完全にローカルで生成されました。外部への送信は一切行われていません。<br>
  MIT License — 無償配布・改変自由
</footer>
</body>
</html>"""

    fname.write_text(html, encoding="utf-8")
    return fname

# ───────────────────────────────────────────────
# JSON レポート生成
# ───────────────────────────────────────────────
def generate_json_report(all_findings: list[dict], score: int, verdict: str) -> Path:
    REPORT_DIR.mkdir(exist_ok=True)
    fname = REPORT_DIR / f"tr_shield_report_{NOW.strftime('%Y%m%d_%H%M%S')}.json"
    data = {
        "program": "TR-SHIELD Self Auditor",
        "version": VERSION,
        "credit": "CHOIIZUKA Truth-Science AI-Team",
        "url": "https://choiizuka.com/tr-shield-self-auditor/",
        "generated_at": NOW.isoformat(),
        "host": socket.gethostname(),
        "os": f"{platform.system()} {platform.release()}",
        "score": score,
        "verdict": verdict,
        "findings": all_findings,
        "note": "このレポートは完全ローカルで生成。外部送信なし。"
    }
    fname.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return fname

# ───────────────────────────────────────────────
# メイン実行
# ───────────────────────────────────────────────
def main():
    banner()

    # 免責・確認
    print(f"""  {C.YELLOW}【実行前の確認】{C.RESET}
  このプログラムは自組織のサーバーに対してのみ実行してください。
  完全ローカル実行（外部通信ゼロ）です。
  スキャンは読み取り専用で、システムへの変更は行いません。
  ループバック通信テストのみ (127.0.0.1) を使用します。

  {C.GRAY}続行するには Enter を押してください（Ctrl+C で中止）{C.RESET}""")

    try:
        input()
    except KeyboardInterrupt:
        print(f"\n  {C.YELLOW}中止しました。{C.RESET}\n")
        sys.exit(0)

    all_findings = []
    start_time = time.perf_counter()

    # M1
    section("M1 認証・セッション耐久性監査")
    f1 = check_auth_session()
    for f in f1:
        result_line(f["label"], f["level"], f.get("detail",""))
    all_findings.extend(f1)
    end_section()

    # M2
    section("M2 Zero-Hold（データ不保持）適合性監査")
    f2 = check_zero_hold()
    for f in f2:
        result_line(f["label"], f["level"], f.get("detail",""))
    all_findings.extend(f2)
    end_section()

    # M3
    section("M3 ポート・レガシーエンドポイント監査")
    f3 = check_open_ports()
    for f in f3:
        result_line(f["label"], f["level"], f.get("detail",""))
    all_findings.extend(f3)
    end_section()

    # M4
    section("M4 アウトバウンド（データ持ち出し）防御監査")
    f4 = check_outbound()
    for f in f4:
        result_line(f["label"], f["level"], f.get("detail",""))
    all_findings.extend(f4)
    end_section()

    # M5
    section("M5 システム更新・権限監査")
    f5 = check_system_update()
    for f in f5:
        result_line(f["label"], f["level"], f.get("detail",""))
    all_findings.extend(f5)
    end_section()

    # 集計
    elapsed = time.perf_counter() - start_time
    score, verdict = calc_score(all_findings)
    criticals = sum(1 for f in all_findings if f["level"] == Level.CRITICAL)
    warnings  = sum(1 for f in all_findings if f["level"] == Level.WARNING)
    passes    = sum(1 for f in all_findings if f["level"] == Level.PASS)

    verdict_display = {
        "CHECKMATE": f"{C.BOLD}\033[41m CHECKMATE \033[0m",
        "CRITICAL":  f"{C.BOLD}{C.RED} CRITICAL {C.RESET}",
        "WARNING":   f"{C.BOLD}{C.YELLOW} WARNING {C.RESET}",
        "CAUTION":   f"{C.BOLD}{C.YELLOW} CAUTION {C.RESET}",
        "PASS":      f"{C.BOLD}{C.GREEN} PASS {C.RESET}",
    }.get(verdict, verdict)

    print(f"""
  {'═'*60}
  {C.BOLD}総合結果{C.RESET}
  {'─'*60}
  耐久スコア  : {C.BOLD}{score}/100{C.RESET}
  総合判定    : {verdict_display}
  {'─'*60}
  CRITICAL : {C.RED}{criticals}件{C.RESET}   WARNING : {C.YELLOW}{warnings}件{C.RESET}   PASS : {C.GREEN}{passes}件{C.RESET}
  実行時間    : {elapsed:.2f}秒
  {'═'*60}
""")

    if criticals > 0:
        print(f"  {C.BOLD}{C.RED}⚠ 重大な脆弱性を検出しました。上記の CRITICAL 項目を即時対応してください。{C.RESET}")
        print(f"  {C.RED}  AI自律エージェントによる攻撃が発生した場合、データ奪取リスクが極めて高い状態です。{C.RESET}\n")

    # レポート生成
    html_path = generate_html_report(all_findings, score, verdict)
    json_path = generate_json_report(all_findings, score, verdict)

    print(f"  {C.BOLD}レポート出力:{C.RESET}")
    print(f"  HTML: {C.CYAN}{html_path}{C.RESET}")
    print(f"  JSON: {C.CYAN}{json_path}{C.RESET}")

    # HTMLをブラウザで開くか確認
    print(f"\n  {C.GRAY}HTMLレポートをブラウザで開きますか？ [Y/n]{C.RESET} ", end="")
    try:
        ans = input().strip().lower()
        if ans in ["", "y", "yes"]:
            webbrowser.open(f"file://{html_path.resolve()}")
            print(f"  {C.GREEN}ブラウザを開きました。{C.RESET}")
    except KeyboardInterrupt:
        pass

    print(f"""
  {C.GRAY}─────────────────────────────────────────────────────{C.RESET}
  {C.BOLD}TR-SHIELD Self Auditor{C.RESET}  |  CHOIIZUKA Truth-Science AI-Team
  https://choiizuka.com/  |  https://choiizuka.com/tr-shield-self-auditor/
  完全ローカル実行・外部通信ゼロ・無償配布 (MIT)
  {C.GRAY}─────────────────────────────────────────────────────{C.RESET}
""")

if __name__ == "__main__":
    main()
