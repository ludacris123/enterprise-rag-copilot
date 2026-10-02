import json
from unittest.mock import patch
import httpx
from app import providers
from app.config import get_settings


def test_groq_http_contract():
    def handler(request):
        assert str(request.url)=='https://api.groq.com/openai/v1/chat/completions'
        assert request.headers['Authorization']=='Bearer dummy-test-key'
        body=json.loads(request.content)
        assert body['messages'][0]['role']=='system' and body['messages'][1]['role']=='user'
        assert body['response_format']=={'type':'json_object'} and body['max_tokens']==1200
        return httpx.Response(200,json={'choices':[{'message':{'content':'{"tool":"knowledge_search"}'}}], 'usage':{'prompt_tokens':12,'completion_tokens':6}})
    client=httpx.Client(transport=httpx.MockTransport(handler),trust_env=False)
    with patch.object(get_settings(),'groq_api_key','dummy-test-key'),patch('app.providers.httpx.Client',return_value=client):
        result=providers.completion('groq','System instruction','Question',True)
    assert result['input_tokens']==12 and result['output_tokens']==6


def test_missing_key_reports_error_without_fallback():
    with patch.object(get_settings(),'groq_api_key',''):
        try:providers.completion('groq','System','Question')
        except providers.ProviderError as exc:assert 'not configured' in str(exc)
        else:raise AssertionError('Missing key was not rejected')
