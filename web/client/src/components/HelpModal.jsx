import { useState } from 'react';
import Button from './Button';

export default function HelpModal({ isOpen, onClose }) {
  const [activeSection, setActiveSection] = useState('getting-started');

  if (!isOpen) return null;

  const sections = [
    {
      id: 'getting-started',
      title: '快速开始',
      content: `
## 欢迎使用 AI Life OS

AI Life OS 是一个由AI驱动的个人生活操作系统，帮助你管理时间、习惯和目标。

### 基本概念

1. **愿景 (Vision)**: 你长期追求的方向和理想状态
2. **目标 (Goal)**: 具体的、可衡量的短期或中期目标
3. **任务 (Task)**: 实现目标的具体行动步骤
4. **Guardian**: AI守护系统，监控你的行为并提供反馈

### 开始使用

1. 创建你的第一个愿景
2. 将愿景分解为具体目标
3. 为目标设定任务和时间表
4. Guardian会自动监控你的进度
      `,
    },
    {
      id: 'vision',
      title: '愿景管理',
      content: `
## 愿景管理

### 什么是愿景？

愿景是你长期追求的方向，它应该是：
- 激励人心的
- 长期的（1-5年）
- 与你的价值观一致

### 如何创建愿景？

1. 点击"新建愿景"按钮
2. 描述你想要达到的状态
3. AI会帮助你细化和完善愿景
4. 设定愿景的时间范围

### 愿景示例

- "成为一名优秀的软件工程师"
- "建立健康的生活方式"
- "实现财务自由"
      `,
    },
    {
      id: 'goals',
      title: '目标设定',
      content: `
## 目标设定

### SMART原则

目标应该符合SMART原则：
- **S**pecific (具体的)
- **M**easurable (可衡量的)
- **A**chievable (可实现的)
- **R**elevant (相关的)
- **T**ime-bound (有时限的)

### 目标分解

AI会帮助你将目标分解为：
- 具体的任务
- 时间节点
- 里程碑

### 目标追踪

- 查看目标进度
- 接收Guardian提醒
- 调整目标计划
      `,
    },
    {
      id: 'guardian',
      title: 'Guardian系统',
      content: `
## Guardian守护系统

### Guardian的作用

Guardian是你的AI守护者，它会：
- 监控你的行为模式
- 检测偏离目标的行为
- 提供温和但坚定的提醒
- 帮助你保持正轨

### Guardian提醒

Guardian会在以下情况提醒你：
- 长时间未完成重要任务
- 重复放弃或跳过任务
- 行为模式偏离目标
- 需要调整计划时

### 如何响应Guardian

- 认真对待Guardian的提醒
- 反思自己的行为
- 调整计划或重新承诺
- 与Guardian对话获取建议
      `,
    },
    {
      id: 'faq',
      title: '常见问题',
      content: `
## 常见问题

### Q: 如何重置引导流程？

A: 在设置中点击"重置引导"按钮。

### Q: Guardian会打扰我吗？

A: Guardian设计为温和但坚定，只在必要时提醒你。你可以在设置中调整提醒频率。

### Q: 数据会同步到云端吗？

A: 是的，你的数据会安全地存储在云端，支持多设备同步。

### Q: 如何删除我的数据？

A: 在设置中可以导出或删除所有数据。

### Q: 支持离线使用吗？

A: 是的，AI Life OS支持PWA，可以离线使用基本功能。
      `,
    },
  ];

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 border border-white/10 rounded-2xl shadow-2xl max-w-4xl w-full h-[80vh] flex overflow-hidden">
        {/* Sidebar */}
        <div className="w-64 bg-slate-900/50 border-r border-white/10 p-4">
          <h2 className="text-xl font-bold text-white mb-6">帮助文档</h2>
          <nav className="space-y-2">
            {sections.map((section) => (
              <button
                key={section.id}
                onClick={() => setActiveSection(section.id)}
                className={`
                  w-full text-left px-4 py-2 rounded-lg transition-colors
                  ${activeSection === section.id
                    ? 'bg-blue-500 text-white'
                    : 'text-gray-400 hover:bg-slate-700 hover:text-white'
                  }
                `}
              >
                {section.title}
              </button>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="flex-1 flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-white/10">
            <h3 className="text-2xl font-bold text-white">
              {sections.find(s => s.id === activeSection)?.title}
            </h3>
            <Button variant="secondary" onClick={onClose}>
              关闭
            </Button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto p-6">
            <div className="prose prose-invert max-w-none">
              <MarkdownContent>
                {sections.find(s => s.id === activeSection)?.content}
              </MarkdownContent>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MarkdownContent({ children }) {
  // 简单的Markdown渲染
  const lines = children.trim().split('\n');
  
  return (
    <div className="space-y-4">
      {lines.map((line, index) => {
        if (line.startsWith('## ')) {
          return <h2 key={index} className="text-xl font-bold text-white mt-6 mb-4">{line.slice(3)}</h2>;
        }
        if (line.startsWith('### ')) {
          return <h3 key={index} className="text-lg font-semibold text-white mt-4 mb-2">{line.slice(4)}</h3>;
        }
        if (line.startsWith('- ')) {
          return <li key={index} className="text-gray-300 ml-4">{line.slice(2)}</li>;
        }
        if (line.match(/^\d+\. /)) {
          return <li key={index} className="text-gray-300 ml-4 list-decimal">{line.replace(/^\d+\. /, '')}</li>;
        }
        if (line.trim() === '') {
          return <div key={index} className="h-2" />;
        }
        return <p key={index} className="text-gray-300">{line}</p>;
      })}
    </div>
  );
}
