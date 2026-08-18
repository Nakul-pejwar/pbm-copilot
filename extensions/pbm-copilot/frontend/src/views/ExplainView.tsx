import React, { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Form,
  Input,
  Select,
  Space,
  Card,
  Alert,
  Tag,
  Typography,
  Divider,
} from 'antd';
import { MessageOutlined } from '@ant-design/icons';
import { explainClaim, getCompanies, ExplainResult, Company } from '../api';

const RISK_COLORS: Record<string, string> = {
  CRITICAL: 'red',
  HIGH: 'orange',
  MEDIUM: 'gold',
  LOW: 'green',
};

const ExplainView: React.FC = () => {
  const [claimId, setClaimId] = useState('');
  const [companyId, setCompanyId] = useState<string | undefined>(undefined);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);
  const [result, setResult] = useState<ExplainResult | undefined>(undefined);

  useEffect(() => {
    getCompanies()
      .then(setCompanies)
      .catch(() => setCompanies([]));
  }, []);

  const submit = useCallback(
    async (id: string, cid?: string) => {
      if (!id.trim()) {
        setError('Claim ID is required.');
        return;
      }
      setError(undefined);
      setResult(undefined);
      setLoading(true);
      try {
        setResult(await explainClaim(id.trim(), cid));
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Explain failed');
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Card title="Explain an anomaly" size="small">
        <Form layout="inline">
          <Form.Item label="Claim ID" required style={{ minWidth: 260 }}>
            <Input
              placeholder="CLM-00012345"
              value={claimId}
              onChange={(e) => setClaimId(e.target.value)}
            />
          </Form.Item>
          <Form.Item label="Company (optional)">
            <Select
              allowClear
              placeholder="All companies"
              style={{ minWidth: 200 }}
              value={companyId}
              onChange={setCompanyId}
              options={companies.map((c) => ({
                value: c.company_id,
                label: `${c.name} (${c.company_id})`,
              }))}
            />
          </Form.Item>
          <Form.Item>
            <Button
              type="primary"
              icon={<MessageOutlined />}
              loading={loading}
              onClick={() => submit(claimId, companyId)}
            >
              Explain
            </Button>
          </Form.Item>
        </Form>
        {error && <Alert type="error" showIcon message={error} style={{ marginTop: 12 }} />}
      </Card>

      {result && (
        <Card
          size="small"
          title={
            <Space>
              <span>{result.claim_id}</span>
              <Tag color={RISK_COLORS[result.risk_level] ?? 'default'}>
                {result.risk_level} · {result.risk_score}
              </Tag>
              <Tag>{result.mode === 'llm' ? 'GenAI' : 'Deterministic fallback'}</Tag>
            </Space>
          }
        >
          <Typography.Text type="secondary">
            Company: {result.company_id} · Provider: {result.provider_id} · Paid: $
            {Number(result.paid_amount).toLocaleString()}
          </Typography.Text>
          <Divider style={{ margin: '8px 0' }} />
          <Typography.Paragraph style={{ whiteSpace: 'pre-wrap' }}>
            {result.explanation}
          </Typography.Paragraph>
          {result.rule_codes && (
            <div>
              <Typography.Text type="secondary">Triggered rules: </Typography.Text>
              {result.rule_codes.split('|').map((code) => (
                <Tag key={code} style={{ margin: 2 }}>
                  {code}
                </Tag>
              ))}
            </div>
          )}
        </Card>
      )}
    </Space>
  );
};

export default ExplainView;