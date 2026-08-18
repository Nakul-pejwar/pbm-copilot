import React, { useState } from 'react';
import {
  Button,
  Card,
  Form,
  Input,
  Upload,
  Alert,
  Tag,
  Space,
  Typography,
  Divider,
} from 'antd';
import { InboxOutlined } from '@ant-design/icons';
import { uploadClaims, UploadResult } from '../api';

const { Dragger } = Upload;

const RISK_COLORS: Record<string, string> = {
  CRITICAL: 'red',
  HIGH: 'orange',
  MEDIUM: 'gold',
  LOW: 'green',
};

const UploadView: React.FC = () => {
  const [companyName, setCompanyName] = useState('');
  const [file, setFile] = useState<File | undefined>(undefined);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);
  const [result, setResult] = useState<UploadResult | undefined>(undefined);

  const submit = async () => {
    if (!companyName.trim()) {
      setError('Company name is required.');
      return;
    }
    if (!file) {
      setError('Pick a CSV or Excel file first.');
      return;
    }
    setError(undefined);
    setResult(undefined);
    setLoading(true);
    try {
      const res = await uploadClaims(companyName.trim(), file);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Card title="Upload company claims" size="small">
        <Form layout="vertical">
          <Form.Item label="Company name" required>
            <Input
              placeholder="e.g. Acme Pharma"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
            />
          </Form.Item>
          <Form.Item label="Claim data file (.csv, .xlsx, .xls)">
            <Dragger
              accept=".csv,.xlsx,.xls"
              beforeUpload={(f) => {
                setFile(f);
                return false;
              }}
              fileList={file ? [{ uid: 'f', name: file.name }] : []}
              onRemove={() => setFile(undefined)}
              maxCount={1}
            >
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">
                Click or drag a claim file here to upload
              </p>
              <p className="ant-upload-hint">
                Re-uploading the same company replaces its previous data. The file
                must contain the 17 expected columns.
              </p>
            </Dragger>
          </Form.Item>
          <Button
            type="primary"
            loading={loading}
            onClick={submit}
            disabled={!companyName.trim() || !file}
          >
            Upload &amp; Process
          </Button>
        </Form>
        {error && (
          <Alert type="error" showIcon message={error} style={{ marginTop: 12 }} />
        )}
      </Card>

      {result && (
        <Card title="Upload result" size="small">
          <Space direction="vertical" size="middle">
            <Space size="large" wrap>
              <Typography.Text>
                Company: <b>{result.company_id}</b>
              </Typography.Text>
              <Typography.Text>
                Rows loaded: <b>{result.rows_loaded.toLocaleString()}</b>
              </Typography.Text>
              <Typography.Text>
                Anomalies: <b>{result.anomalies.toLocaleString()}</b>
              </Typography.Text>
            </Space>
            <Divider style={{ margin: '8px 0' }} />
            <Space wrap>
              {Object.entries(result.risk_levels).map(([level, count]) => (
                <Tag key={level} color={RISK_COLORS[level] ?? 'default'}>
                  {level}: {count.toLocaleString()}
                </Tag>
              ))}
            </Space>
            {result.dashboard_url && (
              <Button
                type="primary"
                ghost
                href={result.dashboard_url}
                target="_blank"
              >
                Open company dashboard in Superset
              </Button>
            )}
          </Space>
        </Card>
      )}
    </Space>
  );
};

export default UploadView;