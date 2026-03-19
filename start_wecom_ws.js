/**
 * 企业微信 WebSocket 长连接客户端
 * 使用官方 SDK @wecom/aibot-node-sdk
 */
const AiBot = require('@wecom/aibot-node-sdk');
const { generateReqId } = require('@wecom/aibot-node-sdk');

// 配置参数
const BOT_ID = '1000002';
const SECRET = 'ytH5r7WKSmzoI9i2Zf4QOrVcC7gw_RMPjSP-XrCRc2E';

// 创建客户端
const wsClient = new AiBot.WSClient({
  botId: BOT_ID,
  secret: SECRET,
});

console.log('🚀 启动企业微信 WebSocket 客户端...');
console.log(`bot_id: ${BOT_ID}`);
console.log('✅ 无需公网IP，无需域名备案');

// 连接
wsClient.connect();

// 认证成功
wsClient.on('authenticated', () => {
  console.log('🔐 认证成功');
});

// 连接关闭
wsClient.on('disconnected', () => {
  console.log('❌ 连接已关闭');
});

// 错误处理
wsClient.on('error', (err) => {
  console.error('❌ 错误:', err);
});

// 文本消息
wsClient.on('message.text', (frame) => {
  const content = frame.body.text?.content;
  const from = frame.body.from?.userid;
  console.log(`📝 收到文本消息: ${content} (from: ${from})`);

  // 回复消息
  wsClient.reply(frame, {
    msgtype: 'text',
    text: { content: `收到: ${content}` }
  });
});

// 图片消息
wsClient.on('message.image', (frame) => {
  console.log('🖼️ 收到图片消息');
});

// 进入会话
wsClient.on('event.enter_chat', (frame) => {
  console.log('👋 用户进入会话');
  
  wsClient.replyWelcome(frame, {
    msgtype: 'text',
    text: { content: '您好！我是 AI Life OS 智能助手，有什么可以帮您的吗？' }
  });
});

// 优雅退出
process.on('SIGINT', () => {
  console.log('\n🛑 正在停止...');
  wsClient.disconnect();
  process.exit(0);
});

console.log('✅ 客户端已启动，等待消息...');
