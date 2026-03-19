#!/usr/bin/env python3
"""
WURANK.TOP 域名HTTPS配置脚本

自动配置ailife.wurank.top的HTTPS证书和服务。
"""
import os
import sys
import subprocess
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def print_header():
    """打印欢迎信息"""
    print("\n" + "=" * 60)
    print("WURANK.TOP HTTPS配置助手")
    print("=" * 60)
    print("\n域名：ailife.wurank.top")
    print("IP地址：69.63.211.116")
    print("DNS状态：✅ 已正确解析\n")


def check_certbot():
    """检查Certbot是否已安装"""
    try:
        result = subprocess.run(
            ["certbot", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("✅ Certbot已安装")
            print(f"   版本: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        print("❌ Certbot未安装")
        return False
    except Exception as e:
        print(f"⚠️ Certbot检查失败: {e}")
        return False


def install_certbot():
    """安装Certbot"""
    print("\n" + "=" * 60)
    print("安装Certbot")
    print("=" * 60)

    print("\n选择安装方式：")
    print("1. 使用Chocolatey（推荐）")
    print("2. 手动下载安装器")
    print("3. 跳过（已安装或使用其他方式）")

    choice = input("\n请选择 (1/2/3): ").strip()

    if choice == "1":
        print("\n正在使用Chocolatey安装Certbot...")
        try:
            result = subprocess.run(
                ["choco", "install", "certbot", "-y"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print("✅ Certbot安装成功")
                return True
            else:
                print(f"❌ 安装失败: {result.stderr}")
                return False
        except FileNotFoundError:
            print("❌ Chocolatey未安装")
            print("\n安装Chocolatey:")
            print("Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))")
            return False

    elif choice == "2":
        print("\n请手动下载并安装Certbot:")
        print("https://dl.eff.org/certbot-beta-installer-win32.exe")
        input("\n安装完成后按回车继续...")
        return check_certbot()

    elif choice == "3":
        return check_certbot()

    else:
        print("❌ 无效选择")
        return False


def get_certificate():
    """获取HTTPS证书"""
    print("\n" + "=" * 60)
    print("获取HTTPS证书")
    print("=" * 60)

    domain = "ailife.wurank.top"

    print(f"\n域名: {domain}")
    print("\n选择证书获取方式：")
    print("1. Standalone模式（需要临时停止服务）")
    print("2. Webroot模式（服务运行中）")
    print("3. 手动DNS验证")
    print("4. 使用自签名证书（仅测试）")
    print("5. 跳过（已有证书）")

    choice = input("\n请选择 (1/2/3/4/5): ").strip()

    if choice == "1":
        return get_cert_standalone(domain)
    elif choice == "2":
        return get_cert_webroot(domain)
    elif choice == "3":
        return get_cert_dns(domain)
    elif choice == "4":
        return get_self_signed_cert(domain)
    elif choice == "5":
        cert_path = input("证书文件路径 (fullchain.pem): ").strip()
        key_path = input("私钥文件路径 (privkey.pem): ").strip()
        return {"cert_path": cert_path, "key_path": key_path}
    else:
        print("❌ 无效选择")
        return None


def get_cert_standalone(domain):
    """使用standalone模式获取证书"""
    print(f"\n使用Standalone模式获取证书: {domain}")

    print("\n⚠️ 注意：此模式需要临时停止占用80端口的服务")
    proceed = input("是否继续？(y/n): ").strip().lower()
    if proceed != 'y':
        return None

    email = input("输入邮箱地址（用于证书通知）: ").strip()

    try:
        cmd = [
            "certbot", "certonly",
            "--standalone",
            "-d", domain,
            "--email", email,
            "--agree-tos",
            "--no-eff-email"
        ]

        print(f"\n执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print("✅ 证书获取成功！")
            cert_path = f"C:/Certbot/live/{domain}/fullchain.pem"
            key_path = f"C:/Certbot/live/{domain}/privkey.pem"
            print(f"\n证书位置:")
            print(f"  证书: {cert_path}")
            print(f"  私钥: {key_path}")
            return {"cert_path": cert_path, "key_path": key_path}
        else:
            print(f"❌ 证书获取失败:\n{result.stderr}")
            return None

    except Exception as e:
        print(f"❌ 证书获取失败: {e}")
        return None


def get_cert_webroot(domain):
    """使用webroot模式获取证书"""
    print(f"\n使用Webroot模式获取证书: {domain}")

    webroot = input("输入webroot路径 (例如: C:/webroot): ").strip()
    email = input("输入邮箱地址: ").strip()

    try:
        cmd = [
            "certbot", "certonly",
            "--webroot",
            "-w", webroot,
            "-d", domain,
            "--email", email,
            "--agree-tos",
            "--no-eff-email"
        ]

        print(f"\n执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print("✅ 证书获取成功！")
            cert_path = f"C:/Certbot/live/{domain}/fullchain.pem"
            key_path = f"C:/Certbot/live/{domain}/privkey.pem"
            return {"cert_path": cert_path, "key_path": key_path}
        else:
            print(f"❌ 证书获取失败:\n{result.stderr}")
            return None

    except Exception as e:
        print(f"❌ 证书获取失败: {e}")
        return None


def get_cert_dns(domain):
    """使用DNS验证获取证书"""
    print(f"\n使用DNS验证获取证书: {domain}")

    print("\n将使用DNS验证，请按提示添加TXT记录")
    email = input("输入邮箱地址: ").strip()

    try:
        cmd = [
            "certbot", "certonly",
            "--manual",
            "--preferred-challenges", "dns",
            "-d", domain,
            "--email", email,
            "--agree-tos",
            "--no-eff-email"
        ]

        print(f"\n执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print("✅ 证书获取成功！")
            cert_path = f"C:/Certbot/live/{domain}/fullchain.pem"
            key_path = f"C:/Certbot/live/{domain}/privkey.pem"
            return {"cert_path": cert_path, "key_path": key_path}
        else:
            print(f"❌ 证书获取失败:\n{result.stderr}")
            return None

    except Exception as e:
        print(f"❌ 证书获取失败: {e}")
        return None


def get_self_signed_cert(domain):
    """生成自签名证书"""
    print(f"\n生成自签名证书: {domain}")

    cert_dir = project_root / "certs"
    cert_dir.mkdir(exist_ok=True)

    cert_path = cert_dir / "cert.pem"
    key_path = cert_dir / "key.pem"

    try:
        cmd = [
            "openssl", "req",
            "-x509",
            "-newkey", "rsa:4096",
            "-keyout", str(key_path),
            "-out", str(cert_path),
            "-days", "365",
            "-nodes",
            "-subj", f"/CN={domain}"
        ]

        print(f"\n执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print("✅ 自签名证书生成成功！")
            print(f"\n证书位置:")
            print(f"  证书: {cert_path}")
            print(f"  私钥: {key_path}")
            print("\n⚠️ 注意：自签名证书仅用于测试，浏览器会显示不安全警告")
            return {"cert_path": str(cert_path), "key_path": str(key_path)}
        else:
            print(f"❌ 证书生成失败:\n{result.stderr}")
            return None

    except Exception as e:
        print(f"❌ 证书生成失败: {e}")
        return None


def configure_firewall():
    """配置防火墙"""
    print("\n" + "=" * 60)
    print("配置防火墙")
    print("=" * 60)

    print("\n是否配置防火墙允许HTTPS流量？(y/n): ")
    choice = input().strip().lower()

    if choice == 'y':
        try:
            # 允许HTTPS
            subprocess.run(
                ['New-NetFirewallRule', '-DisplayName', 'HTTPS',
                 '-Direction', 'Inbound', '-LocalPort', '443',
                 '-Protocol', 'TCP', '-Action', 'Allow'],
                check=True
            )
            print("✅ 防火墙规则已添加")

            # 允许HTTP（用于证书获取）
            subprocess.run(
                ['New-NetFirewallRule', '-DisplayName', 'HTTP',
                 '-Direction', 'Inbound', '-LocalPort', '80',
                 '-Protocol', 'TCP', '-Action', 'Allow'],
                check=True
            )
            print("✅ HTTP端口已开放（用于证书获取）")

        except Exception as e:
            print(f"⚠️ 防火墙配置失败: {e}")
            print("请手动配置防火墙允许443和80端口")


def update_main_py(cert_info):
    """更新main.py配置"""
    print("\n" + "=" * 60)
    print("更新服务配置")
    print("=" * 60)

    if not cert_info:
        print("❌ 缺少证书信息")
        return False

    main_py_path = project_root / "main.py"

    try:
        with open(main_py_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查是否已有SSL配置
        if "ssl_context" in content:
            print("⚠️ main.py 已包含SSL配置")
            print(f"\n请手动更新证书路径:")
            print(f"  证书: {cert_info['cert_path']}")
            print(f"  私钥: {cert_info['key_path']}")
            return True

        # 添加SSL配置
        ssl_code = f'''
    # SSL配置
    ssl_context = None
    if port == 443:
        import ssl
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(
            certfile=r"{cert_info['cert_path']}",
            keyfile=r"{cert_info['key_path']}"
        )
'''

        # 在uvicorn.run之前插入
        content = content.replace(
            "    uvicorn.run(",
            ssl_code + "\n    uvicorn.run("
        )

        # 添加ssl参数
        content = content.replace(
            'reload_dirs=["web", "core"] if reload_enabled else None,',
            'reload_dirs=["web", "core"] if reload_enabled else None,\n        ssl=ssl_context,'
        )

        with open(main_py_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print("✅ main.py 已更新")
        return True

    except Exception as e:
        print(f"❌ 更新配置失败: {e}")
        return False


def show_final_instructions():
    """显示最终配置说明"""
    print("\n" + "=" * 60)
    print("配置完成！")
    print("=" * 60)

    domain = "ailife.wurank.top"

    print(f"\n✅ HTTPS配置完成！")
    print(f"\n你的服务地址：")
    print(f"  HTTPS: https://{domain}")
    print(f"  Health: https://{domain}/health")
    print(f"  Webhook: https://{domain}/wecom/webhook")

    print(f"\n📋 下一步操作：")
    print(f"\n1. 启动服务（使用HTTPS）：")
    print(f"   python main.py")

    print(f"\n2. 测试HTTPS访问：")
    print(f"   curl https://{domain}/health")

    print(f"\n3. 在企业微信管理后台配置回调URL：")
    print(f"   https://{domain}/wecom/webhook")

    print(f"\n4. 运行企业微信配置脚本：")
    print(f"   python scripts/setup_wecom.py")

    print(f"\n📚 详细文档：")
    print(f"   docs/wurank_setup.md")
    print(f"   docs/wecom_setup_guide.md")

    print("\n" + "=" * 60)


def main():
    """主函数"""
    print_header()

    # 检查并安装Certbot
    if not check_certbot():
        if not install_certbot():
            print("\n❌ Certbot安装失败，无法继续")
            return 1

    # 获取证书
    cert_info = get_certificate()
    if not cert_info:
        print("\n❌ 证书获取失败")
        return 1

    # 配置防火墙
    configure_firewall()

    # 更新服务配置
    if not update_main_py(cert_info):
        return 1

    # 显示最终说明
    show_final_instructions()

    return 0


if __name__ == "__main__":
    sys.exit(main())
