"""验收脚本：evolution_engine A3-A5 + monitor B + scheduler C + manifest D"""
import json, tempfile, inspect
from pathlib import Path
from unittest import mock

print('=== 验收：A3-A5 + B + C + D ===\n')

# ===== A3: generate_rule =====
print('--- A3: generate_rule ---')
from core.evolution_engine import (
    generate_rule, ALLOWED_HOOKS, _build_generation_prompt,
    InvalidObservationError, validate_observation_format
)

sig = inspect.signature(generate_rule)
assert 'observation' in sig.parameters
print('[PASS] generate_rule() 签名正确')

try:
    generate_rule({'bad': 'data'})
    raise AssertionError('应该抛出异常')
except InvalidObservationError:
    print('[PASS] 非法 observation 抛出 InvalidObservationError')

prompt = _build_generation_prompt({
    'pattern': 'test', 'confidence': 0.8,
    'evidence': ['e1'], 'suggested_action': 'do something'
})
for hook in ALLOWED_HOOKS:
    assert hook in prompt, f'prompt 缺少 hook: {hook}'
print('[PASS] _build_generation_prompt 包含所有 hook 点')

# ===== A4: validate_rule =====
print('\n--- A4: validate_rule ---')
from core.evolution_engine import validate_rule

bad_syntax_rule = {
    'rule_id': 'test_001',
    'code': 'def detect_signal(context: dict) -> dict:\n    return {invalid python here',
    'target_hook': 'signal_detector',
    'description': 'test',
    'confidence': 0.8
}
passed, reason = validate_rule(bad_syntax_rule)
assert not passed, '语法错误代码应该失败'
print(f'[PASS] 语法错误被拒绝: {reason[:60]}')

wrong_name_rule = {
    'rule_id': 'test_002',
    'code': 'def wrong_name(context: dict) -> dict:\n    return {}',
    'target_hook': 'signal_detector',
    'description': 'test',
    'confidence': 0.8
}
passed, reason = validate_rule(wrong_name_rule)
assert not passed, '签名不匹配应该失败'
print(f'[PASS] 签名不匹配被拒绝: {reason[:60]}')

valid_code = (
    'def detect_signal(context: dict) -> dict:\n'
    '    return {\n'
    '        "signal_detected": False,\n'
    '        "signal_type": "none",\n'
    '        "severity": 0.0,\n'
    '        "description": "no signal"\n'
    '    }'
)
valid_rule = {
    'rule_id': 'test_003',
    'code': valid_code,
    'target_hook': 'signal_detector',
    'description': 'test valid rule',
    'confidence': 0.8
}
passed, reason = validate_rule(valid_rule)
assert passed, f'合法规则应该通过，失败原因: {reason}'
print('[PASS] 合法规则通过三关验证')

crash_code = (
    'def detect_signal(context: dict) -> dict:\n'
    '    raise RuntimeError("intentional crash")'
)
crash_rule = {
    'rule_id': 'test_004',
    'code': crash_code,
    'target_hook': 'signal_detector',
    'description': 'crash test',
    'confidence': 0.8
}
passed, reason = validate_rule(crash_rule)
assert not passed, '崩溃代码应该被拦截'
print(f'[PASS] 崩溃代码被沙箱拦截: {reason[:60]}')

# ===== A5: apply_rule =====
print('\n--- A5: apply_rule ---')
from core.evolution_engine import apply_rule, RuleNotValidatedError

unvalidated_rule = {
    'rule_id': 'test_005',
    'code': valid_code,
    'target_hook': 'signal_detector',
    'description': 'test',
    'confidence': 0.8
}
try:
    apply_rule(unvalidated_rule)
    raise AssertionError('应该抛出 RuleNotValidatedError')
except RuleNotValidatedError:
    print('[PASS] 未验证规则被 apply_rule 拒绝')

validated_rule = {
    'rule_id': 'test_rule_valid_001',
    'code': valid_code,
    'target_hook': 'signal_detector',
    'description': 'test validated rule',
    'confidence': 0.8,
    'validated': True
}
with tempfile.TemporaryDirectory() as tmpdir:
    tmp_rules_dir = Path(tmpdir) / 'evolved'
    tmp_manifest = tmp_rules_dir / 'manifest.json'
    with mock.patch('core.evolution_engine.RULES_DIR', tmp_rules_dir), \
         mock.patch('core.evolution_engine.MANIFEST_PATH', tmp_manifest):
        success = apply_rule(validated_rule)
        assert success, '已验证规则应写入成功'
        assert (tmp_rules_dir / 'test_rule_valid_001.py').exists(), '规则文件未写入'
        manifest = json.loads(tmp_manifest.read_text(encoding='utf-8'))
        assert any(r['rule_id'] == 'test_rule_valid_001' for r in manifest['rules'])
        print('[PASS] 已验证规则成功写入文件和 manifest')

# ===== B: evolution_monitor =====
print('\n--- B: evolution_monitor ---')
from core.evolution_monitor import evaluate_rules, rollback_rule, RuleNotFoundError

with tempfile.TemporaryDirectory() as tmpdir:
    tmp_manifest = Path(tmpdir) / 'manifest.json'
    with mock.patch('core.evolution_monitor.MANIFEST_PATH', tmp_manifest):
        result = evaluate_rules()
        assert result == []
        print('[PASS] 空 manifest 时 evaluate_rules 返回空列表')

with tempfile.TemporaryDirectory() as tmpdir:
    tmp_rules_dir = Path(tmpdir) / 'evolved'
    tmp_rules_dir.mkdir()
    tmp_manifest = tmp_rules_dir / 'manifest.json'
    tmp_manifest.write_text(json.dumps({'version': '1.0', 'rules': []}))
    with mock.patch('core.evolution_monitor.MANIFEST_PATH', tmp_manifest), \
         mock.patch('core.evolution_monitor.RULES_DIR', tmp_rules_dir):
        try:
            rollback_rule('nonexistent_rule')
            raise AssertionError('应该抛出 RuleNotFoundError')
        except RuleNotFoundError:
            print('[PASS] 不存在的规则抛出 RuleNotFoundError')

with tempfile.TemporaryDirectory() as tmpdir:
    tmp_rules_dir = Path(tmpdir) / 'evolved'
    tmp_rules_dir.mkdir()
    rule_file = tmp_rules_dir / 'rule_test_rb.py'
    rule_file.write_text('# test rule')
    tmp_manifest = tmp_rules_dir / 'manifest.json'
    tmp_manifest.write_text(json.dumps({
        'version': '1.0',
        'rules': [{'rule_id': 'rule_test_rb', 'status': 'active', 'target_hook': 'signal_detector'}]
    }))
    with mock.patch('core.evolution_monitor.MANIFEST_PATH', tmp_manifest), \
         mock.patch('core.evolution_monitor.RULES_DIR', tmp_rules_dir), \
         mock.patch('core.evolution_monitor._write_rollback_event', return_value=None):
        success = rollback_rule('rule_test_rb')
        assert success
        assert not rule_file.exists(), '规则文件应该被删除'
        manifest = json.loads(tmp_manifest.read_text(encoding='utf-8'))
        rule = next(r for r in manifest['rules'] if r['rule_id'] == 'rule_test_rb')
        assert rule['status'] == 'rolled_back'
        assert 'rollback_info' in rule
        print('[PASS] rollback_rule 正常回滚，文件删除，manifest 更新')

# ===== C: 调度器 =====
print('\n--- C: 调度器集成 ---')
import yaml
with open('scheduler/cron_config.yaml', 'r', encoding='utf-8') as f:
    cron_cfg = yaml.safe_load(f)
job_names = [j['name'] for j in cron_cfg['jobs']]
assert 'weekly-evolution' in job_names, f'缺少 weekly-evolution，现有: {job_names}'
assert 'daily-evolution-monitor' in job_names, f'缺少 daily-evolution-monitor'
weekly = next(j for j in cron_cfg['jobs'] if j['name'] == 'weekly-evolution')
daily_mon = next(j for j in cron_cfg['jobs'] if j['name'] == 'daily-evolution-monitor')
assert weekly['cron'] == '0 2 * * 0', f'cron 错误: {weekly["cron"]}'
assert daily_mon['cron'] == '0 3 * * *', f'cron 错误: {daily_mon["cron"]}'
print('[PASS] cron_config.yaml 两个新 job 配置正确')

sched_src = open('scheduler/cron_scheduler.py', encoding='utf-8').read()
assert 'weekly-evolution' in sched_src
assert 'daily-evolution-monitor' in sched_src
assert 'evolution_engine' in sched_src
assert 'evolution_monitor' in sched_src
print('[PASS] cron_scheduler.py 注册了两个新 handler')

# ===== D: manifest.json =====
print('\n--- D: 初始化文件 ---')
manifest_path = Path('skills/evolved/manifest.json')
assert manifest_path.exists(), 'manifest.json 不存在'
manifest = json.loads(manifest_path.read_text())
assert 'version' in manifest
assert 'rules' in manifest
assert isinstance(manifest['rules'], list)
print('[PASS] skills/evolved/manifest.json 存在且格式正确')

# Blueprint 无写入
import re
src = open('core/evolution_engine.py', encoding='utf-8').read()
contexts = re.findall(r'.{0,60}BLUEPRINT_PATH.{0,60}', src)
for ctx in contexts:
    assert '"w"' not in ctx and "'w'" not in ctx, f'Blueprint 可能有写入: {ctx}'
print('[PASS] Blueprint 路径无写入操作')

print('\n=== 全部验收通过 ===')
