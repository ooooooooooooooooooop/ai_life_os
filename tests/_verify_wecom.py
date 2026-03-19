"""验收脚本：企业微信接入 A-D"""
import json, inspect, yaml, asyncio
from pathlib import Path
from datetime import datetime, timedelta
from unittest import mock

print('=== 验收：企业微信接入 ===\n')

# ===== A: wecom_models.py =====
print('--- A: wecom_models ---')
from interface.wecom_models import WeComConfig, WeComMessage, WeComAPIResponse, WeComSendMessage

cfg = WeComConfig(corp_id='wx123', corp_secret='sec', agent_id='1000')
assert cfg.is_configured() == True
cfg_empty = WeComConfig(corp_id='', corp_secret='', agent_id='')
assert cfg_empty.is_configured() == False
print('[PASS] WeComConfig.is_configured() 逻辑正确')

resp_ok = WeComAPIResponse(errcode=0, errmsg='ok', access_token='token123', expires_in=7200)
assert resp_ok.is_success() == True
resp_err = WeComAPIResponse(errcode=40001, errmsg='error')
assert resp_err.is_success() == False
print('[PASS] WeComAPIResponse.is_success() 逻辑正确')

msg = WeComSendMessage(touser='zhangsan', msgtype='text', agentid=1000, text={'content': 'hello'})
d = msg.to_dict()
assert d['touser'] == 'zhangsan'
assert d['msgtype'] == 'text'
assert d['agentid'] == 1000
print('[PASS] WeComSendMessage.to_dict() 正确')

# ===== B: WeComNotifier =====
print('\n--- B: WeComNotifier ---')
from interface.notifiers.wecom_notifier import WeComNotifier

n = WeComNotifier({'corp_id': 'wx123', 'corp_secret': 'sec', 'agent_id': '1000', 'enabled': True})
assert hasattr(n, 'send')
assert hasattr(n, 'send_raw')
assert hasattr(n, '_get_access_token')
assert hasattr(n, '_send_message')
print('[PASS] WeComNotifier 四个方法都存在')

n2 = WeComNotifier({'corp_id': 'wx', 'corp_secret': 's', 'agent_id': '1', 'enabled': True})
n2._access_token = 'cached_token'
n2._token_expire_time = datetime.now() + timedelta(hours=1)
token = n2._get_access_token()
assert token == 'cached_token', f'应走缓存，实际: {token}'
print('[PASS] access_token 缓存机制正确')

n_disabled = WeComNotifier({'corp_id': 'wx', 'corp_secret': 's', 'agent_id': '1', 'enabled': False})
assert n_disabled.send_raw('test') == False
print('[PASS] enabled=False 时 send_raw 返回 False')

assert n.get_name() == 'wecom'
print('[PASS] get_name() 返回 "wecom"')

# ===== C: wecom_bot =====
print('\n--- C: wecom_bot ---')
from interface.wecom_bot import router, _parse_xml_message, _build_xml_response

all_methods = set()
for r in router.routes:
    all_methods.update(r.methods)
assert 'GET' in all_methods, f'缺少 GET，现有: {all_methods}'
assert 'POST' in all_methods, f'缺少 POST，现有: {all_methods}'
print('[PASS] router 包含 GET 和 POST /webhook')

xml_str = (
    "<xml>"
    "<ToUserName><![CDATA[ww_corp]]></ToUserName>"
    "<FromUserName><![CDATA[zhangsan]]></FromUserName>"
    "<CreateTime>1700000000</CreateTime>"
    "<MsgType><![CDATA[text]]></MsgType>"
    "<Content><![CDATA[今天]]></Content>"
    "<MsgId>123456</MsgId>"
    "<AgentID>1000</AgentID>"
    "</xml>"
)
msg_dict = _parse_xml_message(xml_str)
assert msg_dict is not None
assert msg_dict['from_user_name'] == 'zhangsan'
assert msg_dict['content'] == '今天'
assert msg_dict['msg_type'] == 'text'
print('[PASS] _parse_xml_message 正确解析企业微信 XML')

assert _parse_xml_message('not xml at all') is None
print('[PASS] 非法 XML 返回 None')

reply_xml = _build_xml_response(to_user='zhangsan', from_user='ww_corp', content='你好')
assert 'zhangsan' in reply_xml
assert 'text' in reply_xml
assert '你好' in reply_xml
print('[PASS] _build_xml_response 构造正确')

# GET /webhook 用 httpx ASGITransport
import httpx
from fastapi import FastAPI
app_test = FastAPI()
app_test.include_router(router, prefix='/wecom')

async def test_endpoints():
    transport = httpx.ASGITransport(app=app_test)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        # GET echostr
        resp = await client.get('/wecom/webhook?echostr=hello123')
        assert resp.status_code == 200, f'GET 状态码: {resp.status_code}'
        assert 'hello123' in resp.text, f'echostr 未返回: {resp.text}'

        # POST XML
        resp2 = await client.post(
            '/wecom/webhook',
            content=xml_str.encode('utf-8'),
            headers={'Content-Type': 'application/xml'}
        )
        assert resp2.status_code == 200, f'POST 状态码: {resp2.status_code}'

asyncio.run(test_endpoints())
print('[PASS] GET /wecom/webhook 正确返回 echostr')
print('[PASS] POST /wecom/webhook 返回 200')

# ===== D: 系统集成 =====
print('\n--- D: 系统集成 ---')

app_src = open('web/backend/app.py', encoding='utf-8').read()
assert 'wecom' in app_src.lower(), 'app.py 未挂载 wecom 路由'
print('[PASS] app.py 已挂载 wecom 路由')

with open('scheduler/cron_config.yaml', encoding='utf-8') as f:
    cron_cfg = yaml.safe_load(f)
job_names = [j['name'] for j in cron_cfg['jobs']]
assert 'wecom-morning-push' in job_names, f'缺少 wecom-morning-push，现有: {job_names}'
morning = next(j for j in cron_cfg['jobs'] if j['name'] == 'wecom-morning-push')
assert morning['cron'] == '0 8 * * *', f'cron 错误: {morning["cron"]}'
print('[PASS] cron_config.yaml 包含 wecom-morning-push (0 8 * * *)')

sched_src = open('scheduler/cron_scheduler.py', encoding='utf-8').read()
assert 'wecom' in sched_src
print('[PASS] cron_scheduler.py 注册了 wecom handler')

with open('config/wecom.yaml', encoding='utf-8') as f:
    wecom_cfg = yaml.safe_load(f)
for key in ['corp_id', 'corp_secret', 'agent_id', 'to_user', 'enabled']:
    assert key in wecom_cfg, f'wecom.yaml 缺少: {key}'
assert wecom_cfg['enabled'] == False
assert wecom_cfg['to_user'] == '@all'
print('[PASS] config/wecom.yaml 格式正确，enabled 默认 false')

print('\n=== 全部验收通过 ===')
