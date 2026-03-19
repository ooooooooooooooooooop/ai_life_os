#!/usr/bin/env python3
"""
企业微信配置助手

交互式配置企业微信应用信息。
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("企业微信配置助手")
    print("=" * 60)
    print()

    # 配置文件路径
    config_file = project_root / "config" / "wecom.yaml"

    print("请按照提示输入企业微信配置信息：\n")

    # 读取企业ID
    print("【企业ID】")
    print("获取方式：企业微信管理后台 -> 我的企业 -> 企业信息")
    corp_id = input("请输入企业ID: ").strip()

    # 读取应用Secret
    print("\n【应用Secret】")
    print("获取方式：企业微信管理后台 -> 应用管理 -> 选择应用 -> 查看应用详情")
    corp_secret = input("请输入应用Secret: ").strip()

    # 读取应用AgentId
    print("\n【应用AgentId】")
    print("获取方式：企业微信管理后台 -> 应用管理 -> 选择应用 -> 查看应用详情")
    agent_id = input("请输入应用AgentId: ").strip()

    # 读取Token
    print("\n【消息加密Token】")
    print("建议使用：ailifeos2026")
    token = input("请输入Token (直接回车使用默认值 ailifeos2026): ").strip()
    if not token:
        token = "ailifeos2026"

    # 读取EncodingAESKey
    print("\n【消息加密EncodingAESKey】")
    print("测试阶段可以留空，生产环境建议在企业微信后台生成")
    encoding_aes_key = input("请输入EncodingAESKey (留空则不加密): ").strip()

    # 显示配置摘要
    print("\n" + "=" * 60)
    print("配置摘要")
    print("=" * 60)
    print(f"企业ID: {corp_id}")
    print(f"应用Secret: {corp_secret[:10]}...")
    print(f"应用AgentId: {agent_id}")
    print(f"Token: {token}")
    print(f"EncodingAESKey: {encoding_aes_key if encoding_aes_key else '不加密'}")
    print()

    confirm = input("确认保存配置? (y/n): ").strip().lower()
    if confirm != 'y':
        print("已取消配置")
        return 1

    # 生成配置文件内容
    config_content = f"""# 企业微信配置
# 用于企业微信消息接收和推送功能

# 企业 ID（必填）
# 在企业微信管理后台 -> 我的企业 -> 企业信息 中查看
corp_id: "{corp_id}"

# 应用 Secret（必填）
# 在企业微信管理后台 -> 应用管理 -> 选择应用 -> 查看应用详情 中查看
corp_secret: "{corp_secret}"

# 应用 AgentId（必填）
# 在企业微信管理后台 -> 应用管理 -> 选择应用 -> 查看应用详情 中查看
agent_id: "{agent_id}"

# 默认推送对象（可选，默认值：@all）
# 可以是用户 ID、部门 ID 或标签 ID
# 例如：
#   - "@all"：推送给所有用户
#   - "zhangsan"：推送给指定用户
#   - "zhangsan|lisi"：推送给多个用户（用 | 分隔）
to_user: "@all"

# 消息加密 Token（可选）
# 如果配置了消息加密，需要填写此项
# 在企业微信管理后台 -> 应用管理 -> 选择应用 -> 设置 API 接收 中配置
token: "{token}"

# 消息加密 EncodingAESKey（可选）
# 如果配置了消息加密，需要填写此项
# 在企业微信管理后台 -> 应用管理 -> 选择应用 -> 设置 API 接收 中配置
encoding_aes_key: "{encoding_aes_key}"

# 是否启用企业微信接入（可选，默认值：false）
# 设置为 true 后，系统将启用企业微信消息接收和推送功能
enabled: true
"""

    # 写入配置文件
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            f.write(config_content)
        
        print(f"\n✅ 配置已保存到: {config_file}")
        print("\n下一步：")
        print("1. 在企业微信后台配置回调URL: http://ailife.wurank.top:8000/wecom/webhook")
        print(f"2. Token填写: {token}")
        print(f"3. EncodingAESKey填写: {encoding_aes_key if encoding_aes_key else '留空'}")
        print("4. 重启服务: C:\\tools\\winsw\\restart_ai_life_os.bat")
        print()
        
        return 0
        
    except Exception as e:
        print(f"\n❌ 配置保存失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
