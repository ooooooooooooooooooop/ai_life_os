#!/usr/bin/env python3
"""
NameSilo域名配置助手

帮助用户快速配置NameSilo域名和HTTPS证书。
"""
import sys
import subprocess
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def print_header():
    """打印欢迎信息"""
    print("\n" + "=" * 60)
    print("NameSilo域名配置助手")
    print("=" * 60)
    print("\n本脚本将帮助你：")
    print("1. 配置DNS解析")
    print("2. 获取HTTPS证书")
    print("3. 更新服务配置")
    print("4. 测试验证\n")


def get_domain_info():
    """获取域名信息"""
    print("【第一步：域名信息】")
    print("\n请输入你的域名信息：")

    domain = input("域名（例如：example.com）: ").strip()
    if not domain:
        print("❌ 域名不能为空")
        return None

    print(f"\n域名：{domain}")
    print("\n选择子域名方案：")
    print("1. 使用子域名 wecom.{domain}（推荐）")
    print("2. 使用根域名 {domain}")
    print("3. 自定义子域名")

    choice = input("请选择 (1/2/3): ").strip()

    if choice == "1":
        subdomain = "wecom"
        full_domain = f"wecom.{domain}"
    elif choice == "2":
        subdomain = "@"
        full_domain = domain
    elif choice == "3":
        subdomain = input("输入子域名（例如：api）: ").strip()
        full_domain = f"{subdomain}.{domain}"
    else:
        print("❌ 无效选择")
        return None

    return {
        "domain": domain,
        "subdomain": subdomain,
        "full_domain": full_domain
    }


def show_dns_instructions(domain_info):
    """显示DNS配置说明"""
    print("\n" + "=" * 60)
    print("【第二步：配置DNS解析】")
    print("=" * 60)

    print(f"\n请在NameSilo管理后台添加以下DNS记录：")
    print("\n1. 登录：https://www.namesilo.com/account/login")
    print("2. 进入 Domain Manager → DNS Records")
    print("3. 添加以下记录：\n")

    if domain_info["subdomain"] == "@":
        print(f"| Type | Host | Value           | TTL   |")
        print(f"|------|------|-----------------|-------|")
        print(f"| A    | @    | 69.63.211.116   | 7207  |")
        print(f"| A    | www  | 69.63.211.116   | 7207  |")
    else:
        print(f"| Type | Host        | Value           | TTL   |")
        print(f"|------|-------------|-----------------|-------|")
        print(f"| A    | {domain_info['subdomain']:<10} | 69.63.211.116   | 7207  |")

    print(f"\n完整域名：{domain_info['full_domain']}")

    input("\n配置完成后按回车继续...")


def check_dns(domain_info):
    """检查DNS解析"""
    print("\n" + "=" * 60)
    print("【检查DNS解析】")
    print("=" * 60)

    full_domain = domain_info["full_domain"]

    print(f"\n正在检查 {full_domain} 的DNS解析...")

    try:
        # Windows使用nslookup
        result = subprocess.run(
            ["nslookup", full_domain],
            capture_output=True,
            text=True,
            timeout=10
        )

        if "69.63.211.116" in result.stdout:
            print("✅ DNS解析正确！")
            print(f"   {full_domain} -> 69.63.211.116")
            return True
        else:
            print("⚠️ DNS解析未生效或配置错误")
            print(f"\n解析结果：\n{result.stdout}")
            print("\n可能的原因：")
            print("1. DNS记录刚添加，需要等待传播（10分钟-2小时）")
            print("2. DNS记录配置错误")
            print("\n你可以稍后再运行此脚本，或手动检查：")
            print(f"   nslookup {full_domain}")

            proceed = input("\n是否继续配置？(y/n): ").strip().lower()
            return proceed == 'y'

    except Exception as e:
        print(f"❌ DNS检查失败: {e}")
        proceed = input("\n是否继续配置？(y/n): ").strip().lower()
        return proceed == 'y'


def setup_https_cert(domain_info):
    """配置HTTPS证书"""
    print("\n" + "=" * 60)
    print("【第三步：配置HTTPS证书】")
    print("=" * 60)

    full_domain = domain_info["full_domain"]

    print("\n选择证书获取方式：")
    print("1. Certbot（推荐，自动获取Let's Encrypt证书）")
    print("2. acme.sh（灵活，支持DNS验证）")
    print("3. 自签名证书（仅测试用）")
    print("4. 已有证书，跳过此步")

    choice = input("\n请选择 (1/2/3/4): ").strip()

    if choice == "1":
        return setup_certbot(full_domain)
    elif choice == "2":
        return setup_acme_sh(full_domain)
    elif choice == "3":
        return setup_self_signed(full_domain)
    elif choice == "4":
        cert_path = input("证书文件路径 (fullchain.pem): ").strip()
        key_path = input("私钥文件路径 (privkey.pem): ").strip()
        return {"cert_path": cert_path, "key_path": key_path}
    else:
        print("❌ 无效选择")
        return None


def setup_certbot(domain):
    """使用Certbot获取证书"""
    print(f"\n正在使用Certbot获取证书：{domain}")

    print("\n前提条件：")
    print("1. 已安装Certbot")
    print("2. DNS已正确解析")
    print("3. 80端口可访问（standalone模式）")

    input("\n准备好后按回车继续...")

    email = input("输入邮箱地址（用于证书通知）: ").strip()

    print("\n选择验证方式：")
    print("1. Standalone（需要临时停止服务）")
    print("2. Webroot（服务运行中）")
    print("3. DNS验证（推荐，无需开放端口）")

    method = input("请选择 (1/2/3): ").strip()

    try:
        if method == "1":
            cmd = [
                "certbot", "certonly",
                "--standalone",
                "-d", domain,
                "--email", email,
                "--agree-tos",
                "--no-eff-email"
            ]
        elif method == "2":
            webroot = input("输入webroot路径 (例如：/var/www/certbot): ").strip()
            cmd = [
                "certbot", "certonly",
                "--webroot",
                "-w", webroot,
                "-d", domain,
                "--email", email,
                "--agree-tos",
                "--no-eff-email"
            ]
        elif method == "3":
            print("\n将使用DNS验证，请按提示添加TXT记录")
            cmd = [
                "certbot", "certonly",
                "--manual",
                "--preferred-challenges", "dns",
                "-d", domain,
                "--email", email,
                "--agree-tos",
                "--no-eff-email"
            ]
        else:
            print("❌ 无效选择")
            return None

        print(f"\n执行命令：{' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print("✅ 证书获取成功！")
            cert_path = f"/etc/letsencrypt/live/{domain}/fullchain.pem"
            key_path = f"/etc/letsencrypt/live/{domain}/privkey.pem"
            print(f"\n证书位置：")
            print(f"  证书：{cert_path}")
            print(f"  私钥：{key_path}")
            return {"cert_path": cert_path, "key_path": key_path}
        else:
            print(f"❌ 证书获取失败：\n{result.stderr}")
            return None

    except FileNotFoundError:
        print("❌ Certbot未安装")
        print("\n安装方法：")
        print("Windows: https://dl.eff.org/certbot-beta-installer-win32.exe")
        print("Linux: sudo apt-get install certbot")
        return None
    except Exception as e:
        print(f"❌ 证书获取失败: {e}")
        return None


def setup_acme_sh(domain):
    """使用acme.sh获取证书"""
    print(f"\n使用acme.sh获取证书：{domain}")

    print("\n前提条件：")
    print("1. 已安装acme.sh")
    print("2. 有NameSilo API Key")

    input("\n准备好后按回车继续...")

    api_key = input("输入NameSilo API Key: ").strip()

    try:
        # 设置API Key
        subprocess.run(
            ["export", f"Namesilo_Key={api_key}"],
            shell=True,
            check=True
        )

        # 获取证书
        cmd = [
            "acme.sh",
            "--issue",
            "--dns", "dns_namesilo",
            "-d", domain
        ]

        print(f"\n执行命令：{' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)

        if result.returncode == 0:
            print("✅ 证书获取成功！")
            cert_path = f"~/.acme.sh/{domain}/fullchain.cer"
            key_path = f"~/.acme.sh/{domain}/{domain}.key"
            return {"cert_path": cert_path, "key_path": key_path}
        else:
            print(f"❌ 证书获取失败：\n{result.stderr}")
            return None

    except FileNotFoundError:
        print("❌ acme.sh未安装")
        print("\n安装方法：")
        print("curl https://get.acme.sh | sh")
        return None
    except Exception as e:
        print(f"❌ 证书获取失败: {e}")
        return None


def setup_self_signed(domain):
    """生成自签名证书"""
    print(f"\n生成自签名证书：{domain}")

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

        print(f"\n执行命令：{' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            print("✅ 自签名证书生成成功！")
            print(f"\n证书位置：")
            print(f"  证书：{cert_path}")
            print(f"  私钥：{key_path}")
            print("\n⚠️ 注意：自签名证书仅用于测试，浏览器会显示不安全警告")
            return {"cert_path": str(cert_path), "key_path": str(key_path)}
        else:
            print(f"❌ 证书生成失败：\n{result.stderr}")
            return None

    except FileNotFoundError:
        print("❌ OpenSSL未安装")
        return None
    except Exception as e:
        print(f"❌ 证书生成失败: {e}")
        return None


def update_service_config(domain_info, cert_info):
    """更新服务配置"""
    print("\n" + "=" * 60)
    print("【第四步：更新服务配置】")
    print("=" * 60)

    if not cert_info:
        print("❌ 缺少证书信息，无法更新配置")
        return False

    # 更新main.py
    print("\n正在更新 main.py...")

    main_py_path = project_root / "main.py"

    try:
        with open(main_py_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查是否已有SSL配置
        if "ssl_context" in content:
            print("⚠️ main.py 已包含SSL配置，请手动更新")
            print(f"\n证书路径：{cert_info['cert_path']}")
            print(f"私钥路径：{cert_info['key_path']}")
        else:
            # 添加SSL配置
            ssl_code = f'''
    # SSL配置
    ssl_context = None
    if port == 443:
        import ssl
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(
            certfile="{cert_info['cert_path']}",
            keyfile="{cert_info['key_path']}"
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


def show_final_instructions(domain_info):
    """显示最终配置说明"""
    print("\n" + "=" * 60)
    print("【配置完成】")
    print("=" * 60)

    full_domain = domain_info["full_domain"]

    print(f"\n✅ 域名配置完成！")
    print(f"\n你的服务地址：")
    print(f"  HTTPS: https://{full_domain}")
    print(f"  Health: https://{full_domain}/health")
    print(f"  Webhook: https://{full_domain}/wecom/webhook")

    print(f"\n📋 下一步操作：")
    print(f"\n1. 重启服务：")
    print(f"   python main.py")

    print(f"\n2. 在企业微信管理后台配置回调URL：")
    print(f"   https://{full_domain}/wecom/webhook")

    print(f"\n3. 运行配置脚本：")
    print(f"   python scripts/setup_wecom.py")

    print(f"\n4. 测试验证：")
    print(f"   curl https://{full_domain}/health")

    print(f"\n📚 详细文档：")
    print(f"   docs/namesilo_setup.md")
    print(f"   docs/wecom_setup_guide.md")

    print("\n" + "=" * 60)


def main():
    """主函数"""
    print_header()

    # 获取域名信息
    domain_info = get_domain_info()
    if not domain_info:
        return 1

    # 显示DNS配置说明
    show_dns_instructions(domain_info)

    # 检查DNS解析
    if not check_dns(domain_info):
        return 1

    # 配置HTTPS证书
    cert_info = setup_https_cert(domain_info)
    if not cert_info:
        print("\n❌ HTTPS证书配置失败")
        return 1

    # 更新服务配置
    if not update_service_config(domain_info, cert_info):
        return 1

    # 显示最终说明
    show_final_instructions(domain_info)

    return 0


if __name__ == "__main__":
    sys.exit(main())
