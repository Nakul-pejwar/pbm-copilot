import React, { useEffect, useState } from 'react';
import { Card, Form, Input, Button, Alert, Space, Typography } from 'antd';
import { ApiOutlined } from '@ant-design/icons';
import { loadSettings, saveSettings, getConfig, CopilotSettings } from '../api';

interface Props {
  onSaved?: () => void;
}

const SettingsView: React.FC<Props> = ({ onSaved }) => {
  const [baseUrl, setBaseUrl] = useState('');
  const [token, setToken] = useState('');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<
    { ok: boolean; message: string } | undefined
  >(undefined);

  useEffect(() => {
    const s = loadSettings();
    setBaseUrl(s.baseUrl);
    setToken(s.token);
  }, []);

  const test = async () => {
    setTesting(true);
    setTestResult(undefined);
    saveSettings({ baseUrl, token });
    try {
      const cfg = await getConfig();
      setTestResult({
        ok: true,
        message: `Connected to ${cfg.service} v${cfg.version}${
          cfg.auth_required ? ' (token accepted)' : ' (no token required)'
        }`,
      });
    } catch (err) {
      setTestResult({
        ok: false,
        message: err instanceof Error ? err.message : 'Connection failed',
      });
    } finally {
      setTesting(false);
    }
  };

  const save = () => {
    saveSettings({ baseUrl, token });
    setTestResult({ ok: true, message: 'Settings saved.' });
    if (onSaved) onSaved();
  };

  return (
    <Card title="API connection" size="small" style={{ maxWidth: 640 }}>
      <Form layout="vertical">
        <Form.Item
          label="API base URL"
          extra="The PBM Copilot FastAPI service (docker stack)."
        >
          <Input
            prefix={<ApiOutlined />}
            placeholder="http://localhost:8000"
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
          />
        </Form.Item>
        <Form.Item
          label="API token (optional)"
          extra="Only needed if PBM_API_TOKEN is set on the API. Sent as X-API-Token."
        >
          <Input.Password
            placeholder="Leave empty for the local demo"
            value={token}
            onChange={(e) => setToken(e.target.value)}
          />
        </Form.Item>
        <Space>
          <Button type="primary" onClick={save}>
            Save
          </Button>
          <Button loading={testing} onClick={test}>
            Test connection
          </Button>
        </Space>
      </Form>
      {testResult && (
        <Alert
          type={testResult.ok ? 'success' : 'error'}
          showIcon
          message={testResult.message}
          style={{ marginTop: 12 }}
        />
      )}
      <Typography.Paragraph type="secondary" style={{ marginTop: 12, fontSize: 12 }}>
        Settings are stored in this browser only (localStorage). The default base URL
        points at the dockerized API on localhost:8000.
      </Typography.Paragraph>
    </Card>
  );
};

export default SettingsView;