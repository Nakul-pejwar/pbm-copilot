import React, { useCallback, useEffect, useState } from 'react';
import {
  Table,
  Button,
  Alert,
  Space,
  Tag,
  Card,
  Typography,
  Divider,
  Spin,
} from 'antd';
import { ReloadOutlined, MessageOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import { getAnomalies, explainClaim, AnomalyRow, ExplainResult } from '../api';

const RISK_COLORS: Record<string, string> = {
  CRITICAL: 'red',
  HIGH: 'orange',
  MEDIUM: 'gold',
  LOW: 'green',
};

const AnomaliesView: React.FC = () => {
  const [rows, setRows] = useState<AnomalyRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);
  const [explaining, setExplaining] = useState<string | undefined>(undefined);
  const [explanation, setExplanation] = useState<ExplainResult | undefined>(
    undefined,
  );

  const load = useCallback(async () => {
    setLoading(true);
    setError(undefined);
    try {
      setRows(await getAnomalies(25));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load anomalies');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const explain = async (claimId: string) => {
    setExplaining(claimId);
    setExplanation(undefined);
    try {
      setExplanation(await explainClaim(claimId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Explain failed');
    } finally {
      setExplaining(undefined);
    }
  };

  const columns: ColumnsType<AnomalyRow> = [
    { title: 'Claim', dataIndex: 'claim_id', key: 'claim_id' },
    { title: 'Date', dataIndex: 'claim_date', key: 'claim_date' },
    { title: 'Provider', dataIndex: 'provider_id', key: 'provider_id' },
    { title: 'Plan', dataIndex: 'plan_id', key: 'plan_id' },
    {
      title: 'Paid',
      dataIndex: 'paid_amount',
      key: 'paid_amount',
      align: 'right',
      render: (v: number) => `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2 })}`,
    },
    {
      title: 'Risk',
      dataIndex: 'risk_score',
      key: 'risk_score',
      align: 'right',
      render: (v: number) => <b>{v}</b>,
    },
    {
      title: 'Level',
      dataIndex: 'risk_level',
      key: 'risk_level',
      render: (v: string) => <Tag color={RISK_COLORS[v] ?? 'default'}>{v}</Tag>,
    },
    {
      title: 'Rules',
      dataIndex: 'rule_codes',
      key: 'rule_codes',
      render: (v: string) =>
        v
          ? v.split('|').map((code) => (
              <Tag key={code} style={{ margin: 2 }}>
                {code}
              </Tag>
            ))
          : <Tag>ML-only</Tag>,
    },
    {
      title: 'Action',
      key: 'action',
      render: (_, row) => (
        <Button
          size="small"
          icon={<MessageOutlined />}
          loading={explaining === row.claim_id}
          onClick={() => explain(row.claim_id)}
        >
          Explain
        </Button>
      ),
    },
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>
        Refresh
      </Button>
      {error && <Alert type="error" showIcon message={error} />}
      <Table
        rowKey="claim_id"
        columns={columns}
        dataSource={rows}
        loading={loading}
        size="small"
        pagination={false}
        scroll={{ x: true }}
      />
      {explaining && (
        <div style={{ textAlign: 'center', padding: 16 }}>
          <Spin tip={`Explaining ${explaining}...`} />
        </div>
      )}
      {explanation && (
        <Card
          size="small"
          title={
            <Space>
              <span>Explanation for {explanation.claim_id}</span>
              <Tag color={RISK_COLORS[explanation.risk_level] ?? 'default'}>
                {explanation.risk_level} · {explanation.risk_score}
              </Tag>
              <Tag>{explanation.mode === 'llm' ? 'GenAI' : 'Deterministic fallback'}</Tag>
            </Space>
          }
        >
          <Typography.Paragraph style={{ whiteSpace: 'pre-wrap' }}>
            {explanation.explanation}
          </Typography.Paragraph>
          <Divider style={{ margin: '8px 0' }} />
          <Typography.Text type="secondary">
            Evidence: {explanation.evidence || 'ML baseline anomaly'}
          </Typography.Text>
        </Card>
      )}
    </Space>
  );
};

export default AnomaliesView;