#!/bin/bash

echo "============================================================"
echo "企业微信配置助手"
echo "============================================================"
echo ""

# 读取当前配置
CONFIG_FILE="/c/Desktop/learn/ai_life_os/config/wecom.yaml"

echo "请按照提示输入企业微信配置信息："
echo ""

# 读取企业ID
echo "【企业ID】"
echo "获取方式：企业微信管理后台 -> 我的企业 -> 企业信息"
read -p "请输入企业ID: " corp_id

# 读取应用Secret
echo ""
echo "【应用Secret】"
echo "获取方式：企业微信管理后台 -> 应用管理 -> 选择应用 -> 查看应用详情"
read -p "请输入应用Secret: " corp_secret

# 读取应用AgentId
echo ""
echo "【应用AgentId】"
echo "获取方式：企业微信管理后台 -> 应用管理 -> 选择应用 -> 查看应用详情"
read -p "请输入应用AgentId: " agent_id

# 读取Token
echo ""
echo "【消息加密Token】"
echo "建议使用：ailifeos2026"
read -p "请输入Token (直接回车使用默认值 ailifeos2026): " token
token=${token:-ailifeos2026}

# 读取EncodingAESKey
echo ""
echo "【消息加密EncodingAESKey】"
echo "测试阶段可以留空，生产环境建议在企业微信后台生成"
read -p "请输入EncodingAESKey (留空则不加密): " encoding_aes_key

# 显示配置摘要
echo ""
echo "============================================================"
echo "配置摘要"
echo "============================================================"
echo "企业ID: $corp_id"
echo "应用Secret: ${corp_secret:0:10}..."
echo "应用AgentId: $agent_id"
echo "Token: $token"
echo "EncodingAESKey: ${encoding_aes_key:-不加密}"
echo ""

read -p "确认保存配置? (y/n): " confirm
if [ "$confirm" != "y" ]; then
    echo "已取消配置"
    exit 1
fi

# 更新配置文件
cat > "$CONFIG_FILE" << EOF
# 企业微信配置
# 用于企业微信消息接收和推送功能

# 企业 ID（必填）
# 在企业微信管理后台 -> 我的企业 -> 企业信息 中查看
corp_id: "$corp_id"

# 应用 Secret（必填）
# 在企业微信管理后台 -> 应用管理 -> 选择应用 -> 查看应用详情 中查看
corp_secret: "$corp_secret"

# 应用 AgentId（必填）
# 在企业微信管理后台 -> 应用管理 -> 选择应用 -> 查看应用详情 中查看
agent_id: "$agent_id"

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
token: "$token"

# 消息加密 EncodingAESKey（可选）
# 如果配置了消息加密，需要填写此项
# 在企业微信管理后台 -> 应用管理 -> 选择应用 -> 设置 API 接收 中配置
encoding_aes_key: "$encoding_aes_key"

# 是否启用企业微信接入（可选，默认值：false）
# 设置为 true 后，系统将启用企业微信消息接收和推送功能
enabled: true
EOF

echo ""
echo "✅ 配置已保存到: $CONFIG_FILE"
echo ""
echo "下一步："
echo "1. 在企业微信后台配置回调URL: http://ailife.wurank.top:8000/wecom/webhook"
echo "2. Token填写: $token"
echo "3. EncodingAESKey填写: ${encoding_aes_key:-留空}"
echo "4. 重启服务: C:\tools\winsw\restart_ai_life_os.bat"
echo ""
