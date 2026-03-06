import { useState, useEffect } from 'react';
import Button from './Button';

export default function OnboardingTour({ onComplete }) {
  const [currentStep, setCurrentStep] = useState(0);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // 检查是否已完成引导
    const completed = localStorage.getItem('onboarding_completed');
    if (!completed) {
      setIsVisible(true);
    }
  }, []);

  const steps = [
    {
      title: '欢迎使用 AI Life OS',
      description: '这是一个由AI驱动的个人生活操作系统，帮助你管理时间、习惯和目标，守护你走向更好的生活。',
      icon: '🏠',
    },
    {
      title: '创建你的愿景',
      description: '愿景是你长期追求的方向。点击"新建愿景"开始规划你的人生目标。',
      icon: '🎯',
      target: '/vision/new',
    },
    {
      title: '设定具体目标',
      description: '将愿景分解为可执行的目标。每个目标都应该具体、可衡量、可实现。',
      icon: '📋',
      target: '/goals/new',
    },
    {
      title: 'Guardian守护系统',
      description: 'Guardian会监控你的行为，在发现偏差时温和但坚定地提醒你，帮助你保持正轨。',
      icon: '🛡️',
    },
    {
      title: '开始你的旅程',
      description: '现在你已经了解了基本功能，开始创建你的第一个目标吧！',
      icon: '🚀',
    },
  ];

  const handleNext = () => {
    if (currentStep < steps.length - 1) {
      setCurrentStep(currentStep + 1);
    } else {
      handleComplete();
    }
  };

  const handlePrevious = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleSkip = () => {
    handleComplete();
  };

  const handleComplete = () => {
    localStorage.setItem('onboarding_completed', 'true');
    setIsVisible(false);
    if (onComplete) {
      onComplete();
    }
  };

  if (!isVisible) return null;

  const step = steps[currentStep];

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 border border-white/10 rounded-2xl shadow-2xl max-w-md w-full overflow-hidden">
        {/* Progress Bar */}
        <div className="h-1 bg-slate-700">
          <div
            className="h-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all duration-300"
            style={{ width: `${((currentStep + 1) / steps.length) * 100}%` }}
          />
        </div>

        {/* Content */}
        <div className="p-8">
          {/* Icon */}
          <div className="text-6xl mb-6 text-center">{step.icon}</div>

          {/* Title */}
          <h2 className="text-2xl font-bold text-white mb-4 text-center">
            {step.title}
          </h2>

          {/* Description */}
          <p className="text-gray-400 text-center mb-8 leading-relaxed">
            {step.description}
          </p>

          {/* Navigation */}
          <div className="flex items-center justify-between gap-4">
            {/* Previous Button */}
            {currentStep > 0 ? (
              <Button variant="secondary" onClick={handlePrevious}>
                上一步
              </Button>
            ) : (
              <div />
            )}

            {/* Step Indicators */}
            <div className="flex gap-2">
              {steps.map((_, index) => (
                <div
                  key={index}
                  className={`
                    w-2 h-2 rounded-full transition-all
                    ${index === currentStep ? 'bg-blue-500 w-6' : 'bg-slate-600'}
                  `}
                />
              ))}
            </div>

            {/* Next/Skip Button */}
            <div className="flex gap-2">
              {currentStep < steps.length - 1 && (
                <Button variant="secondary" onClick={handleSkip}>
                  跳过
                </Button>
              )}
              <Button onClick={handleNext}>
                {currentStep === steps.length - 1 ? '开始使用' : '下一步'}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function useOnboarding() {
  const [isCompleted, setIsCompleted] = useState(false);

  useEffect(() => {
    const completed = localStorage.getItem('onboarding_completed');
    setIsCompleted(!!completed);
  }, []);

  const completeOnboarding = () => {
    localStorage.setItem('onboarding_completed', 'true');
    setIsCompleted(true);
  };

  const resetOnboarding = () => {
    localStorage.removeItem('onboarding_completed');
    setIsCompleted(false);
  };

  return { isCompleted, completeOnboarding, resetOnboarding };
}
