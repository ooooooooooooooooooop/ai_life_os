#!/usr/bin/env python3
"""
企业微信快速配置脚本

交互式配置企业微信机器人，自动更新配置文件。
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import yaml


def print_header():
    """打印欢迎信息"""
    print("\n" + "=" * 60)
    print("企业微信机器人配置向导")
    print("=" * 60)
    print("\n请按照提示输入企业微信应用信息")
    print("如果不确定，可以参考 docs/wecom_setup_guide.md\n")


def get_input(prompt: str, default: str = "", required: bool = True) -> str:
    """
    获取用户输入。

    Args:
        prompt: 提示信息
        default: 默认值
        required: 是否必填

    Returns:
        用户输入的值
    """
    if default:
        prompt_text = f"{prompt} (默认: {default}): "
    else:
        prompt_text = f"{prompt}: "

    while True:
        value = input(prompt_text).strip()

        if not value:
            if default:
                return default
            elif not required:
                return ""
            else:
                print("❌ 此项为必填项，请重新输入")
                continue

        return value


def validate_config(config: dict) -> bool:
    """
    验证配置是否完整。

    Args:
        config: 配置字典

    Returns:
        True 如果配置有效
    """
    required_fields = ["corp_id", "corp_secret", "agent_id"]
    missing = [field for field in required_fields if not config.get(field)]

    if missing:
        print(f"\n❌ 缺少必填字段: {', '.join(missing)}")
        return False

    return True


def update_config_file(config: dict):
    """
    更新配置文件。

    Args:
        config: 配置字典
    """
    config_path = project_root / "config" / "wecom.yaml"

    # 读取现有配置
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            existing_config = yaml.safe_load(f) or {}
    else:
        existing_config = {}

    # 更新配置
    existing_config.update(config)

    # 写回文件
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(existing_config, f, allow_unicode=True, default_flow_style=False)

    print(f"\n✅ 配置已保存到: {config_path}")


def test_connection():
    """测试企业微信连接"""
    print("\n" + "=" * 60)
    print("测试企业微信连接")
    print("=" * 60)

    try:
        from interface.notifiers.wecom_notifier import WeComNotifier

        notifier = WeComNotifier()

        print(f"\n配置状态:")
        print(f"  - 企业ID: {notifier.wecom_config.corp_id[:10]}...")
        print(f"  - AgentId: {notifier.wecom_config.agent_id}")
        print(f"  - 已启用: {notifier.enabled}")
        print(f"  - 可用性: {notifier.is_available()}")

        # 尝试获取 access_token
        print("\n正在获取 access_token...")
        access_token = notifier._get_access_token()

        if access_token:
            print("✅ 成功获取 access_token")
            print(f"   Token: {access_token[:20]}...")

            # 询问是否发送测试消息
            send_test = input("\n是否发送测试消息? (y/n): ").strip().lower()
            if send_test == 'y':
                print("\n正在发送测试消息...")
                success = notifier.send_raw("🎉 企业微信机器人配置成功！\n\n这是来自 AI Life OS 的测试消息。")
                if success:
                    print("✅ 测试消息发送成功！请检查企业微信")
                else:
                    print("❌ 测试消息发送失败")
        else:
            print("❌ 获取 access_token 失败")
            print("   请检查 corp_id 和 corp_secret 是否正确")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主函数"""
    print_header()

    # 收集配置信息
    print("【必填信息】")
    corp_id = get_input("企业ID (corp_id)")
    corp_secret = get_input("应用Secret (corp_secret)")
    agent_id = get_input("应用AgentId (agent_id)")

    print("\n【可选配置】")
    to_user = get_input("默认推送对象", default="@all", required=False)
    token = get_input("消息加密Token (不加密可留空)", required=False)
    encoding_aes_key = get_input("消息加密Key (不加密可留空)", required=False)

    # 构建配置
    config = {
        "corp_id": corp_id,
        "corp_secret": corp_secret,
        "agent_id": agent_id,
        "to_user": to_user,
        "enabled": True  # 自动启用
    }

    if token:
        config["token"] = token
    if encoding_aes_key:
        config["encoding_aes_key"] = encoding_aes_key

    # 验证配置
    if not validate_config(config):
        print("\n❌ 配置验证失败，请重新运行脚本")
        return 1

    # 显示配置摘要
    print("\n" + "=" * 60)
    print("配置摘要")
    print("=" * 60)
    for key, value in config.items():
        if key == "corp_secret":
            print(f"  {key}: {'*' * 20}")
        else:
            print(f"  {key}: {value}")

    # 确认保存
    confirm = input("\n确认保存配置? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ 已取消配置")
        return 1

    # 保存配置
    update_config_file(config)

    # 测试连接
    test = input("\n是否测试连接? (y/n): ").strip().lower()
    if test == 'y':
        test_connection()

    print("\n" + "=" * 60)
    print("配置完成！")
    print("=" * 60)
    print("\n下一步:")
    print("1. 在企业微信后台配置回调URL:")
    print(f"   http://69.63.211.116:8000/wecom/webhook")
    print("2. 重启服务: python main.py")
    print("3. 在企业微信中发送消息测试")
    print("\n详细说明请参考: docs/wecom_setup_guide.md\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
