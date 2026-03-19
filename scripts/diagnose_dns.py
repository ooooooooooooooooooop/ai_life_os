#!/usr/bin/env python3
"""
DNS解析诊断脚本

检查域名DNS解析是否正确配置。
"""
import subprocess
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def check_dns(domain, expected_ip="69.63.211.116"):
    """
    检查域名DNS解析。

    Args:
        domain: 域名
        expected_ip: 期望的IP地址

    Returns:
        True 如果解析正确
    """
    print(f"\n检查域名: {domain}")
    print(f"期望IP: {expected_ip}")
    print("-" * 60)

    try:
        # 使用nslookup检查
        result = subprocess.run(
            ["nslookup", domain],
            capture_output=True,
            text=True,
            timeout=10
        )

        print(result.stdout)

        # 检查是否包含期望的IP
        if expected_ip in result.stdout:
            print(f"✅ DNS解析正确！")
            return True
        else:
            print(f"❌ DNS解析不正确")
            print(f"   期望: {expected_ip}")
            print(f"   实际: {result.stdout}")

            # 检查是否有CDN或代理
            if "192.124.249.6" in result.stdout:
                print("\n⚠️ 检测到可能的CDN或代理服务")
                print("   IP 192.124.249.6 可能是：")
                print("   - Cloudflare CDN")
                print("   - Sucuri Firewall")
                print("   - 其他安全代理")

            return False

    except subprocess.TimeoutExpired:
        print("❌ DNS查询超时")
        return False
    except Exception as e:
        print(f"❌ DNS检查失败: {e}")
        return False


def check_dns_propagation(domain):
    """
    检查DNS传播状态。

    Args:
        domain: 域名
    """
    print(f"\n检查DNS传播状态: {domain}")
    print("-" * 60)

    # 使用在线DNS检查工具
    print("\n建议使用以下在线工具检查DNS传播：")
    print(f"1. https://dnschecker.org/#A/{domain}")
    print(f"2. https://www.whatsmydns.net/#A/{domain}")
    print(f"3. https://viewdns.info/propagation.php?domain={domain}")


def main():
    """主函数"""
    print("=" * 60)
    print("DNS解析诊断工具")
    print("=" * 60)

    # 获取域名
    print("\n请输入你的域名（例如：example.com）：")
    domain = input("域名: ").strip()

    if not domain:
        print("❌ 域名不能为空")
        return 1

    # 检查主域名
    check_dns(domain)

    # 检查www子域名
    check_dns(f"www.{domain}")

    # 检查ailife子域名
    check_dns(f"ailife.{domain}")

    # 检查DNS传播
    check_dns_propagation(domain)

    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)

    print("\n如果DNS解析不正确，可能的原因：")
    print("1. DNS记录刚添加，需要等待传播（10分钟-48小时）")
    print("2. 域名使用了CDN或代理服务")
    print("3. DNS记录配置错误")
    print("4. 本地DNS缓存未更新")

    print("\n解决方法：")
    print("1. 等待DNS传播完成")
    print("2. 清除本地DNS缓存：")
    print("   Windows: ipconfig /flushdns")
    print("   Linux: sudo systemd-resolve --flush-caches")
    print("3. 使用在线工具检查DNS传播状态")
    print("4. 检查域名是否启用了CDN或代理服务")

    return 0


if __name__ == "__main__":
    sys.exit(main())
