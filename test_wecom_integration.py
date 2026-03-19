"""
企业微信接入功能测试脚本

用于验证企业微信接入功能的基本功能。
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_imports():
    """测试模块导入"""
    print("=" * 60)
    print("测试 1: 模块导入")
    print("=" * 60)

    try:
        from interface.wecom_models import WeComConfig, WeComMessage, WeComAPIResponse
        print("[OK] wecom_models 导入成功")
    except Exception as e:
        print(f"[FAIL] wecom_models 导入失败: {e}")
        return False

    try:
        from interface.notifiers.wecom_notifier import WeComNotifier
        print("[OK] wecom_notifier 导入成功")
    except Exception as e:
        print(f"[FAIL] wecom_notifier 导入失败: {e}")
        return False

    try:
        from interface.wecom_bot import router
        print("[OK] wecom_bot 导入成功")
    except Exception as e:
        print(f"[FAIL] wecom_bot 导入失败: {e}")
        return False

    print("\n所有模块导入成功！\n")
    return True


def test_config_loading():
    """测试配置加载"""
    print("=" * 60)
    print("测试 2: 配置加载")
    print("=" * 60)

    try:
        from interface.wecom_models import WeComConfig

        # 测试默认配置
        config = WeComConfig(
            corp_id="test_corp_id",
            corp_secret="test_corp_secret",
            agent_id="test_agent_id"
        )

        print(f"[OK] 配置创建成功")
        print(f"  - corp_id: {config.corp_id}")
        print(f"  - agent_id: {config.agent_id}")
        print(f"  - to_user: {config.to_user}")
        print(f"  - enabled: {config.enabled}")
        print(f"  - is_configured: {config.is_configured()}")

        # 测试配置文件加载
        import yaml
        config_path = Path("config/wecom.yaml")
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                file_config = yaml.safe_load(f)
            print(f"\n[OK] 配置文件加载成功")
            print(f"  - 文件路径: {config_path}")
            print(f"  - enabled: {file_config.get('enabled', False)}")
        else:
            print(f"\n[WARN] 配置文件不存在: {config_path}")

        print("\n配置加载测试通过！\n")
        return True

    except Exception as e:
        print(f"[FAIL] 配置加载测试失败: {e}")
        return False


def test_notifier_initialization():
    """测试 Notifier 初始化"""
    print("=" * 60)
    print("测试 3: Notifier 初始化")
    print("=" * 60)

    try:
        from interface.notifiers.wecom_notifier import WeComNotifier

        # 测试默认初始化（从配置文件加载）
        notifier = WeComNotifier()
        print(f"[OK] Notifier 初始化成功")
        print(f"  - name: {notifier.get_name()}")
        print(f"  - enabled: {notifier.enabled}")
        print(f"  - available: {notifier.is_available()}")

        # 测试自定义配置初始化
        custom_config = {
            "corp_id": "test_corp",
            "corp_secret": "test_secret",
            "agent_id": "1000001",
            "enabled": True
        }
        notifier_custom = WeComNotifier(config=custom_config)
        print(f"\n[OK] 自定义配置 Notifier 初始化成功")
        print(f"  - enabled: {notifier_custom.enabled}")
        print(f"  - available: {notifier_custom.is_available()}")

        print("\nNotifier 初始化测试通过！\n")
        return True

    except Exception as e:
        print(f"[FAIL] Notifier 初始化测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_xml_parsing():
    """测试 XML 解析"""
    print("=" * 60)
    print("测试 4: XML 解析")
    print("=" * 60)

    try:
        from interface.wecom_bot import _parse_xml_message, _build_xml_response

        # 测试 XML 解析
        test_xml = """<xml>
<ToUserName><![CDATA[toUser]]></ToUserName>
<FromUserName><![CDATA[fromUser]]></FromUserName>
<CreateTime>1348831860</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[this is a test]]></Content>
<MsgId>1234567890123456</MsgId>
<AgentID>1</AgentID>
</xml>"""

        msg_dict = _parse_xml_message(test_xml)
        if msg_dict:
            print(f"[OK] XML 解析成功")
            print(f"  - to_user_name: {msg_dict.get('to_user_name')}")
            print(f"  - from_user_name: {msg_dict.get('from_user_name')}")
            print(f"  - content: {msg_dict.get('content')}")
            print(f"  - msg_type: {msg_dict.get('msg_type')}")
        else:
            print(f"[FAIL] XML 解析失败")
            return False

        # 测试 XML 构造
        reply_xml = _build_xml_response(
            to_user="fromUser",
            from_user="toUser",
            content="这是回复消息"
        )
        print(f"\n[OK] XML 构造成功")
        print(f"  - XML 长度: {len(reply_xml)}")

        print("\nXML 解析测试通过！\n")
        return True

    except Exception as e:
        print(f"[FAIL] XML 解析测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cron_scheduler():
    """测试定时调度器"""
    print("=" * 60)
    print("测试 5: 定时调度器")
    print("=" * 60)

    try:
        from scheduler.cron_scheduler import get_scheduler

        scheduler = get_scheduler()
        print(f"[OK] 调度器获取成功")

        # 检查企业微信早安推送任务是否注册
        if "wecom-morning-push" in scheduler.jobs:
            job = scheduler.jobs["wecom-morning-push"]
            print(f"[OK] 企业微信早安推送任务已注册")
            print(f"  - name: {job.name}")
            print(f"  - cron: {job.cron_expr}")
            print(f"  - enabled: {job.enabled}")
        else:
            print(f"[WARN] 企业微信早安推送任务未注册（需要先加载配置）")

        print("\n定时调度器测试通过！\n")
        return True

    except Exception as e:
        print(f"[FAIL] 定时调度器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("企业微信接入功能测试")
    print("=" * 60 + "\n")

    tests = [
        test_imports,
        test_config_loading,
        test_notifier_initialization,
        test_xml_parsing,
        test_cron_scheduler
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"测试异常: {e}")
            results.append(False)

    # 总结
    print("=" * 60)
    print("测试总结")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"通过: {passed}/{total}")

    if passed == total:
        print("\n[OK] 所有测试通过！")
        return 0
    else:
        print(f"\n[FAIL] {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
